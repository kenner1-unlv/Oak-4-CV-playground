"""Recent mono feature tracks for the Spatial experiment."""

import threading
import time


class FeatureState:
    def __init__(self, max_points=160):
        self._lock = threading.Lock()
        self._latest = {}
        self.max_points = max_points

    def publish(self, camera, timestamp_ns, features, image_size):
        width, height = image_size
        points = []
        for feature in features:
            if len(points) >= self.max_points:
                break
            points.append([
                int(feature.id), round(float(feature.position.x) / width, 4),
                round(float(feature.position.y) / height, 4),
            ])
        with self._lock:
            self._latest[camera] = {
                "timestamp_ns": timestamp_ns,
                "received_at": time.monotonic(),
                "count": len(features),
                "points": points,
            }

    def read(self):
        with self._lock:
            latest = dict(self._latest)
        now = time.monotonic()
        return {
            camera: {
                "device_timestamp_ns": item["timestamp_ns"],
                "count": item["count"],
                "age_ms": round((now - item["received_at"]) * 1000),
                "points": item["points"],
            }
            for camera, item in latest.items()
            if now - item["received_at"] < 1.0
        }
