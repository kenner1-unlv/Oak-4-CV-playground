import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mono_evidence import MonoDetectionStore, match_projected_tracks


class MonoEvidenceTests(unittest.TestCase):
    def test_one_to_one_match_preserves_independent_labels(self):
        frame = {"timestamp_ns": 100, "detections": [
            {"label": "chair", "score": 0.7,
             "bbox_xyxy_norm": [0.4, 0.4, 0.6, 0.6]},
        ]}
        tracks = [(1, {"left": (0.49, 0.5)}),
                  (2, {"left": (0.51, 0.5)})]
        result = match_projected_tracks(tracks, {"left": frame})
        self.assertEqual(sum("left" in item for item in result.values()), 1)
        self.assertEqual(result[1]["left"]["label"], "chair")

    def test_missing_or_outside_is_unknown(self):
        store = MonoDetectionStore()
        store.publish("left", 1_000_000_000, [])
        self.assertEqual(store.near(1_500_000_000), {})
        result = match_projected_tracks(
            [(7, {"left": (0.1, 0.1), "right": (0.5, 0.5)})],
            {"left": {"timestamp_ns": 1, "detections": [
                {"label": "cat", "score": 0.8,
                 "bbox_xyxy_norm": [0.7, 0.7, 0.9, 0.9]},
            ]}},
        )
        self.assertEqual(result[7], {})


if __name__ == "__main__":
    unittest.main()
