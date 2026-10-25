"""Project measured RGB-frame 3D target centers into the mono camera views."""

import numpy as np


def project_point(
    xyz_mm: tuple[float, float, float] | None,
    rgb_to_mono: np.ndarray,
    mono_intrinsics: np.ndarray,
    image_size: tuple[int, int],
) -> tuple[float, float] | None:
    """Return normalized mono pixel coordinates, or None outside the image."""
    if xyz_mm is None:
        return None
    point = np.asarray(xyz_mm, dtype=float)
    if point.shape != (3,) or not np.isfinite(point).all():
        return None
    camera_point = rgb_to_mono[:3, :3] @ point + rgb_to_mono[:3, 3]
    if camera_point[2] <= 100:
        return None
    pixel = mono_intrinsics @ camera_point
    width, height = image_size
    u, v = pixel[0] / pixel[2], pixel[1] / pixel[2]
    if not np.isfinite((u, v)).all() or not (0 <= u < width and 0 <= v < height):
        return None
    return round(float(u / width), 4), round(float(v / height), 4)
