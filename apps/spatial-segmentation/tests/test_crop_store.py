import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crop_store import RgbCropStore


class CropStoreTests(unittest.TestCase):
    def test_current_box_returns_only_selected_region(self):
        store = RgbCropStore()
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        frame[:, 100:] = 255
        store.publish(frame, 1_000_000_000)
        result = store.jpeg([0.5, 0, 1, 1], 1_000_000_000)
        self.assertIsNotNone(result)
        encoded, timestamp = result
        crop = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8),
                            cv2.IMREAD_COLOR)
        self.assertEqual(timestamp, 1_000_000_000)
        self.assertEqual(crop.shape[:2], (100, 100))
        self.assertGreater(float(crop.mean()), 245)

    def test_invalid_or_stale_crop_is_unavailable(self):
        store = RgbCropStore()
        store.publish(np.zeros((100, 100, 3), dtype=np.uint8), 1_000_000_000)
        for box in ([0, 0, 0, 1], [-0.1, 0, 1, 1], [0, 0, 1.1, 1],
                    [0, 0, 0.01, 0.01]):
            self.assertIsNone(store.jpeg(box, 1_000_000_000))
        self.assertIsNone(store.jpeg([0, 0, 1, 1], 2_000_000_000))


if __name__ == "__main__":
    unittest.main()
