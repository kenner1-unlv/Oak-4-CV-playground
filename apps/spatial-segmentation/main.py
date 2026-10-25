"""OAK4 standalone segmentation, mask-aware range, and browser visualization."""

import json
import logging
import os
import socket
from pathlib import Path

import cv2
import depthai as dai
import numpy as np
from depthai_nodes.node import ParsingNeuralNetwork
from depthai_nodes.utils import AnnotationHelper

from hud import rounded_brackets, target_lines
from model_controls import (IRProjectorControl, MonoFrameStore, SceneState,
                            ZoomControl, start_control_server)
from mono_projection import project_point
from perception_core import Observation, SpatialEstimate, TrackManager, estimate_spatial
from tile_geometry import (depth_region_bounds, mask_and_points_for_tile,
                           paired_crops, remap_box, tiles_for_grid, Tile)


LOG = logging.getLogger("oak4-perception")
FPS = int(os.getenv("OAK4_FPS", "30"))
GRID_SIZE = int(os.getenv("OAK4_GRID_SIZE", "2"))
SCAN_MODE = os.getenv("OAK4_SCAN_MODE", "full").strip().lower()
PAIR_SCALE = float(os.getenv("OAK4_PAIR_SCALE", "1.5"))
STEREO_SIZE = (640, 400)
VIDEO_SCALE = int(os.getenv("OAK4_VIDEO_SCALE", "4"))
VIDEO_BITRATE_KBPS = int(os.getenv("OAK4_VIDEO_BITRATE_KBPS", "60000"))
MODEL_YAML = Path(__file__).parent / "models/yolov8_seg_large.RVC4.yaml"


class MonoCaptureNode(dai.node.HostNode):
    """Retain the latest grayscale sensor frame for an on-demand JPEG view."""

    def build(self, frames: dai.Node.Output, store: MonoFrameStore,
              name: str) -> "MonoCaptureNode":
        self.store = store
        self.name = name
        self.link_args(frames)
        return self

    def process(self, frame: dai.ImgFrame) -> None:
        self.store.publish(self.name, np.asarray(frame.getCvFrame()).copy())


class ResultNode(dai.node.HostNode):
    """Join segmentation to an organized RGB point cloud on the camera CPU."""

    def __init__(self) -> None:
        super().__init__()
        self.annotations = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.labels: list[str] = []
        self.tracks = TrackManager()
        self._logged_shapes = False
        self._udp: socket.socket | None = None
        self._target: tuple[str, int] | None = None
        self.tiles = ()
        self.canvas_size = (0, 0)
        self.viewer_size = (0, 0)
        self.scene_state: SceneState | None = None
        self.mono_projectors: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self.zoom_tile: Tile | None = None

    def build(
        self, detections: dai.Node.Output, point_cloud: dai.Node.Output,
        tile_ids: dai.Node.Output, labels: list[str], tiles: tuple,
        canvas_size: tuple[int, int], viewer_size: tuple[int, int],
        scene_state: SceneState,
        mono_projectors: dict[str, tuple[np.ndarray, np.ndarray]],
    ) -> "ResultNode":
        self.labels = labels
        self.tiles = tiles
        if SCAN_MODE == "zoom":
            self.zoom_tile = tiles[1]
        self.tracks = TrackManager(
            grid_size=GRID_SIZE, sweep_frames=len(tiles)
        )
        self.canvas_size = canvas_size
        self.viewer_size = viewer_size
        self.scene_state = scene_state
        self.mono_projectors = mono_projectors
        self.link_args(detections, point_cloud, tile_ids)
        host = os.getenv("ORIN_RESULT_HOST", "").strip()
        if host:
            self._target = (host, int(os.getenv("ORIN_RESULT_PORT", "8766")))
            self._udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self

    def process(
        self, message: dai.ImgDetections, cloud: dai.PointCloudData,
        tile_message: dai.Buffer,
    ) -> None:
        tile_data = tile_message.getData()
        tile_id = int(tile_data[0])
        if len(tile_data) >= 9:
            bounds = [int(tile_data[i]) | (int(tile_data[i + 1]) << 8)
                      for i in (1, 3, 5, 7)]
            tile = Tile(*bounds)
        else:
            tile = self.tiles[tile_id]
        if SCAN_MODE == "zoom" and tile_id == 1:
            self.zoom_tile = tile
        width, height = cloud.getWidth(), cloud.getHeight()
        if height <= 1:
            LOG.warning("Point cloud is not organized; skipping spatial frame")
            return
        # RGBD's setDepthUnits describes its input depth frame. With the stereo
        # frame in millimeters, getPoints() supplies floating-point meters.
        points = np.asarray(cloud.getPoints(), dtype=np.float32) * 1000.0
        if points.size != width * height * 3:
            LOG.warning("Point cloud size mismatch; skipping spatial frame")
            return
        points = points.reshape((height, width, 3))
        if not self._logged_shapes and message.detections:
            first_mask = message.getCvSegmentationMaskByIndex(0)
            positive_z = points[:, :, 2]
            positive_z = positive_z[np.isfinite(positive_z) & (positive_z > 0)]
            LOG.info(
                "Spatial diagnostics: tile=%s cloud=%sx%s mask=%s mask_pixels=%s "
                "message_mask=%sx%s positive_z_median_mm=%.1f",
                tile_id, width, height,
                None if first_mask is None else first_mask.shape,
                None if first_mask is None else int(np.count_nonzero(first_mask)),
                message.getSegmentationMaskWidth(),
                message.getSegmentationMaskHeight(),
                float(np.median(positive_z)) if positive_z.size else float("nan"),
            )
            self._logged_shapes = True
        observations: list[Observation] = []
        for index, detection in enumerate(message.detections):
            name = detection.labelName or (
                self.labels[detection.label]
                if 0 <= detection.label < len(self.labels)
                else str(detection.label)
            )
            mask = message.getCvSegmentationMaskByIndex(index)
            outline = ()
            if mask is None or mask.ndim != 2:
                spatial = SpatialEstimate(None, None, 0.0, None)
            else:
                reduced, region = mask_and_points_for_tile(
                    mask, points, tile, self.canvas_size
                )
                spatial = estimate_spatial(reduced, region)
                contours, _ = cv2.findContours(
                    reduced.astype(np.uint8), cv2.RETR_EXTERNAL,
                    cv2.CHAIN_APPROX_SIMPLE,
                )
                if contours:
                    contour = max(contours, key=cv2.contourArea)
                    contour = cv2.approxPolyDP(contour, 2.0, True)
                    region_x0, region_y0, _, _ = depth_region_bounds(
                        tile, self.canvas_size, (width, height)
                    )
                    outline = tuple(
                        ((region_x0 + int(x)) / width,
                         (region_y0 + int(y)) / height)
                        for x, y in contour.reshape(-1, 2)
                    )
            observations.append(
                Observation(
                    name.lower(), float(detection.confidence),
                    remap_box(
                        (float(detection.xmin), float(detection.ymin),
                         float(detection.xmax), float(detection.ymax)),
                        tile, self.canvas_size,
                    ),
                    spatial, index, outline, tile_id,
                )
            )

        assigned = self.tracks.update(observations)
        observed_ids = {track.id for track, _ in assigned}
        annotations = AnnotationHelper()
        if self.zoom_tile is not None:
            x0 = self.zoom_tile.x / self.canvas_size[0]
            y0 = self.zoom_tile.y / self.canvas_size[1]
            x1 = (self.zoom_tile.x + self.zoom_tile.width) / self.canvas_size[0]
            y1 = (self.zoom_tile.y + self.zoom_tile.height) / self.canvas_size[1]
            annotations.draw_polyline(
                [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                outline_color=(1.0, 0.85, 0.12, 0.8), fill_color=None,
                thickness=2, closed=True,
            )
        records = []
        scene_objects = []
        for track in self.tracks.active():
            item = track.last_observation
            parts = track.recent_parts(
                self.tracks.frame_number, max_age=self.tracks.part_max_age
            )
            if not parts:
                continue
            label = track.label or (
                "animal" if item.label in {"cat", "dog"} else "object"
            )
            x0, y0, x1, y1 = track.bbox
            scores = [part.score for part in parts]
            coverage = float(np.mean([
                part.spatial.valid_fraction for part in parts
            ]))
            coordinates = [part.spatial.xyz_mm for part in parts
                           if part.spatial.xyz_mm is not None]
            xyz_mm = (tuple(float(v) for v in np.median(coordinates, axis=0))
                      if coordinates else None)
            ranges = [part.spatial.range_m for part in parts
                      if part.spatial.range_m is not None]
            range_m = float(np.median(ranges)) if ranges else None
            observed = track.id in observed_ids
            locked = track.label is not None and range_m is not None
            color = ((1.0, 0.16, 0.12, 1.0) if locked
                     else (1.0, 0.58, 0.16, 0.90))
            for bracket in rounded_brackets(track.bbox, self.viewer_size):
                annotations.draw_polyline(
                    list(bracket), outline_color=color, fill_color=None,
                    thickness=3,
                )
            for part in parts:
                if len(part.mask_outline) >= 3:
                    annotations.draw_polyline(
                        list(part.mask_outline),
                        outline_color=color,
                        fill_color=(1.0, 0.16, 0.12, 0.12),
                        closed=True,
                    )
            if locked and max(scores) >= 0.5:
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                annotations.draw_line(
                    (cx - 0.005, cy), (cx + 0.005, cy),
                    color=color, thickness=1,
                )
                annotations.draw_line(
                    (cx, cy - 0.008), (cx, cy + 0.008),
                    color=color, thickness=1,
                )
            lines = target_lines(
                track.id, label, range_m, max(scores),
                coverage, xyz_mm,
                wide_tag=(x1 - x0 >= 0.13 and y1 - y0 >= 0.10),
            )
            row_step = 0.028
            tag_y = max(0.012, y0 - row_step * len(lines) - 0.005)
            tag_x = min(max(x0, 0.005), 0.68)
            for row, line in enumerate(lines):
                annotations.draw_text(
                    line, (tag_x, tag_y + row * row_step),
                    size=22 if row == 0 else 16,
                    color=color if row == 0 else (1.0, 0.68, 0.61, 1.0),
                    background_color=(0.02, 0.02, 0.02, 0.84),
                )
            record = {
                "track_id": track.id,
                "label": label,
                "detector_label": item.label,
                "detector_score": max(scores),
                "bbox_xyxy_norm": track.bbox,
                "xyz_mm": xyz_mm,
                "range_m": range_m,
                "depth_valid_fraction": coverage,
                "depth_spread_mm": item.spatial.spread_mm,
                "track_state": "tracked" if track.id in observed_ids else "held",
                "age_frames": track.missed,
                "tile_parts": len(parts),
            }
            records.append(record)
            scene_objects.append({
                **record,
                "mask_outlines": [part.mask_outline for part in parts
                                  if len(part.mask_outline) >= 3],
                "mono_markers": {
                    name: projected
                    for name, (transform, intrinsics) in
                    self.mono_projectors.items()
                    if (projected := project_point(
                        xyz_mm, transform, intrinsics, STEREO_SIZE
                    )) is not None
                },
            })
        self.annotations.send(
            annotations.build(message.getTimestamp(), message.getSequenceNum())
        )
        packet_data = {
            "schema_version": 1,
            "frame_id": message.getSequenceNum(),
            "tile_id": tile_id,
            "device_timestamp_ns": int(
                message.getTimestampDevice().total_seconds() * 1_000_000_000
            ),
            "objects": records,
        }
        self.scene_state.publish({
            **packet_data, "objects": scene_objects,
            "zoom_region_xyxy_norm": (
                [self.zoom_tile.x / self.canvas_size[0],
                 self.zoom_tile.y / self.canvas_size[1],
                 (self.zoom_tile.x + self.zoom_tile.width) / self.canvas_size[0],
                 (self.zoom_tile.y + self.zoom_tile.height) / self.canvas_size[1]]
                if self.zoom_tile is not None else None
            ),
        })
        if self._udp is not None and self._target is not None:
            packet = json.dumps(packet_data, separators=(",", ":")).encode("utf-8")
            try:
                self._udp.sendto(packet, self._target)
            except OSError:
                LOG.exception("Could not send result packet to Orin")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not 1 <= FPS <= 60 or not 1 <= VIDEO_SCALE <= 6:
        raise ValueError("OAK4_FPS must be 1..60 and OAK4_VIDEO_SCALE must be 1..6")
    if GRID_SIZE not in (2, 3):
        raise ValueError("OAK4_GRID_SIZE must be 2 or 3")
    if SCAN_MODE not in ("grid", "paired", "full", "zoom"):
        raise ValueError("OAK4_SCAN_MODE must be grid, paired, full, or zoom")
    if not 1000 <= VIDEO_BITRATE_KBPS <= 60000:
        raise ValueError("OAK4_VIDEO_BITRATE_KBPS must be 1000..60000")
    archive = dai.NNArchive(
        dai.getModelFromZoo(dai.NNModelDescription.fromYamlFile(str(MODEL_YAML)))
    )
    model_size = archive.getInputSize()
    canvas_size = (model_size[0] * GRID_SIZE, model_size[1] * GRID_SIZE)
    if SCAN_MODE == "grid":
        tiles = tiles_for_grid(*canvas_size, GRID_SIZE)
    elif SCAN_MODE == "paired":
        tiles = paired_crops(canvas_size, model_size, PAIR_SCALE)
    elif SCAN_MODE == "zoom":
        tiles = (Tile(0, 0, *canvas_size),
                 Tile((canvas_size[0] - model_size[0]) // 2,
                      (canvas_size[1] - model_size[1]) // 2,
                      *model_size))
    else:
        tiles = (Tile(0, 0, *canvas_size),)
    video_size = (model_size[0] * VIDEO_SCALE, model_size[1] * VIDEO_SCALE)
    if video_size[0] * video_size[1] * FPS > 248_000_000:
        raise ValueError("H.264 output exceeds the encoder pixel-rate limit")
    labels = archive.getConfig().model.heads[0].metadata.classes
    scene_state = SceneState()
    mono_frames = MonoFrameStore()
    device = dai.Device()
    if device.getPlatform() != dai.Platform.RVC4:
        raise RuntimeError("This app requires an RVC4 camera")
    mono_projectors = {}
    try:
        calibration = device.readCalibration()
        for name, socket in (
            ("left", dai.CameraBoardSocket.CAM_B),
            ("right", dai.CameraBoardSocket.CAM_C),
        ):
            transform = np.asarray(calibration.getCameraExtrinsics(
                dai.CameraBoardSocket.CAM_A, socket,
                unit=dai.LengthUnit.MILLIMETER,
            ), dtype=float)
            intrinsics = np.asarray(calibration.getCameraIntrinsics(
                socket, *STEREO_SIZE,
            ), dtype=float)
            if transform.shape != (4, 4) or intrinsics.shape != (3, 3):
                raise ValueError("unexpected calibration matrix shape")
            mono_projectors[name] = (transform, intrinsics)
    except (RuntimeError, ValueError) as exc:
        LOG.warning("Mono target markers unavailable: %s", exc)
    viewer = dai.RemoteConnection(httpPort=8084)
    with dai.Pipeline(device) as pipeline:
        color = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
        tile_source = color.requestOutput(
            canvas_size, dai.ImgFrame.Type.BGR888i, fps=FPS,
            enableUndistortion=True,
        )
        rgbd_color = color.requestOutput(
            model_size, dai.ImgFrame.Type.RGB888i, fps=FPS,
            enableUndistortion=True,
        )
        left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
        right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
        mono_left = left.requestOutput(
            STEREO_SIZE, dai.ImgFrame.Type.GRAY8, fps=FPS
        )
        mono_right = right.requestOutput(
            STEREO_SIZE, dai.ImgFrame.Type.GRAY8, fps=FPS
        )
        stereo = pipeline.create(dai.node.StereoDepth).build(
            left=mono_left,
            right=mono_right,
            presetMode=dai.node.StereoDepth.PresetMode.HIGH_DETAIL,
        )
        pipeline.create(MonoCaptureNode).build(mono_left, mono_frames, "left")
        pipeline.create(MonoCaptureNode).build(mono_right, mono_frames, "right")
        stereo.setLeftRightCheck(True)
        align = pipeline.create(dai.node.ImageAlign)
        stereo.depth.link(align.input)
        rgbd_color.link(align.inputAlignTo)
        rgbd = pipeline.create(dai.node.RGBD).build()
        rgbd.setDepthUnits(
            dai.StereoDepthConfig.AlgorithmControl.DepthUnit.MILLIMETER
        )
        align.outputAligned.link(rgbd.inDepth)
        rgbd_color.link(rgbd.inColor)

        script = pipeline.create(dai.node.Script)
        script.setScript(f"""
TILES = {[(t.x, t.y, t.width, t.height) for t in tiles]!r}
SCAN_MODE = {SCAN_MODE!r}
ZOOM_W, ZOOM_H = {model_size!r}
zoom_x, zoom_y = TILES[-1][0], TILES[-1][1]
index = 0
while True:
    frame = node.inputs['frame'].get()
    if SCAN_MODE == 'zoom':
        update = node.inputs['zoom'].tryGet()
        if update is not None:
            raw = update.getData()
            if len(raw) >= 4:
                zoom_x = int(raw[0]) | (int(raw[1]) << 8)
                zoom_y = int(raw[2]) | (int(raw[3]) << 8)
        if index == 0:
            x, y, w, h = TILES[0]
        else:
            x, y, w, h = zoom_x, zoom_y, ZOOM_W, ZOOM_H
    else:
        x, y, w, h = TILES[index]
    cfg = ImageManipConfig()
    cfg.addCrop(x, y, w, h)
    cfg.setOutputSize({model_size[0]}, {model_size[1]}, ImageManipConfig.ResizeMode.STRETCH)
    cfg.setFrameType(ImgFrame.Type.BGR888i)
    cfg.setTimestamp(frame.getTimestamp())
    cfg.setTimestampDevice(frame.getTimestampDevice())
    cfg.setSequenceNum(frame.getSequenceNum())
    tile_id = Buffer()
    tile_id.setData([index, x & 255, x >> 8, y & 255, y >> 8,
                     w & 255, w >> 8, h & 255, h >> 8])
    tile_id.setTimestamp(frame.getTimestamp())
    tile_id.setTimestampDevice(frame.getTimestampDevice())
    tile_id.setSequenceNum(frame.getSequenceNum())
    node.outputs['config'].send(cfg)
    node.outputs['image'].send(frame)
    node.outputs['tile'].send(tile_id)
    index = (index + 1) % {len(tiles)}
""")
        tile_source.link(script.inputs["frame"])
        zoom_queue = (script.inputs["zoom"].createInputQueue(maxSize=2,
                       blocking=False) if SCAN_MODE == "zoom" else None)
        manip = pipeline.create(dai.node.ImageManip)
        manip.inputConfig.setWaitForMessage(True)
        manip.setMaxOutputFrameSize(model_size[0] * model_size[1] * 3)
        script.outputs["config"].link(manip.inputConfig)
        script.outputs["image"].link(manip.inputImage)

        nn = pipeline.create(ParsingNeuralNetwork).build(manip.out, archive)
        nn.getParser().setConfidenceThreshold(0.25)
        nn.getParser().setIouThreshold(0.5)
        parser_config_queue = nn.getParser().inputConfig.createInputQueue()
        results = pipeline.create(ResultNode).build(
            nn.out, rgbd.pcl, script.outputs["tile"],
            labels, tiles, canvas_size, video_size,
            scene_state, mono_projectors,
        )

        video = color.requestOutput(
            video_size, dai.ImgFrame.Type.NV12, fps=FPS,
            enableUndistortion=True,
        )
        encoder = pipeline.create(dai.node.VideoEncoder)
        encoder.setDefaultProfilePreset(
            FPS, dai.VideoEncoderProperties.Profile.H264_MAIN
        )
        encoder.setMaxOutputFrameSize(video_size[0] * video_size[1] * 3)
        encoder.setBitrateKbps(VIDEO_BITRATE_KBPS)
        video.link(encoder.input)
        viewer.addTopic("Video", encoder.out, "images")
        viewer.addTopic("Tracks and range", results.annotations, "images")
        pipeline.start()
        viewer.registerPipeline(pipeline)
        zoom_control = (ZoomControl(zoom_queue, dai.Buffer,
                        canvas_size, model_size)
                        if zoom_queue is not None else None)
        ir_projector = IRProjectorControl(device)
        try:
            ir_projector.apply({"enabled": True, "intensity": 0.5})
            LOG.info("IR dot projector enabled at 0.50 intensity")
        except RuntimeError as exc:
            LOG.warning("IR dot projector unavailable: %s", exc)
        control_server = start_control_server(
            nn.getParser(), parser_config_queue, dai.DetectionParserConfig,
            scene_state, mono_frames, ir_projector, 8082,
            zoom_control=zoom_control,
        )
        LOG.info(
            "Perception pipeline running: target=%s fps, video=%sx%s, "
            "bitrate=%s kbps, scan=%s, tiles=%s, tile_input=%sx%s, canvas=%sx%s",
            FPS, *video_size, VIDEO_BITRATE_KBPS,
            SCAN_MODE, len(tiles), *model_size, *canvas_size,
        )
        try:
            while pipeline.isRunning():
                viewer.waitKey(1)
        finally:
            control_server.shutdown()
            try:
                ir_projector.apply({"enabled": False})
            except RuntimeError:
                LOG.warning("Could not turn off IR dot projector at shutdown")


if __name__ == "__main__":
    main()
