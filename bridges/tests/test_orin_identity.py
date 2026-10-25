import sys
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from orin_identity import IdentityResolver


def observation(track_id, x=0, label="chair"):
    return {"track_id": track_id, "track_state": "tracked", "label": label,
            "bbox_xyxy_norm": [0.2, 0.2, 0.4, 0.5],
            "xyz_mm": [x, 0, 2000]}


def packet(frame_id, *objects):
    return {"schema_version": 1, "frame_id": frame_id,
            "device_timestamp_ns": frame_id * 33_000_000,
            "objects": list(objects)}


class IdentityTests(unittest.TestCase):
    def test_reappearing_camera_track_gets_provisional_global_id(self):
        resolver = IdentityResolver()
        first = resolver.ingest(packet(1, observation(3)), now=100.0)
        resolver.ingest(packet(2), now=100.1)
        later = resolver.ingest(packet(3, observation(8, x=70)), now=101.0)
        self.assertEqual(first["source_to_global"]["3"],
                         later["source_to_global"]["8"])
        self.assertEqual(later["longest_recent"][0]["match_kind"],
                         "provisional_reid")
        self.assertEqual(later["global_count"], 1)
        self.assertEqual(later["reid_events"], 1)
        self.assertEqual(later["recent_reid"][0]["new_camera_track_id"], 8)

    def test_far_return_starts_another_identity(self):
        resolver = IdentityResolver()
        resolver.ingest(packet(1, observation(3)), now=100.0)
        later = resolver.ingest(packet(2, observation(8, x=3000)), now=101.0)
        self.assertEqual(later["global_count"], 2)

    def test_simultaneous_tracks_never_merge(self):
        resolver = IdentityResolver()
        result = resolver.ingest(packet(1, observation(3),
                                        observation(8, x=40)), now=100.0)
        self.assertEqual(result["global_count"], 2)
        self.assertNotEqual(result["source_to_global"]["3"],
                            result["source_to_global"]["8"])

    def test_camera_restart_can_reattach_without_reusing_source_map(self):
        resolver = IdentityResolver()
        resolver.ingest(packet(900, observation(3)), now=100.0)
        later = resolver.ingest(packet(1, observation(1, x=30)), now=100.5)
        self.assertEqual(later["source_to_global"]["1"], 1)
        self.assertEqual(later["global_count"], 1)

    def test_long_camera_restart_requires_strong_geometry(self):
        resolver = IdentityResolver()
        resolver.ingest(packet(900, observation(3)), now=100.0)
        same = resolver.ingest(packet(1, observation(1, x=40)), now=112.0)
        self.assertEqual(same["source_to_global"]["1"], 1)
        resolver.ingest(packet(2), now=112.1)
        different = resolver.ingest(packet(3, observation(8, x=1800)),
                                    now=112.2)
        self.assertEqual(different["global_count"], 2)

    def test_longest_observed_identity_ignores_gap(self):
        resolver = IdentityResolver()
        resolver.ingest(packet(1, observation(3)), now=100.0)
        resolver.ingest(packet(2, observation(3)), now=100.1)
        resolver.ingest(packet(3, observation(3)), now=100.2)
        result = resolver.ingest(packet(4, observation(8, x=3000)), now=101.0)
        self.assertEqual(result["longest_recent"][0]["global_id"], 1)
        self.assertAlmostEqual(result["longest_recent"][0]["observed_seconds"],
                               0.2)

    def test_state_survives_service_restart_without_reusing_camera_ids(self):
        resolver = IdentityResolver()
        resolver.ingest(packet(1, observation(3)), now=100.0)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "identities.json"
            resolver.save(path)
            restored = IdentityResolver()
            restored.load(path)
            self.assertEqual(restored.next_id, 2)
            self.assertEqual(restored.source_to_global, {3: 1})
            result = restored.ingest(packet(2, observation(8, x=20)), now=100.5)
            self.assertEqual(result["source_to_global"]["8"], 1)

    def test_new_identity_requires_repeated_observations(self):
        resolver = IdentityResolver(min_confirmations=3)
        first = resolver.ingest(packet(1, observation(3)), now=100.0)
        second = resolver.ingest(packet(2, observation(3)), now=100.1)
        self.assertEqual(first["global_count"], 0)
        self.assertEqual(second["global_count"], 0)
        third = resolver.ingest(packet(3, observation(3)), now=100.2)
        self.assertEqual(third["source_to_global"]["3"], 1)
        self.assertEqual(third["global_count"], 1)

    def test_new_id_waits_for_continuous_observation_time(self):
        resolver = IdentityResolver(min_confirmations=3,
                                    min_confirmation_s=0.35)
        for frame, now in enumerate((100.0, 100.1, 100.2, 100.3), start=1):
            result = resolver.ingest(packet(frame, observation(3)), now=now)
            self.assertEqual(result["global_count"], 0)
        confirmed = resolver.ingest(packet(5, observation(3)), now=100.4)
        self.assertEqual(confirmed["source_to_global"]["3"], 1)

    def test_same_camera_track_keeps_global_id_after_service_restart(self):
        resolver = IdentityResolver()
        resolver.ingest(packet(900, observation(3)), now=100.0)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "identities.json"
            resolver.save(path)
            restored = IdentityResolver()
            restored.load(path)
            same = restored.ingest(packet(901, observation(3, x=20)), now=100.2)
            self.assertEqual(same["source_to_global"]["3"], 1)
            restarted = restored.ingest(packet(1, observation(1, x=30)),
                                        now=112.0)
            self.assertEqual(restarted["source_to_global"]["1"], 1)


if __name__ == "__main__":
    unittest.main()
