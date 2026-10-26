import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dino_state import DinoState, pooled_embedding


class DinoStateTests(unittest.TestCase):
    def test_select_and_pool_preserve_track_provenance(self):
        state = DinoState(max_per_second=30)
        scene = {"age_ms": 20, "frame_id": 7,
                 "device_timestamp_ns": 1_000_000_000,
                 "objects": [{"track_id": 11, "label": "chair",
                              "track_state": "tracked", "detector_score": 0.8,
                              "bbox_xyxy_norm": [0.1, 0.2, 0.5, 0.8]}]}
        selected = state.select(scene, 1_030_000_000)
        self.assertIsNotNone(selected)
        sequence, metadata = selected
        self.assertEqual(metadata["track_id"], 11)
        self.assertIsNone(state.select(scene, 1_040_000_000))
        tensor = np.zeros((1, 384, 18, 24), dtype=np.float32)
        tensor[0, 0] = 2
        tensor[0, 1] = 2
        result = state.complete(sequence, tensor)
        self.assertEqual(result["track_id"], 11)
        self.assertEqual(result["frame_id"], 7)
        self.assertAlmostEqual(result["embedding"][0], 2 ** -0.5,
                               places=5)
        self.assertEqual(state.report()["completed"], 1)

    def test_rejects_malformed_features_and_stale_scene(self):
        with self.assertRaises(ValueError):
            pooled_embedding(np.zeros((1, 384, 18, 24)))
        state = DinoState()
        self.assertIsNone(state.select({"age_ms": 300,
                                        "device_timestamp_ns": 1,
                                        "objects": []}, 1))


if __name__ == "__main__":
    unittest.main()
