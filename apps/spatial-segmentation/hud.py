"""Pixel-aware targeting brackets and compact, honest target statistics."""

from math import cos, pi, sin


def rounded_brackets(
    box: tuple[float, float, float, float],
    frame_size: tuple[int, int],
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Return four rounded L-shaped polylines in normalized image coordinates."""
    x0, y0, x1, y1 = box
    frame_w, frame_h = frame_size
    short_side_px = min((x1 - x0) * frame_w, (y1 - y0) * frame_h)
    length_px = min(40.0, max(6.0, short_side_px * 0.30),
                    short_side_px * 0.45)
    radius_px = min(12.0, length_px * 0.40)
    length_x, length_y = length_px / frame_w, length_px / frame_h
    radius_x, radius_y = radius_px / frame_w, radius_px / frame_h
    result = []
    for x, y, sx, sy in (
        (x0, y0, 1, 1), (x1, y0, -1, 1),
        (x0, y1, 1, -1), (x1, y1, -1, -1),
    ):
        arc = tuple(
            (x + sx * radius_x * (1 - sin(theta)),
             y + sy * radius_y * (1 - cos(theta)))
            for theta in (0, pi / 8, pi / 4, 3 * pi / 8, pi / 2)
        )
        result.append(
            ((x + sx * length_x, y), *arc, (x, y + sy * length_y))
        )
    return tuple(result)


def target_lines(
    track_id: int,
    label: str,
    range_m: float | None,
    detector_score: float,
    depth_valid_fraction: float,
    xyz_mm: tuple[float, float, float] | None,
    wide_tag: bool,
) -> tuple[str, ...]:
    locked = range_m is not None and label not in {"animal", "object"}
    state = "LOCK" if locked else "SCAN"
    distance = f"{range_m:.2f}M" if range_m is not None else "RANGE --"
    title = f"{state} {track_id:03d} / {label.upper()[:14]} / {distance}"
    nn = round(detector_score * 100)
    depth = round(depth_valid_fraction * 100)
    if xyz_mm is None:
        if not wide_tag:
            return (f"{title}  NN {nn}%  D {depth}%",)
        return (title, f"NN {nn}%  DEPTH {depth}%  XYZ --")
    x, y, z = (value / 1000 for value in xyz_mm)
    if wide_tag:
        return (
            title,
            f"NN {nn}%  DEPTH {depth}%  Z {z:.2f}M",
            f"X {x:+.2f}M   Y {y:+.2f}M",
        )
    return (f"{title}  NN {nn}%",)
