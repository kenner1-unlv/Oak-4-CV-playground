"""Map four high-detail inference quadrants back to full-frame depth/video."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Tile:
    x: int
    y: int
    width: int
    height: int


def quadrants(width: int, height: int) -> tuple[Tile, Tile, Tile, Tile]:
    if width <= 0 or height <= 0 or width % 2 or height % 2:
        raise ValueError("the inference canvas must have positive even dimensions")
    half_w, half_h = width // 2, height // 2
    return (
        Tile(0, 0, half_w, half_h),
        Tile(half_w, 0, half_w, half_h),
        Tile(0, half_h, half_w, half_h),
        Tile(half_w, half_h, half_w, half_h),
    )


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
    """Downsample a tile mask onto the corresponding full-frame depth region."""
    canvas_w, canvas_h = canvas_size
    depth_h, depth_w = points_mm.shape[:2]
    if canvas_w != 2 * depth_w or canvas_h != 2 * depth_h:
        raise ValueError("canvas and organized point cloud must have 2:1 scale")
    if mask.shape != (tile.height, tile.width):
        raise ValueError("mask shape does not match inference tile")
    if any(value % 2 for value in (tile.x, tile.y, tile.width, tile.height)):
        raise ValueError("tile bounds must align to depth pixels")
    x0, y0 = tile.x // 2, tile.y // 2
    w, h = tile.width // 2, tile.height // 2
    region = points_mm[y0 : y0 + h, x0 : x0 + w]
    reduced_mask = mask.astype(bool).reshape(h, 2, w, 2).any(axis=(1, 3))
    return reduced_mask, region
