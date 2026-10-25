"""Mask-based spatial estimates and class-agnostic track label persistence."""

from dataclasses import dataclass, field
from math import dist, sqrt

import numpy as np


@dataclass(frozen=True)
class SpatialEstimate:
    xyz_mm: tuple[float, float, float] | None
    range_m: float | None
    valid_fraction: float
    spread_mm: float | None


def estimate_spatial(mask: np.ndarray, points_mm: np.ndarray) -> SpatialEstimate:
    """Use interior instance pixels only; leave range unknown for poor depth."""
    if mask.ndim != 2 or points_mm.shape != (*mask.shape, 3):
        raise ValueError("mask and organized point cloud must have the same shape")
    interior = mask.astype(bool).copy()
    if min(interior.shape) >= 3:
        core = interior[1:-1, 1:-1]
        for row in (-1, 0, 1):
            for col in (-1, 0, 1):
                core &= mask[1 + row : interior.shape[0] - 1 + row,
                             1 + col : interior.shape[1] - 1 + col].astype(bool)
        interior[0, :] = False
        interior[-1, :] = False
        interior[:, 0] = False
        interior[:, -1] = False
    total = int(interior.sum())
    if total == 0:
        return SpatialEstimate(None, None, 0.0, None)
    samples = points_mm[interior]
    good = np.isfinite(samples).all(axis=1) & (samples[:, 2] >= 100) & (
        samples[:, 2] <= 20000
    )
    valid = samples[good]
    fraction = float(len(valid) / total)
    if len(valid) < 10 or fraction < 0.1:
        return SpatialEstimate(None, None, fraction, None)
    median = np.median(valid, axis=0)
    z_spread = float(np.median(np.abs(valid[:, 2] - median[2])))
    xyz = tuple(float(value) for value in median)
    return SpatialEstimate(xyz, sqrt(sum(value * value for value in xyz)) / 1000,
                           fraction, z_spread)


@dataclass(frozen=True)
class Observation:
    label: str
    score: float
    bbox: tuple[float, float, float, float]
    spatial: SpatialEstimate
    mask_index: int
    mask_outline: tuple[tuple[float, float], ...] = ()
    tile_index: int = -1


@dataclass
class Track:
    id: int
    bbox: tuple[float, float, float, float]
    xyz_mm: tuple[float, float, float] | None
    label: str | None = None
    evidence: dict[str, float] = field(default_factory=dict)
    observations: int = 0
    missed: int = 0
    last_observation: Observation | None = None
    tile_observations: dict[int, tuple[int, Observation]] = field(default_factory=dict)

    def recent_parts(self, frame_number: int, max_age: int = 3) -> list[Observation]:
        return [observation for seen, observation in self.tile_observations.values()
                if frame_number - seen <= max_age]


def _iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def _union_box(parts: list[Observation]) -> tuple[float, float, float, float]:
    return (
        min(part.bbox[0] for part in parts),
        min(part.bbox[1] for part in parts),
        max(part.bbox[2] for part in parts),
        max(part.bbox[3] for part in parts),
    )


def _touches_shared_tile_edge(
    a: tuple[float, ...], b: tuple[float, ...],
    old_tile: int, new_tile: int, grid_size: int = 2,
) -> bool:
    old_row, old_col = divmod(old_tile, grid_size)
    new_row, new_col = divmod(new_tile, grid_size)
    if old_row == new_row and abs(old_col - new_col) == 1:
        boundary = max(old_col, new_col) / grid_size
        left, right = (a, b) if old_col < new_col else (b, a)
        return (left[2] >= boundary - 0.03 and
                right[0] <= boundary + 0.03 and
                min(a[3], b[3]) - max(a[1], b[1]) >= -0.03)
    if old_col == new_col and abs(old_row - new_row) == 1:
        boundary = max(old_row, new_row) / grid_size
        top, bottom = (a, b) if old_row < new_row else (b, a)
        return (top[3] >= boundary - 0.03 and
                bottom[1] <= boundary + 0.03 and
                min(a[2], b[2]) - max(a[0], b[0]) >= -0.03)
    return False


class TrackManager:
    """Associate boxes across frames without requiring the class to match."""

    def __init__(self, grid_size: int = 2,
                 sweep_frames: int | None = None) -> None:
        if grid_size not in (2, 3, 4):
            raise ValueError("grid_size must be 2, 3, or 4")
        self.grid_size = grid_size
        self.sweep_frames = sweep_frames or grid_size * grid_size
        if self.sweep_frames < 1:
            raise ValueError("sweep_frames must be at least 1")
        self.part_max_age = max(4, self.sweep_frames)
        self.hold_frames = max(3, self.sweep_frames - 1)
        self._tracks: dict[int, Track] = {}
        self._next_id = 1
        self._frame_number = 0

    def _merge_person_fragments(
        self, result: list[tuple[Track, Observation]]
    ) -> list[tuple[Track, Observation]]:
        """Join separate person IDs only at an adjacent tile edge in 3D."""
        while True:
            merged = False
            ids = sorted(self._tracks)
            for first_index, first_id in enumerate(ids):
                first = self._tracks[first_id]
                if (first.last_observation is None or
                    first.last_observation.label != "person" or
                    first.xyz_mm is None or
                    first.missed >= self.sweep_frames):
                    continue
                for second_id in ids[first_index + 1:]:
                    second = self._tracks[second_id]
                    if (second.last_observation is None or
                        second.last_observation.label != "person" or
                        second.xyz_mm is None or
                        second.missed >= self.sweep_frames or
                        set(first.tile_observations) &
                        set(second.tile_observations) or
                        dist(first.xyz_mm, second.xyz_mm) > 1500):
                        continue
                    if not any(
                        _touches_shared_tile_edge(
                            part_a.bbox, part_b.bbox, tile_a, tile_b,
                            self.grid_size,
                        )
                        for tile_a, (seen_a, part_a) in first.tile_observations.items()
                        for tile_b, (seen_b, part_b) in second.tile_observations.items()
                        if (self._frame_number - seen_a <= self.part_max_age and
                            self._frame_number - seen_b <= self.part_max_age)
                    ):
                        continue
                    second_is_newer = second.missed < first.missed
                    first.tile_observations.update(second.tile_observations)
                    parts = first.recent_parts(
                        self._frame_number, max_age=self.part_max_age
                    )
                    first.bbox = _union_box(parts)
                    first.missed = min(first.missed, second.missed)
                    first.observations += second.observations
                    for label, score in second.evidence.items():
                        first.evidence[label] = first.evidence.get(label, 0) + score
                    if second_is_newer:
                        first.last_observation = second.last_observation
                        first.xyz_mm = second.xyz_mm
                    del self._tracks[second_id]
                    result = [(first if track.id == second_id else track, obs)
                              for track, obs in result]
                    merged = True
                    break
                if merged:
                    break
            if not merged:
                return result

    def update(self, observations: list[Observation]) -> list[tuple[Track, Observation]]:
        self._frame_number += 1
        for track in self._tracks.values():
            track.missed += 1
            for tile_id, (seen, _) in list(track.tile_observations.items()):
                if self._frame_number - seen > self.part_max_age:
                    del track.tile_observations[tile_id]
            parts = track.recent_parts(
                self._frame_number, max_age=self.part_max_age
            )
            if parts:
                track.bbox = _union_box(parts)
        candidates: list[tuple[float, int, int]] = []
        for track in self._tracks.values():
            for index, observation in enumerate(observations):
                overlap = _iou(track.bbox, observation.bbox)
                if overlap < 0.15:
                    previous = track.last_observation
                    if (previous is None or
                        previous.label != observation.label or
                        track.xyz_mm is None or
                        observation.spatial.xyz_mm is None or
                        dist(track.xyz_mm, observation.spatial.xyz_mm) > (
                            1500 if observation.label == "person" else 900
                        ) or
                        not any(
                            _touches_shared_tile_edge(
                                part.bbox, observation.bbox,
                                old_tile, observation.tile_index,
                                self.grid_size,
                            )
                            for old_tile, (_, part) in track.tile_observations.items()
                        )):
                        continue
                    overlap = 0.16
                if track.xyz_mm is not None and observation.spatial.xyz_mm is not None:
                    if dist(track.xyz_mm, observation.spatial.xyz_mm) > 2000:
                        continue
                candidates.append((overlap, track.id, index))
        matched_tracks: set[int] = set()
        matched_observations: set[int] = set()
        assignments: dict[int, Track] = {}
        for _, track_id, index in sorted(candidates, reverse=True):
            if track_id in matched_tracks or index in matched_observations:
                continue
            assignments[index] = self._tracks[track_id]
            matched_tracks.add(track_id)
            matched_observations.add(index)
        result: list[tuple[Track, Observation]] = []
        for index, observation in enumerate(observations):
            track = assignments.get(index)
            if track is None:
                track = Track(self._next_id, observation.bbox,
                              observation.spatial.xyz_mm)
                self._tracks[track.id] = track
                self._next_id += 1
            track.bbox = observation.bbox
            track.xyz_mm = observation.spatial.xyz_mm or track.xyz_mm
            track.last_observation = observation
            track.tile_observations[observation.tile_index] = (
                self._frame_number, observation
            )
            parts = track.recent_parts(
                self._frame_number, max_age=self.part_max_age
            )
            track.bbox = _union_box(parts)
            track.missed = 0
            track.observations += 1
            for label in list(track.evidence):
                track.evidence[label] *= 0.9
            track.evidence[observation.label] = (
                track.evidence.get(observation.label, 0.0) + observation.score
            )
            best = max(track.evidence, key=track.evidence.get)
            if track.label is None:
                if track.observations >= 3 or observation.label not in {"cat", "dog"}:
                    track.label = best
            elif best != track.label and (
                track.evidence[best] > 1.5 * track.evidence.get(track.label, 0.0)
                and track.observations >= 3
            ):
                track.label = best
            result.append((track, observation))
        for track_id in list(self._tracks):
            if self._tracks[track_id].missed > max(10, 2 * self.sweep_frames + 2):
                del self._tracks[track_id]
        return self._merge_person_fragments(result)

    def active(self, max_missed: int | None = None) -> list[Track]:
        """Keep a tile's last observation visible until its next sweep."""
        if max_missed is None:
            max_missed = self.hold_frames
        return [track for track in self._tracks.values()
                if track.last_observation is not None and track.missed <= max_missed]

    @property
    def frame_number(self) -> int:
        return self._frame_number
