import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from perception_core import Observation, SpatialEstimate, TrackManager, estimate_spatial
from tile_geometry import (Tile, mask_and_points_for_tile, quadrants,
                           remap_box, paired_crops, tiles_for_grid)
from hud import rounded_brackets, target_lines


class SpatialTests(unittest.TestCase):
    def test_range_uses_mask_interior_instead_of_background(self) -> None:
        cloud = np.zeros((20, 20, 3), dtype=np.float32)
        cloud[:, :, 2] = 8000
        cloud[5:15, 5:15, 0] = 100
        cloud[5:15, 5:15, 2] = 2000
        mask = np.zeros((20, 20), dtype=np.uint8)
        mask[5:15, 5:15] = 1
        result = estimate_spatial(mask, cloud)
        self.assertEqual(result.xyz_mm, (100.0, 0.0, 2000.0))
        self.assertAlmostEqual(result.range_m, 2.002498, places=5)
        self.assertEqual(result.valid_fraction, 1.0)

    def test_unusable_depth_has_no_range(self) -> None:
        cloud = np.zeros((20, 20, 3), dtype=np.float32)
        mask = np.ones((20, 20), dtype=np.uint8)
        result = estimate_spatial(mask, cloud)
        self.assertIsNone(result.xyz_mm)
        self.assertIsNone(result.range_m)


class TrackingTests(unittest.TestCase):
    def test_cat_dog_flip_keeps_identity_and_stable_label(self) -> None:
        manager = TrackManager()
        spatial = SpatialEstimate((0, 0, 2000), 2.0, 1.0, 0.0)
        labels = []
        ids = []
        for label in ("cat", "dog", "cat", "dog", "cat", "dog", "cat"):
            observation = Observation(label, 0.6, (0.2, 0.2, 0.4, 0.5), spatial, 0)
            track, _ = manager.update([observation])[0]
            ids.append(track.id)
            labels.append(track.label)
        self.assertEqual(set(ids), {1})
        self.assertEqual(labels[2:], ["cat"] * 5)

    def test_sustained_evidence_can_correct_an_initial_label(self) -> None:
        manager = TrackManager()
        spatial = SpatialEstimate((0, 0, 2000), 2.0, 1.0, 0.0)
        labels = []
        for label in (["dog"] * 3) + (["cat"] * 12):
            observation = Observation(label, 0.8, (0.2, 0.2, 0.4, 0.5), spatial, 0)
            track, _ = manager.update([observation])[0]
            labels.append(track.label)
        self.assertEqual(labels[2], "dog")
        self.assertEqual(labels[-1], "cat")

    def test_one_person_across_adjacent_tiles_keeps_one_id(self) -> None:
        manager = TrackManager()
        left = Observation("person", 0.8, (0.35, 0.2, 0.5, 0.45),
                           SpatialEstimate((0, 0, 2000), 2.0, 0.8, 20), 0,
                           tile_index=0)
        right = Observation("person", 0.9, (0.5, 0.2, 0.66, 0.45),
                            SpatialEstimate((100, 0, 2050), 2.05, 0.8, 20), 0,
                            tile_index=1)
        first, _ = manager.update([left])[0]
        second, _ = manager.update([right])[0]
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.bbox, (0.35, 0.2, 0.66, 0.45))
        self.assertEqual(len(second.recent_parts(manager.frame_number)), 2)

    def test_adjacent_tiles_do_not_merge_distant_people(self) -> None:
        manager = TrackManager()
        left = Observation("person", 0.8, (0.35, 0.2, 0.5, 0.45),
                           SpatialEstimate((0, 0, 2000), 2.0, 0.8, 20), 0,
                           tile_index=0)
        right = Observation("person", 0.9, (0.5, 0.2, 0.66, 0.45),
                            SpatialEstimate((100, 0, 5000), 5.0, 0.8, 20), 0,
                            tile_index=1)
        first, _ = manager.update([left])[0]
        second, _ = manager.update([right])[0]
        self.assertNotEqual(first.id, second.id)

    def test_tall_person_merges_across_horizontal_tile_edge(self) -> None:
        manager = TrackManager()
        top = Observation("person", 0.8, (0.35, 0.3, 0.45, 0.5),
                          SpatialEstimate((0, -600, 2000), 2.1, 0.7, 30), 0,
                          tile_index=0)
        bottom = Observation("person", 0.7, (0.35, 0.5, 0.45, 0.85),
                             SpatialEstimate((0, 500, 2100), 2.2, 0.7, 30), 0,
                             tile_index=2)
        first, _ = manager.update([top])[0]
        second, _ = manager.update([bottom])[0]
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.bbox, (0.35, 0.3, 0.45, 0.85))

    def test_existing_head_and_body_tracks_merge_after_depth_recovers(self) -> None:
        manager = TrackManager()
        top = Observation("person", 0.8, (0.35, 0.3, 0.45, 0.5),
                          SpatialEstimate((0, -600, 2000), 2.1, 0.7, 30), 0,
                          tile_index=0)
        body_without_depth = Observation("person", 0.7,
            (0.35, 0.5, 0.45, 0.85),
            SpatialEstimate(None, None, 0.0, None), 0, tile_index=2)
        body_with_depth = Observation("person", 0.7,
            (0.35, 0.5, 0.45, 0.85),
            SpatialEstimate((0, 500, 2100), 2.2, 0.7, 30), 0, tile_index=2)
        head_track, _ = manager.update([top])[0]
        body_track, _ = manager.update([body_without_depth])[0]
        self.assertNotEqual(head_track.id, body_track.id)
        merged, _ = manager.update([body_with_depth])[0]
        self.assertEqual(merged.id, head_track.id)
        self.assertEqual(merged.bbox, (0.35, 0.3, 0.45, 0.85))
        self.assertEqual(len(manager.active()), 1)


class TilingTests(unittest.TestCase):
    def test_full_frame_and_zoom_masks_map_to_same_depth_frame(self) -> None:
        points = np.zeros((352, 640, 3), dtype=np.float32)
        points[:, :, 2] = 2000
        mask = np.ones((352, 640), dtype=np.uint8)
        full = Tile(0, 0, 1280, 704)
        zoom = Tile(320, 176, 640, 352)
        full_mask, full_region = mask_and_points_for_tile(
            mask, points, full, (1280, 704)
        )
        zoom_mask, zoom_region = mask_and_points_for_tile(
            mask, points, zoom, (1280, 704)
        )
        self.assertEqual(full_region.shape, (352, 640, 3))
        self.assertEqual(zoom_region.shape, (176, 320, 3))
        self.assertAlmostEqual(estimate_spatial(full_mask, full_region).range_m, 2)
        self.assertAlmostEqual(estimate_spatial(zoom_mask, zoom_region).range_m, 2)
        self.assertEqual(remap_box((0, 0, 1, 1), zoom, (1280, 704)),
                         (0.25, 0.25, 0.75, 0.75))

    def test_two_wide_overlapping_crops_preserve_model_aspect(self) -> None:
        left, right = paired_crops((1280, 704), (640, 352), 1.5)
        self.assertEqual((left.x, left.y, left.width, left.height),
                         (0, 88, 960, 528))
        self.assertEqual((right.x, right.y, right.width, right.height),
                         (320, 88, 960, 528))
        self.assertEqual(left.width / left.height, 640 / 352)
        self.assertEqual(paired_crops((1280, 704), (640, 352), 1.75)[1].x,
                         160)
        points = np.zeros((352, 640, 3), dtype=np.float32)
        points[:, :, 2] = 2000
        # The NN mask stays 640x352 while the source crop is 960x528.
        mask = np.ones((352, 640), dtype=np.uint8)
        reduced, region = mask_and_points_for_tile(mask, points, right,
                                                    (1280, 704))
        self.assertEqual(region.shape, (264, 480, 3))
        self.assertTrue(reduced.all())
        self.assertAlmostEqual(estimate_spatial(reduced, region).range_m, 2.0)

    def test_two_pass_tracker_holds_between_left_and_right(self) -> None:
        manager = TrackManager(grid_size=2, sweep_frames=2)
        spatial = SpatialEstimate((0, 0, 2000), 2.0, 1.0, 0.0)
        observation = Observation("chair", 0.9, (0.2, 0.4, 0.4, 0.8),
                                  spatial, 0, tile_index=0)
        first, _ = manager.update([observation])[0]
        manager.update([])
        self.assertEqual(manager.active()[0].id, first.id)
        second, _ = manager.update([observation])[0]
        self.assertEqual(second.id, first.id)

    def test_nine_tiles_cover_wide_canvas_and_depth(self) -> None:
        tiles = tiles_for_grid(30, 30, 3)
        self.assertEqual(len(tiles), 9)
        self.assertEqual(tiles[8].x, 20)
        self.assertEqual(tiles[8].y, 20)
        self.assertEqual(remap_box((0, 0, 1, 1), tiles[8], (30, 30)),
                         (2/3, 2/3, 1.0, 1.0))
        points = np.zeros((8, 8, 3), dtype=np.float32)
        points[5:, 5:, 2] = 2500
        mask = np.ones((10, 10), dtype=np.uint8)
        reduced, region = mask_and_points_for_tile(mask, points, tiles[8],
                                                    (30, 30))
        self.assertEqual(region.shape, (3, 3, 3))
        self.assertTrue(reduced.all())
        self.assertTrue(np.all(region[:, :, 2] == 2500))

    def test_nine_tile_sweep_keeps_track_visible_and_joins_seam(self) -> None:
        manager = TrackManager(grid_size=3)
        spatial = SpatialEstimate((0, 0, 2000), 2.0, 1.0, 0.0)
        left = Observation("person", 0.8, (0.25, 0.2, 1/3, 0.45),
                           spatial, 0, tile_index=0)
        right = Observation("person", 0.9, (1/3, 0.2, 0.44, 0.45),
                            spatial, 0, tile_index=1)
        first, _ = manager.update([left])[0]
        second, _ = manager.update([right])[0]
        self.assertEqual(first.id, second.id)
        for _ in range(7):
            manager.update([])
        self.assertEqual(manager.active()[0].missed, 7)
        manager.update([left])
        self.assertEqual(manager.active()[0].id, first.id)

    def test_quadrant_box_maps_to_full_frame(self) -> None:
        tile = quadrants(1280, 704)[3]
        self.assertEqual(
            remap_box((0.0, 0.0, 1.0, 1.0), tile, (1280, 704)),
            (0.5, 0.5, 1.0, 1.0),
        )

    def test_mask_samples_only_matching_depth_quadrant(self) -> None:
        tiles = quadrants(8, 8)
        points = np.zeros((4, 4, 3), dtype=np.float32)
        points[:2, :2, 2] = 1000
        points[2:, 2:, 2] = 4000
        mask = np.ones((4, 4), dtype=np.uint8)
        reduced, region = mask_and_points_for_tile(mask, points, tiles[3], (8, 8))
        self.assertEqual(reduced.shape, (2, 2))
        self.assertTrue(reduced.all())
        self.assertTrue(np.all(region[:, :, 2] == 4000))

    def test_track_remains_visible_between_four_tile_updates(self) -> None:
        manager = TrackManager()
        spatial = SpatialEstimate((0, 0, 2000), 2.0, 1.0, 0.0)
        observation = Observation("cat", 0.8, (0.1, 0.1, 0.2, 0.2), spatial, 0)
        manager.update([observation])
        for expected_missed in (1, 2, 3):
            manager.update([])
            self.assertEqual(manager.active()[0].missed, expected_missed)
        manager.update([observation])
        self.assertEqual(manager.active()[0].id, 1)


class HudTests(unittest.TestCase):
    def test_brackets_curve_inside_box(self) -> None:
        box = (0.2, 0.3, 0.6, 0.8)
        brackets = rounded_brackets(box, (1920, 1056))
        self.assertEqual(len(brackets), 4)
        for bracket in brackets:
            self.assertEqual(len(bracket), 7)
            self.assertTrue(all(box[0] <= x <= box[2] and box[1] <= y <= box[3]
                                for x, y in bracket))
        self.assertGreater(brackets[0][2][1], box[1])

    def test_tag_separates_model_score_and_depth_coverage(self) -> None:
        lines = target_lines(4, "chair", 2.54, 0.92, 0.80,
                             (1224, 515, 2167), True)
        self.assertIn("LOCK 004 / CHAIR / 2.54M", lines[0])
        self.assertIn("NN 92%", lines[1])
        self.assertIn("DEPTH 80%", lines[1])
        self.assertIn("X +1.22M", lines[2])
        compact = target_lines(5, "book", 5.1, 0.6, 0.7,
                               (100, 20, 5100), False)
        self.assertEqual(len(compact), 1)
        self.assertIn("NN 60%", compact[0])


if __name__ == "__main__":
    unittest.main()
