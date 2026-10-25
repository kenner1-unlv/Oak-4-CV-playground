import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mono_projection import project_point


class MonoProjectionTests(unittest.TestCase):
    def test_center_and_stereo_baseline(self):
        intrinsic = np.array([[500, 0, 320], [0, 500, 200], [0, 0, 1]])
        identity = np.eye(4)
        self.assertEqual(project_point((0, 0, 2000), identity, intrinsic,
                                       (640, 400)), (0.5, 0.5))
        shifted = identity.copy()
        shifted[0, 3] = 100  # 100 mm camera translation moves the marker.
        self.assertEqual(project_point((0, 0, 2000), shifted, intrinsic,
                                       (640, 400)), (0.5391, 0.5))

    def test_invalid_or_out_of_frame_depth_has_no_marker(self):
        intrinsic = np.array([[500, 0, 320], [0, 500, 200], [0, 0, 1]])
        identity = np.eye(4)
        self.assertIsNone(project_point(None, identity, intrinsic, (640, 400)))
        self.assertIsNone(project_point((0, 0, 0), identity, intrinsic,
                                        (640, 400)))
        self.assertIsNone(project_point((5000, 0, 1000), identity, intrinsic,
                                        (640, 400)))
