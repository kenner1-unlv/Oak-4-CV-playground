# Data Model

The Orin owns durable records. IDs are opaque UUIDs or content hashes. Every serialized record has `schema_version`; timestamps carry a named clock domain. Paths are relative to a configured data root and never accepted from browser input as arbitrary filesystem paths.

## RecordingSession

| Field | Meaning |
| --- | --- |
| `session_id`, `name`, `scene_group_id` | Stable identity, human label, and split grouping key |
| `state` | `recording`, `complete`, `incomplete` |
| `started_at_utc`, `ended_at_utc` | Orin control times; end may be absent after crash |
| `operator_note`, `benchmark_id`, `challenge_level` | Scene context, including LEGO protocol when used |
| `sources` | OAK cameras, identity service, L2, their hardware/config identifiers |
| `model_ids`, `calibration_ids`, `package_id` | Versions known at capture start and any transitions |
| `counts`, `bytes_written`, `dropped`, `unmatched`, `sync_state` | Health, by source; `sync_state` may be `offset_unknown` |
| `manifest_hash`, `failure_reason` | Final integrity and incomplete reason |

**Transition**: `recording -> complete` only after all queued writes and manifest finalization; `recording -> incomplete` on crash, storage failure, or source discontinuity that prevents continuation. A new session follows a restart rather than silently appending to the old one.

## SourceAsset

| Field | Meaning |
| --- | --- |
| `asset_id`, `sha256`, `byte_length`, `media_type`, `relative_path` | Immutable asset identity and integrity |
| `session_id`, `source_id`, `frame_sequence` | Provenance and optional frame association |
| `source_timestamp_ns`, `clock_domain`, `received_at_ns` | Original source and Orin receipt time; neither substitutes for the other |
| `calibration_id`, `image_transform_id` | Geometry and image preprocessing, when relevant |
| `availability` | `present`, `dropped`, `missing`, `stale`, `unmatched`, `corrupt` |

Assets may be RGB/mono source images or reviewable crops, depth samples, sampled L2 clouds, or other explicitly typed media. A missing/dropped marker has no file path or hash and records a reason. A hash mismatch makes an asset untrusted for evaluation.

## Observation

Timestamped model or sensor output linked to a source frame or asset. Fields: `observation_id`, `session_id`, `source_id`, `sensor_kind`, `frame_sequence`, `source_timestamp_ns`, `clock_domain`, `received_at_ns`, `model_id` (nullable for raw L2), `calibration_id`, `input_transform_id`, `inference_status`, `availability`, `raw_score` and `score_semantics`, class ID/label, box/mask or measured geometry, local track ID, provisional Orin global ID, and `asset_ids`. Missing and stale observations remain explicit records. A model score, DINO cosine similarity, and depth quality metric are different semantics and cannot be averaged as one confidence.

## ModelArtifact and PredictionSnapshot

`ModelArtifact`: `model_id`, name, task (`segmentation`, `mono_detection`, `appearance`, `pose`, `association`, etc.), source reference, artifact SHA-256 if local, framework/format, input dimensions and transform, label taxonomy version, training dataset/run, conversion record, compatible target, and status (`referenced`, `available`, `candidate`, `installed`, `unknown`). Installed status requires device/package evidence.

`PredictionSnapshot`: `snapshot_id`, model ID, session/observation IDs, creation time, inference configuration, output asset/hash, and execution mode (`captured_live`, `replay`, `shadow`). A snapshot is output evidence, not the model weights.

## Correction

Fields: `correction_id`, `target_observation_ids` or track IDs, `session_id`, `kind` (`same_object`, `different_object`, `wrong_class`, `uncertain`, `split`, `merge`), corrected class/identity when applicable, `author`, `created_at_utc`, `reason`, `supersedes_id`, and `active_revision`. Append a new correction to revise an older one; never mutate raw observations or delete revision history. An uncertain mark is not forced into a positive or negative training label.

## BenchmarkScene and PieceTruth

`BenchmarkScene`: `benchmark_id`, protocol version, scene group ID, board dimensions/reference image, camera pose/distance, lighting, shake procedure, challenge level (`separated_flat`, `increased_count`, `narrow_gap`, `touching`, `overlap`, `occlusion`, `lighting_change`, `motion`), changed condition and its measured value, piece inventory hash, layout seed or repetition number, and eligibility result. The baseline requires approximately 20 known pieces flat on the board, no contact or overlap after shaking; invalid layouts are labeled and excluded from the baseline rather than silently corrected.

`PieceTruth`: stable piece instance ID, scene ID, color category, size category and physical dimensions/stud count, visible polygon or box, orientation, occlusion/contact flags, and independent annotation provenance. Count is derived from eligible truth instances. Orientation variants of the same scene stay in one split group. Per-piece detection, class, color, and size metrics retain counts and denominators.

`BenchmarkFinding`: Git-safe summary ID, frozen report hash, protocol/stage, changed conditions, ground-truth method, dataset/split hashes, model and configuration IDs, metric numerators/denominators, per-stage and orientation breakdown, observed limitations, and verification level (`fixture`, `physical`). It contains no raw capture or model weights.

## DatasetSplit

Fields: `split_id`, version, creation time, grouping rule (`scene_group_id` or whole session), sorted train/validation/test group IDs, source manifest hashes, truth/correction revision, frozen test membership SHA-256, taxonomy version, eligibility/exclusion reasons, and status (`draft`, `frozen`). Reject a group in more than one partition. Once frozen, membership cannot change; create a new version instead.

## ExperimentRun

Fields: `run_id`, task, candidate model/artifact ID, baseline ID, split ID/hash, code revision, configuration hash, execution mode (`train`, `replay`, `shadow`, `deployed`), state (`queued`, `running`, `paused`, `complete`, `failed`), resource measurements, start/end times, metrics with numerator/denominator and scene breakdowns, report hash, failure reason. Training output never changes `installed` state without a separate deployment record and owner approval.

## CalibrationRecord

Fields: `calibration_id`, OAK and L2 hardware IDs/frame IDs, rigid transform with units and coordinate convention, method and reference target IDs, measurement residuals/uncertainty, valid pose/time range, OAK-to-Orin and ROS-to-Orin clock alignment estimates and drift, L2 point density at target distance, and validation status. `preview_only` allows visualization. `validated_scene_range` permits board/scene comparisons. `validated_piece_resolution` is required before per-piece L2 association. Stale or different mount/calibration versions invalidate prior associations.

## Integrity and relationships

- One session owns many assets and observations; observations reference immutable assets and model/calibration versions.
- Corrections reference observations/tracks but never replace them. A derived label set names an exact correction revision.
- Split manifests reference sessions/scenes and truth versions; runs reference exact frozen splits and model versions.
- A report is reproducible from hashes of source manifest, split, labels, candidate, baseline, configuration, and code revision.
- L2 observation association remains absent until the relevant calibration state is valid. Unknown clock offset or sparse returns prohibit fused range metrics.
