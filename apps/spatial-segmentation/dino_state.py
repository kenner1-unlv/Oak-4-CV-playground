"""Bounded scheduling and provenance for on-camera DINOv3 crop embeddings."""

import math
import threading
import time

import numpy as np


MODEL = "luxonis/dinov3-backbone:vit-small-384x288"


def pooled_embedding(tensor):
    """Pool dense channel features into a unit vector for crop comparison."""
    array = np.asarray(tensor, dtype=np.float32)
    if array.ndim != 4 or array.shape[0] != 1 or array.shape[1] != 384:
        raise ValueError(f"unexpected DINOv3 tensor shape: {array.shape}")
    vector = array.mean(axis=(0, 2, 3))
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(vector).all() or not math.isfinite(norm) or norm < 1e-8:
        raise ValueError("invalid DINOv3 embedding")
    return (vector / norm).tolist()


class DinoState:
    def __init__(self, max_per_second=3, resample_seconds=1.5):
        self.lock = threading.Lock()
        self.interval_ns = int(1e9 / max_per_second)
        self.resample_ns = int(resample_seconds * 1e9)
        self.last_dispatch_ns = 0
        self.last_by_track = {}
        self.pending = {}
        self.next_sequence = 1
        self.sent = 0
        self.completed = 0
        self.errors = 0
        self.latest = None
        self.enabled = True

    def set_enabled(self, enabled):
        with self.lock:
            self.enabled = bool(enabled)

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
                bbox = obj.get("bbox_xyxy_norm")
                track_id = obj.get("track_id")
                if (obj.get("track_state") != "tracked" or
                    not isinstance(track_id, int) or
                    not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or
                    any(not isinstance(value, (int, float)) or
                        not math.isfinite(value) for value in bbox) or
                    not (0 <= bbox[0] < bbox[2] <= 1 and
                         0 <= bbox[1] < bbox[3] <= 1)):
                    continue
                area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                if area < 0.003 or obj.get("detector_score", 0) < 0.3:
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
            item = {"track_id": obj["track_id"], "label": obj.get("label"),
                    "bbox_xyxy_norm": list(obj["bbox_xyxy_norm"]),
                    "frame_id": scene.get("frame_id"),
                    "device_timestamp_ns": frame_timestamp_ns,
                    "sent_at_ns": now_ns}
            self.pending[sequence] = item
            self.last_by_track[obj["track_id"]] = now_ns
            self.last_dispatch_ns = now_ns
            self.sent += 1
            return sequence, item

    def complete(self, sequence, tensor):
        vector = pooled_embedding(tensor)
        with self.lock:
            item = self.pending.pop(sequence, None)
            if item is None:
                self.errors += 1
                return None
            self.completed += 1
            self.latest = {"track_id": item["track_id"],
                           "frame_id": item["frame_id"],
                           "device_timestamp_ns": item["device_timestamp_ns"],
                           "latency_ms": round((time.monotonic_ns() -
                                                item["sent_at_ns"]) / 1e6),
                           "dimension": len(vector)}
            return {"schema_version": 1, "kind": "appearance_embedding",
                    "model": MODEL, "sequence": sequence,
                    "track_id": item["track_id"], "label": item["label"],
                    "frame_id": item["frame_id"],
                    "device_timestamp_ns": item["device_timestamp_ns"],
                    "embedding": [round(value, 6) for value in vector]}

    def fail(self, sequence):
        with self.lock:
            self.pending.pop(sequence, None)
            self.errors += 1

    def report(self):
        with self.lock:
            return {"enabled": self.enabled, "model": MODEL, "sent": self.sent,
                    "completed": self.completed, "errors": self.errors,
                    "pending": len(self.pending), "latest": self.latest}
