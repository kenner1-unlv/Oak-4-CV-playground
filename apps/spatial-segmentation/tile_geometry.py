"""Map inference tiles back to the full-frame depth and video coordinates."""

from dataclasses import dataclass

import numpy as np
import cv2


@dataclass(frozen=True)
class Tile:
    x: int
    y: int
    width: int
    height: int


def tiles_for_grid(width: int, height: int, grid_size: int) -> tuple[Tile, ...]:
    if (width <= 0 or height <= 0 or grid_size < 2 or grid_size > 4 or
            width % grid_size or height % grid_size):
        raise ValueError("canvas dimensions must divide into 2–4 grid cells")
    tile_w, tile_h = width // grid_size, height // grid_size
    return tuple(Tile(col * tile_w, row * tile_h, tile_w, tile_h)
                 for row in range(grid_size) for col in range(grid_size))


def quadrants(width: int, height: int) -> tuple[Tile, ...]:
    return tiles_for_grid(width, height, 2)


def paired_crops(
    canvas_size: tuple[int, int], model_size: tuple[int, int],
    scale: float = 1.5,
) -> tuple[Tile, Tile]:
    """Two overlapping left/right landscape crops, centered vertically."""
    if scale not in (1.5, 1.75):
        raise ValueError("paired scale must be 1.5 or 1.75")
    canvas_w, canvas_h = canvas_size
    tile_w, tile_h = (round(model_size[0] * scale),
                      round(model_size[1] * scale))
    if tile_w > canvas_w or tile_h > canvas_h:
        raise ValueError("paired crop exceeds the inference canvas")
    y = (canvas_h - tile_h) // 2
    return (Tile(0, y, tile_w, tile_h),
            Tile(canvas_w - tile_w, y, tile_w, tile_h))


def depth_region_bounds(
    tile: Tile, canvas_size: tuple[int, int], depth_size: tuple[int, int]
) -> tuple[int, int, int, int]:
    canvas_w, canvas_h = canvas_size
    depth_w, depth_h = depth_size
    x0 = round(tile.x * depth_w / canvas_w)
    y0 = round(tile.y * depth_h / canvas_h)
    x1 = round((tile.x + tile.width) * depth_w / canvas_w)
    y1 = round((tile.y + tile.height) * depth_h / canvas_h)
    return x0, y0, x1, y1


def remap_box(
    box: tuple[float, float, float, float],
    tile: Tile,
    canvas_size: tuple[int, int],
) -> tuple[float, float, float, float]:
    canvas_w, canvas_h = canvas_size
    return (
        (tile.x + box[0] * tile.width) / canvas_w,
        (tile.y + box[1] * tile.height) / canvas_h,
        (tile.x + box[2] * tile.width) / canvas_w,
        (tile.y + box[3] * tile.height) / canvas_h,
    )


def mask_and_points_for_tile(
    mask: np.ndarray, points_mm: np.ndarray, tile: Tile,
    canvas_size: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Downsample a tile mask onto its RGB-aligned depth region."""
    depth_h, depth_w = points_mm.shape[:2]
    if mask.ndim != 2 or not mask.size:
        raise ValueError("segmentation mask must be a nonempty 2D image")
    x0, y0, x1, y1 = depth_region_bounds(
        tile, canvas_size, (depth_w, depth_h)
    )
    if x1 <= x0 or y1 <= y0:
        raise ValueError("tile does not cover a depth pixel")
    region = points_mm[y0:y1, x0:x1]
    reduced_mask = cv2.resize(mask.astype(np.float32), (x1 - x0, y1 - y0),
                              interpolation=cv2.INTER_AREA) > 0.08
    return reduced_mask, region
