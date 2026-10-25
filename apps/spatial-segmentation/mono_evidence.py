"""Timestamped mono detections and conservative RGB-track evidence matching."""

import threading
import time


class MonoDetectionStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._latest = {}

    def publish(self, camera, timestamp_ns, detections):
        with self._lock:
            self._latest[camera] = {
                "timestamp_ns": timestamp_ns,
                "received_at": time.monotonic(),
                "detections": detections,
            }

    def near(self, timestamp_ns, tolerance_ns=180_000_000):
        with self._lock:
            latest = dict(self._latest)
        return {
            camera: item for camera, item in latest.items()
            if abs(item["timestamp_ns"] - timestamp_ns) <= tolerance_ns
            and time.monotonic() - item["received_at"] < 0.7
        }


def match_projected_tracks(tracks, frames, margin=0.035):
    """One-to-one match of projected RGB centers to mono model boxes.

    tracks contains (track_id, {camera: normalized_point}). A missing match
    is unknown, never evidence that a class is absent.
    """
    result = {track_id: {} for track_id, _ in tracks}
    for camera in ("left", "right"):
        frame = frames.get(camera)
        if frame is None:
            continue
        candidates = []
        for track_id, markers in tracks:
            point = markers.get(camera)
            if point is None:
                continue
            px, py = point
            for index, detection in enumerate(frame["detections"]):
                x0, y0, x1, y1 = detection["bbox_xyxy_norm"]
                if x0 - margin <= px <= x1 + margin and y0 - margin <= py <= y1 + margin:
                    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                    candidates.append(((px - cx) ** 2 + (py - cy) ** 2,
                                       track_id, index))
        used_tracks, used_detections = set(), set()
        for _, track_id, index in sorted(candidates):
            if track_id in used_tracks or index in used_detections:
                continue
            used_tracks.add(track_id)
            used_detections.add(index)
            result[track_id][camera] = {
                **frame["detections"][index],
                "timestamp_ns": frame["timestamp_ns"],
            }
    return result
