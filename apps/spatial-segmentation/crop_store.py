"""Low-rate RGB frames for timestamped, on-demand object crops."""

import math
import threading
import time

import cv2
import numpy as np


class RgbCropStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._latest = None

    def publish(self, frame, device_timestamp_ns):
        with self._lock:
            self._latest = (np.asarray(frame).copy(), int(device_timestamp_ns),
                            time.monotonic())

    def jpeg(self, bbox, scene_timestamp_ns, max_skew_ns=250_000_000):
        if (not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or
            any(isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) for value in bbox)):
            return None
        x0, y0, x1, y1 = bbox
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            return None
        with self._lock:
            saved = self._latest
        if saved is None:
            return None
        frame, timestamp_ns, received_at = saved
        if (time.monotonic() - received_at > 0.5 or
                abs(timestamp_ns - int(scene_timestamp_ns)) > max_skew_ns):
            return None
        height, width = frame.shape[:2]
        left, top = int(x0 * width), int(y0 * height)
        right, bottom = min(width, math.ceil(x1 * width)), \
                        min(height, math.ceil(y1 * height))
        if right - left < 8 or bottom - top < 8:
            return None
        crop = frame[top:bottom, left:right]
        scale = min(1.0, 512 / max(crop.shape[:2]))
        if scale < 1:
            crop = cv2.resize(crop, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode('.jpg', crop,
                                   [cv2.IMWRITE_JPEG_QUALITY, 85])
        return (encoded.tobytes(), timestamp_ns) if ok else None
