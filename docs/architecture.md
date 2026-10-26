# Pipeline architecture

The OAK 4 D Pro runs the model and stereo pipeline. The Orin builds/installs
the app and optionally consumes metadata; it does not process browser video.
One camera app provides several switchable browser views.

```mermaid
flowchart LR
  RGB[RGB camera] --> Video[2560×1408 H.264]
  RGB --> Canvas[1280×704 inference canvas]
  Canvas --> Resize[Downscale full scene to 640×352]
  Resize --> NN[YOLOv8 Large segmentation]
  Mono[Left + right mono] --> Stereo[Stereo depth]
  Mono --> Jpeg[On-demand grayscale JPEGs]
  Stereo --> Align[Align depth to RGB]
  NN --> Join[Timestamp-matched results]
  Align --> Join
  Join --> Spatial[Mask-interior XYZ and range]
  Spatial --> Tracks[Short-term IDs and label evidence]
  Tracks --> Overlay[Browser annotations + scene JSON]
  Tracks --> UDP[Compact UDP JSON to Orin]
  Video -->|Color view only| Viewer[Browser page]
  Jpeg -->|Selected mono view only| Viewer
  Overlay --> Viewer
```

The source is in [spatial-segmentation](../apps/spatial-segmentation/). The
current baseline makes one full-scene model pass per camera frame;
the earlier v0.5.2 baseline rotated four quadrant crops. The parser emits a
mask, box, class, and score for each instance. The ResultNode pairs those
outputs with an organized RGB-aligned point cloud and tile ID. It samples
valid 3D points inside a shrunken mask, then uses a robust median for X/Y/Z
and range. The in-memory tracker associates detections across frames and
accumulates class evidence before changing a displayed label.

The browser page on port 8082 proxies the color Visualizer, which uses a
WebSocket on port 8765. Confidence and IoU sliders send
`DetectionParserConfig` messages to the native parser's input queue. IoU here
controls **model non-maxima suppression**; it does not change the tracker's
separate association threshold. The control values are process state, so they
reset when the app restarts.
One House V page switches Vision Lab and Training Lab in place. It creates
the color Visualizer only while Color video is selected in a visible tab.
Changing the lab panel keeps that viewer connection. Hidden tabs release it,
and the reconnect control can recreate only the iframe when its image feed
stalls while scene JSON stays live. Detections only removes the iframe and
polls scene JSON to draw
distance-colored reticles and faint masks on a dark canvas. The encoder stays
active in the camera graph
for fast switching, but H.264 is no longer delivered to that browser.
Color, Mono, and Targets Only can each share the main box with the spatial
canvas. The PiP control swaps pane sizes without rebuilding the color iframe
or its WebSocket. Targets Only still disconnects the iframe entirely. The
spatial canvas returns to the target panel when it is not paired with a view.
Left/right mono views request JPEGs on demand and can show or hide projected
3D target-center markers. They do not reuse the color masks because the
cameras have different optical centers, fields of view, and image geometry.
The calibration transforms RGB-frame XYZ into each mono camera frame before
projection. Markers with invalid depth or outside the mono image are omitted.
The built-in IR dot projector is commanded to 0.50 intensity at startup and
can be adjusted live independently of the display mode.

## Streams and browser delivery

| Data path | Purpose | Leaves the camera? |
| --- | --- | --- |
| RGB inference canvas → one tile → YOLO | Classes, boxes, instance masks | No raw tile frames |
| RGB color + left/right mono → stereo/RGBD | Align depth and measure mask-interior 3D points | No raw depth or point cloud |
| RGB NV12 → H.264 encoder | 2560×1408 color video | Delivered only while Color video view is selected |
| Annotation topic | Stock color-aligned masks, brackets, labels, range | Available to the native Visualizer; House V draws its own scene-based reticles |
| Left/right mono JPEGs | Grayscale diagnostic camera views | Only the selected mono frame is JPEG-encoded on request |
| Scene JSON | Boxes, mask outlines, IDs, range, projected mono target centers | Polled by House V in Color, Detections only, and mono views |
| UDP result records | Compact detection/track metadata | Yes, to the Orin when configured |

The YOLO COCO classes do not produce wall geometry. A green depth-edge
prototype was tried and rejected because stereo noise yielded unhelpful room
lines. Accurate wall geometry and calibrated lidar fusion remain future work.

## Unitree L2 preview path

The Orin's Unitree ROS 2 node publishes `/unilidar/cloud` and `/unilidar/imu`.
The [browser relay](../bridges/README.md) samples every second cloud point and
serves the latest scan to the camera app's `/api/lidar` proxy. The browser
draws cyan dots over Color and Detections only. In the overhead panel, it
retains ground-plane cells with returns at three or more height bands to
suppress broad floor and ceiling planes, then colors those likely vertical
returns by horizontal distance. This is a heuristic, not plane segmentation.
The target reticles use OAK camera-relative range: red through 1.25 m,
transitioning through orange, yellow, and green to cyan at 8 m or farther.
The target index places tracked objects first, nearest to farthest; held and
unknown-range records follow. These visual ranges are not yet transformed to
the robot base frame.
The spatial map labels target dots by object class; track and global IDs remain
in the target index.
This is an approximate, uncalibrated projection with an assumed mount
orientation and field of view. The L2 points are not associated with masks,
assigned object labels, or included in the camera's UDP result records.

## Result record

When `ORIN_RESULT_HOST` is set, the app sends one UDP JSON datagram per model
pass to `ORIN_RESULT_HOST:8766` (override the port with `ORIN_RESULT_PORT`).
An example shape, with illustrative values:

```json
{
  "schema_version": 1,
  "frame_id": 1234,
  "tile_id": 2,
  "device_timestamp_ns": 123456789,
  "objects": [
    {
      "track_id": 7,
      "label": "chair",
      "detector_label": "chair",
      "detector_score": 0.92,
      "alternate_label": "couch",
      "alternate_evidence_share": 0.18,
      "bbox_xyxy_norm": [0.25, 0.5, 0.45, 0.9],
      "xyz_mm": [120, 20, 1850],
      "range_m": 1.854,
      "depth_valid_fraction": 0.8,
      "depth_spread_mm": 45,
      "track_state": "tracked",
      "age_frames": 0,
      "tile_parts": 1
    }
  ]
}
```

`xyz_mm` and `range_m` are `null` when depth is insufficient. `detector_score`
is a class/model score; `depth_valid_fraction` and `depth_spread_mm` describe
depth sampling quality. `track_state` is `tracked` for a direct observation
in the current pass and `held` for a recent track displayed between passes.
The alternate class fields are `null` unless the same YOLO model has produced
another class for that track over time. The evidence share is a decayed vote
fraction, not a second model probability.
An independent Orin identity service listens on UDP 8766, assigns provisional
global IDs from camera-frame 3D proximity, image overlap, class, and elapsed
time, and serves its current mapping on HTTP 8771. It persists compact state
under `/data/oak4` so service restarts do not reset global numbering. House V
proxies that feed and can show the two longest-observed recent IDs; the second
model column is an explicit placeholder. Geometry-only matching can falsely
merge lookalike objects, so it is not yet a verified re-identification system.
The UDP record contains boxes and measurements, **not** image frames or mask
pixels. Color masks are visualized through the browser annotation topic or
outline coordinates in the detection-only HTTP scene record. Mono HTTP scene
records add projected center markers, without changing the UDP contract.

## Performance and limitations

At a 30 FPS video target, the current baseline executes 30 full-scene model
passes/s. The app does not record video. A live 120-frame check measured 30.2
result passes/s with range measurements. The 2560×1408 browser stream ran at
30 FPS network/decode/render in an earlier same-resolution candidate. These
numbers do not measure end-to-end latency or inference accuracy; see the
[resolution comparison](resolution-experiment.md).

The tracker holds identities through short gaps but has no appearance model
for re-identification after long occlusion. A segmentation mask can be wrong
even when its model score is high. Stereo distance can be missing or biased
by texture, reflectivity, calibration, and occlusion. The
[experiment plan](experiments.md) is intended to measure those failure modes.
