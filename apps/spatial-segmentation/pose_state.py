"""Bounded-rate scheduling, status, and overlay data for human pose inference."""

import math
import threading
import time


MODEL = "luxonis/lite-hrnet:18-coco-192x256"
POSE_SIZE = (192, 256)
PERSON_LABEL = "person"


def valid_box(box):
    return (
        isinstance(box, (list, tuple)) and len(box) == 4 and
        all(isinstance(value, (int, float)) and math.isfinite(value)
            for value in box) and
        0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1
    )


def padded_pose_box(box, padding=0.1, target_aspect=POSE_SIZE[0] / POSE_SIZE[1]):
    """Expand a normalized person box to include context and pose input ratio."""
    x0, y0, x1, y1 = map(float, box)
    width, height = x1 - x0, y1 - y0
    x0 -= width * padding
    x1 += width * padding
    y0 -= height * padding
    y1 += height * padding
    width, height = x1 - x0, y1 - y0
    if width / height < target_aspect:
        extra = (height * target_aspect - width) / 2
        x0 -= extra
        x1 += extra
    else:
        extra = (width / target_aspect - height) / 2
        y0 -= extra
        y1 += extra
    return [max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1)]


def remap_keypoints(points, crop_box):
    """Map HRNet crop-normalized points back to full-frame coordinates."""
    x0, y0, x1, y1 = crop_box
    output = []
    for point in points:
        x, y, confidence = point
        if not all(math.isfinite(value) for value in (x, y, confidence)):
            continue
        output.append([
            min(1.0, max(0.0, x0 + x * (x1 - x0))),
            min(1.0, max(0.0, y0 + y * (y1 - y0))),
            min(1.0, max(0.0, confidence)),
        ])
    return output


class PoseState:
    """Keep one bounded-rate person crop in flight and skeletons by track."""

    def __init__(self, enabled=False, max_per_second=20,
                 resample_seconds=0.05, stale_seconds=0.35,
                 skeleton_edges=()):
        if max_per_second < 1:
            raise ValueError("max_per_second must be at least one")
        self.lock = threading.Lock()
        self.interval_ns = int(1e9 / max_per_second)
        self.resample_ns = int(resample_seconds * 1e9)
        self.stale_ns = int(stale_seconds * 1e9)
        self.skeleton_edges = tuple(tuple(int(index) for index in edge)
                                    for edge in skeleton_edges)
        self.last_dispatch_ns = 0
        self.last_by_track = {}
        self.pending = {}
        self.next_sequence = 1
        self.sent = 0
        self.completed = 0
        self.errors = 0
        self.latest_by_track = {}
        self.requested = bool(enabled)
        self.training = False

    @property
    def enabled(self):
        return self.requested and not self.training

    def set_training(self, training):
        with self.lock:
            self.training = bool(training)

    def apply(self, payload):
        if (not isinstance(payload, dict) or set(payload) != {"enabled"} or
                not isinstance(payload["enabled"], bool)):
            raise ValueError("enabled must be true or false")
        with self.lock:
            self.requested = payload["enabled"]
            return self._report_locked()

    def select(self, scene, frame_timestamp_ns):
        if (scene.get("age_ms") is None or scene["age_ms"] > 250 or
                scene.get("device_timestamp_ns") is None or
                abs(frame_timestamp_ns - scene["device_timestamp_ns"]) > 250_000_000):
            return None
        with self.lock:
            now_ns = time.monotonic_ns()
            for sequence, item in list(self.pending.items()):
                if now_ns - item["sent_at_ns"] > 2_000_000_000:
                    del self.pending[sequence]
                    self.errors += 1
            if (not self.enabled or self.pending or
                    now_ns - self.last_dispatch_ns < self.interval_ns):
                return None
            choices = []
            for obj in scene.get("objects", []):
                box = obj.get("bbox_xyxy_norm")
                track_id = obj.get("track_id")
                if (obj.get("track_state") != "tracked" or
                        (obj.get("label") or obj.get("detector_label", "")).lower()
                        != PERSON_LABEL or not isinstance(track_id, int) or
                        not valid_box(box) or obj.get("detector_score", 0) < 0.3):
                    continue
                area = (box[2] - box[0]) * (box[3] - box[1])
                if area < 0.003:
                    continue
                last = self.last_by_track.get(track_id, 0)
                if now_ns - last < self.resample_ns:
                    continue
                choices.append((last, -area, obj))
            if not choices:
                return None
            _, _, obj = min(choices, key=lambda item: (item[0], item[1]))
            sequence = self.next_sequence
            self.next_sequence += 1
            item = {
                "track_id": obj["track_id"],
                "bbox_xyxy_norm": list(obj["bbox_xyxy_norm"]),
                "crop_box_xyxy_norm": padded_pose_box(obj["bbox_xyxy_norm"]),
                "frame_id": scene.get("frame_id"),
                "device_timestamp_ns": frame_timestamp_ns,
                "sent_at_ns": now_ns,
            }
            self.pending[sequence] = item
            self.last_by_track[obj["track_id"]] = now_ns
            self.last_dispatch_ns = now_ns
            self.sent += 1
            return sequence, item

    def complete(self, sequence, message):
        try:
            points = []
            for keypoint in message.getKeypoints():
                xy = keypoint.imageCoordinates
                points.append((float(xy.x), float(xy.y),
                               float(keypoint.confidence)))
        except (AttributeError, TypeError, ValueError) as exc:
            self.fail(sequence)
            raise ValueError("invalid HRNet keypoint output") from exc
        with self.lock:
            item = self.pending.pop(sequence, None)
            if item is None:
                self.errors += 1
                return None
            full_frame_points = remap_keypoints(points,
                                               item["crop_box_xyxy_norm"])
            self.completed += 1
            pose = {
                "track_id": item["track_id"],
                "frame_id": item["frame_id"],
                "device_timestamp_ns": item["device_timestamp_ns"],
                "latency_ms": round((time.monotonic_ns() -
                                     item["sent_at_ns"]) / 1e6),
                "keypoints": full_frame_points,
            }
            self.latest_by_track[item["track_id"]] = pose
            return pose

    def fail(self, sequence):
        with self.lock:
            self.pending.pop(sequence, None)
            self.errors += 1

    def overlays(self, frame_timestamp_ns):
        with self.lock:
            return [
                pose.copy() for pose in self.latest_by_track.values()
                if 0 <= frame_timestamp_ns - pose["device_timestamp_ns"]
                <= self.stale_ns
            ]

    def read(self):
        with self.lock:
            return self._report_locked()

    def _report_locked(self):
        latest = max(self.latest_by_track.values(),
                     key=lambda pose: pose["device_timestamp_ns"],
                     default=None)
        return {
            "enabled": self.enabled,
            "requested": self.requested,
            "training": self.training,
            "model": MODEL,
            "skeleton_edges": self.skeleton_edges,
            "max_per_second": round(1e9 / self.interval_ns),
            "sent": self.sent,
            "completed": self.completed,
            "errors": self.errors,
            "pending": len(self.pending),
            "latest": latest,
        }
