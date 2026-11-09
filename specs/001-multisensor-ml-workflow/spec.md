# Feature Specification: Multisensor ML Workflow

**Feature Branch**: `plan/multisensor-ml-workflow`

**Created**: 2026-11-09

**Status**: Draft

**Input**: Add recording, review, testing, training, model and snapshot inspection, and a dashboard workflow for the OAK 4, Jetson Orin, and Unitree L2 system. Use a staged LEGO board study as the concrete object-recognition benchmark.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record a Reproducible Session (Priority: P1)

As the project operator, I can start a named capture from Training Lab, watch capture health, and stop it with a durable manifest so a real scene can be reviewed and replayed later.

**Why this priority**: Later training and accuracy claims need preserved input evidence.

**Independent Test**: Record a short local scene, stop it, and reopen its manifest with source images, observations, device metadata, and any missing-sample markers.

**Acceptance Scenarios**:

1. **Given** the live viewer is running and recording is off, **when** the operator starts a named session, **then** the page displays recording state, elapsed time, sample counts, dropped samples, storage usage, and synchronization health.
2. **Given** an active session, **when** the operator stops it, **then** a completed manifest identifies the scene, devices, models, calibration, time bounds, source assets, and content integrity references.
3. **Given** a source is unavailable or timestamps do not match, **when** capture continues, **then** the session marks the gap and does not fabricate a synchronized pair.

---

### User Story 2 - Inspect and Correct Evidence (Priority: P2)

As a reviewer, I can browse recordings and OAK model outputs or snapshots, compare RGB, mono, stereo, and L2 evidence, and record class or identity corrections without changing raw capture.

**Why this priority**: Human-reviewed labels and traceable model provenance are required before training or testing.

**Independent Test**: Open one captured track, view available source evidence and model identity, mark a class or identity correction, and confirm the raw record remains intact.

**Acceptance Scenarios**:

1. **Given** a recorded session, **when** a reviewer selects a sample or track, **then** the dashboard shows each available observation with sensor, timestamp, model version, score, and missing/stale status.
2. **Given** an OAK model artifact or prediction snapshot, **when** its provenance is available, **then** the dashboard identifies its version, task, input shape or transform, deployment status, and source recording; unavailable metadata is explicitly unknown.
3. **Given** a reviewer sees an error, **when** they mark same object, different object, wrong class, uncertain, or a split/merge, **then** the correction is attributed and stored separately from raw predictions.

---

### User Story 3 - Run the LEGO Board Benchmark (Priority: P3)

As an experimenter, I can record a repeatable LEGO board scene, annotate the actual pieces, and measure piece count, color, size or footprint, and separation before increasing scene difficulty.

**Why this priority**: A concrete, reviewable benchmark makes detector training and comparison meaningful beyond an attractive live overlay.

**Independent Test**: Run a fixture with about 20 mixed-color, mixed-size pieces shaken flat on a board, with no touching or overlap, and produce a per-piece and aggregate result report against human labels.

**Acceptance Scenarios**:

1. **Given** a baseline board scene of roughly 20 pieces, **when** it is captured, **then** the session records actual count, color and size/footprint labels, board and camera setup, lighting, and confirmation that pieces are flat, separate, non-touching, and non-overlapping.
2. **Given** the same pieces in different in-plane orientations, **when** outputs are evaluated, **then** count, color, size/footprint, and separation are scored independently of orientation; orientation-specific failures remain visible.
3. **Given** a completed baseline, **when** the operator creates harder stages, **then** each stage records which variable changed, such as more pieces, smaller gaps, touching, overlap/occlusion, or lighting, and reports metrics separately rather than pooling unmarked stages.

---

### User Story 4 - Train and Evaluate Candidates (Priority: P4)

As an experimenter, I can prepare nonleaking train, validation, and held-out test sets, train a supervised custom LEGO instance model on reviewed RGB images off-device, evaluate it against a baseline, and separately evaluate an Orin-side identity candidate before considering live use.

**Why this priority**: The project becomes an ML workflow only when it can measure a candidate against reviewed evidence and a baseline.

**Independent Test**: On a small local fixture with known labels, freeze a split, run a detector candidate and an identity candidate through their relevant evaluations, and reproduce each comparison report.

**Acceptance Scenarios**:

1. **Given** reviewed sessions, **when** an experimenter creates a split, **then** whole scene/session groups are assigned to one partition and the held-out test membership is frozen before candidate tuning.
2. **Given** a candidate and baseline, **when** both are evaluated on the same frozen examples, **then** the dashboard reports relevant LEGO detection/count/color/size/separation measures or identity switches/merges/fragmentation/recovery, with per-stage and per-scene breakdowns.
3. **Given** a candidate that has only replay results, **when** its record is opened, **then** its status remains experimental; no training result is shown as a live or deployed result.

---

### User Story 5 - Compare Calibrated L2 and Stereo (Priority: P5)

As an operator, I can inspect Unitree L2 alongside camera evidence and, once calibration and reference measurements exist, compare distance estimates with explicit uncertainty.

**Why this priority**: The L2 extends the project beyond the OAK, but current sampled points are unaligned and cannot be treated as ground truth.

**Independent Test**: View an uncalibrated recording with a clear warning; then use a fixture with a calibration record and known target distances to produce an error report.

**Acceptance Scenarios**:

1. **Given** no valid camera-to-L2 calibration, **when** L2 points are displayed, **then** they remain a separate unaligned preview without projected labels or fused accuracy claims.
2. **Given** a calibration and synchronized known-distance scene, **when** the comparison is run, **then** the report states transform and timing provenance, range error, missing measurements, and uncertainty by target or surface.
3. **Given** a LEGO board scene without measured per-piece L2 coverage, **when** its results are reviewed, **then** L2 is reported only as board-plane or scene context, without claiming it resolves individual pieces.

### Edge Cases

- Capture starts with insufficient storage or loses storage mid-session: show an actionable error, stop cleanly, and preserve readable data already written.
- The OAK, Orin, or L2 restarts or its clock changes: record a source discontinuity; never silently connect samples across it.
- Recording is interrupted without a normal stop: mark the session incomplete and permit safe inspection or recovery.
- An artifact path exists but its hash or model metadata differs: display a provenance failure and exclude it from trusted evaluation.
- A model's output classes, input transform, or calibration differ between snapshots: show the difference and prevent a misleading direct comparison.
- A reviewer changes an earlier correction: preserve correction history and active revision.
- Training competes with live inference: queue or pause training when measured resource limits are exceeded and display the reason.
- A held-out test scene is accidentally selected for training: reject the run before it starts.
- An L2 cloud is stale or sparse: display source age and point count, and omit unsupported fused measurements.
- LEGO pieces touch or overlap in a nominal baseline: mark the scene as a harder stage or invalid baseline; do not use it to claim separated-piece performance.
- A piece color changes under lighting or a reflective surface: retain the human label and report the ambiguity instead of silently assigning a confident color.
- Exact LEGO part identity is unknown: permit a size/footprint category and avoid fabricating a part ID.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST keep the current live Vision Lab and identity view available while optional Training Lab capabilities are added.
- **FR-002**: The operator MUST explicitly start and stop a named recording session; recording MUST default to off.
- **FR-003**: Each session MUST preserve source imagery or reviewable crops, model observations, available L2 samples, timestamps, source identifiers, camera and sensor configuration, calibration identifiers, and model identifiers needed to replay and inspect the evidence.
- **FR-004**: Capture MUST report elapsed time, counts by source, dropped or unmatched samples, storage usage, and synchronization status, and MUST mark incomplete sessions.
- **FR-005**: Capture manifests MUST identify immutable source assets by integrity reference and keep raw evidence distinct from predictions, human corrections, and later derived datasets.
- **FR-006**: The dashboard MUST list recordings, model artifacts, and prediction snapshots with known provenance and explicitly mark missing metadata or unavailable assets.
- **FR-007**: The dashboard MUST compare available RGB, left mono, right mono, stereo, Orin identity, and L2 evidence on a shared timeline while preserving each source's own timestamp and missing/stale state.
- **FR-008**: Reviewers MUST be able to record same-object, different-object, wrong-class, uncertain, and identity split/merge corrections, with attribution and revision history.
- **FR-009**: The system MUST create versioned train, validation, and test manifests that keep a scene or recording group entirely within one split and freeze the held-out test membership before tuning.
- **FR-010**: Experiment records MUST identify dataset manifest, candidate and baseline versions, configuration, run status, results, and whether evidence came from replay, shadow mode, or live deployment.
- **FR-011**: Evaluation MUST compare candidate and baseline on the same examples and report relevant identity, class, range, timing, and failure-case metrics with denominators and per-scene breakdowns. The workflow MUST accept candidates from separate feature work without requiring a new fusion algorithm in this feature.
- **FR-012**: Training MUST be an explicit separate action from capture, evaluation, and deployment, and MUST preserve the live model and a rollback candidate.
- **FR-013**: Resource contention MUST be measured before concurrent Orin training is enabled; a run exceeding configured live-service limits MUST be queued, paused, or rejected with a visible reason.
- **FR-014**: The system MUST not project camera labels onto L2 points or report stereo-versus-L2 accuracy without a valid spatial transform, time-alignment evidence, and a known-distance reference scene.
- **FR-015**: The dashboard MUST distinguish implemented actions and measured results from planned features, placeholders, and unverified device behavior.
- **FR-016**: The benchmark MUST support a baseline of approximately 20 shaken-flat, non-touching, non-overlapping LEGO pieces of mixed colors and sizes, recording the actual count and setup for each run.
- **FR-017**: Human-reviewed LEGO ground truth MUST include each visible instance, count, color category, size/footprint category, and separation state; exact commercial part ID MUST be optional until a verified taxonomy exists.
- **FR-018**: Evaluation MUST report LEGO count error, per-instance detection or mask quality, color and size/footprint results, and split/merge or touching errors, with metrics separated by challenge stage and orientation where relevant.
- **FR-019**: The operator MUST be able to define progressive challenge stages that change piece count, gap, touching, overlap/occlusion, or lighting, and each result MUST identify the stage and changed conditions.
- **FR-020**: The workflow MUST support supervised training and held-out testing of a custom LEGO instance detection or segmentation candidate using human-reviewed RGB evidence, separately from Orin-side identity candidates. Training MUST occur away from the live OAK device; conversion and deployment to OAK hardware require separate measured gates and owner approval.
- **FR-021**: A per-piece L2 claim MUST require measured point density or coverage at the piece scale, valid calibration, time alignment, and reference measurements. Until then, L2 MAY provide only board-plane or scene context.
- **FR-022**: Shareable findings MUST state scene and stage, ground-truth method, model/configuration versions, dataset and evaluation provenance, metrics with denominators, and limits without including raw captures or trained weights in Git.

### Key Entities

- **Recording Session**: Named scene capture with operator notes, source roster, time bounds, state, storage and sync health, and manifest.
- **Observation**: Timestamped source evidence, sensor and model identity, prediction or measurement, input transform, and availability state.
- **Source Asset**: Reviewable image/crop, depth sample, or L2 sample with immutable identity and integrity reference.
- **Model Artifact / Snapshot**: Versioned model or output snapshot with task, input contract, provenance, and deployment state.
- **Correction**: Attributed and versioned human judgment linked to raw observations or tracks.
- **Dataset Split**: Frozen membership of grouped scenes/sessions in train, validation, and test partitions.
- **Experiment Run**: Candidate, baseline, split, configuration, execution mode, measurements, and failure details.
- **Calibration Record**: Camera-to-L2 transform and timing evidence with validity bounds and reference measurements.
- **LEGO Board Scene**: Actual piece inventory/count, human-reviewed per-piece color and footprint labels, board layout, orientation, spacing/contact state, lighting, and stage.
- **Benchmark Finding**: Git-safe summary of a frozen evaluation with model and dataset provenance, denominators, stage breakdown, and observed limits.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can start, stop, and reopen a 5-minute session from Training Lab; 100% of saved samples identify their source and capture time, and every detected gap is visible.
- **SC-002**: A reviewer can find a session, inspect a track's source evidence, and save a correction in under 3 minutes during a guided usability check.
- **SC-003**: On a fixed local fixture, two evaluations of the same candidate and frozen split produce identical sample membership and metric totals.
- **SC-004**: A fixture with adjacent frames from one scene is rejected if it would place that scene in more than one dataset partition.
- **SC-005**: In an uncalibrated L2 session, 100% of displayed L2 views identify the data as unaligned and zero camera-to-L2 accuracy values are shown.
- **SC-006**: Each candidate comparison identifies its baseline, dataset size, per-scene outcomes, and execution mode, enabling a reviewer to decide whether a candidate is ready for further live testing.
- **SC-007**: A baseline fixture containing about 20 physically separate pieces produces an auditable per-piece record and reports count error plus color, size/footprint, and separation outcomes; rotating pieces in-plane does not change the ground-truth identities or evaluation rules.
- **SC-008**: At least two staged LEGO fixtures with different difficulty settings produce separate result summaries that identify the changed condition and preserve denominators.
- **SC-009**: No report claims per-piece L2 detection until measured point coverage, calibration, alignment, and reference-distance checks are attached to that claim.

## Assumptions

- The initial user is a local project operator/reviewer; multiuser account and remote sharing workflows are outside this increment.
- The existing Training Lab and Vision Lab page remains the user entry point. The Orin is the durable local capture and experiment host; the OAK continues its real-time camera pipeline.
- Initial ML work includes supervised custom LEGO instance detection/segmentation from reviewed RGB images and Orin-side object association/class evidence as distinct candidate paths. Reinforcement learning and automatic live promotion are later experiments with separate gates.
- Existing [cross-camera identity fusion issue #2](https://github.com/kenner1-unlv/Oak-4-CV-playground/issues/2) owns fusion behavior. This feature supplies capture, review, dataset, and evaluation infrastructure for it. Existing [dense-scene benchmark issue #1](https://github.com/kenner1-unlv/Oak-4-CV-playground/issues/1) owns that benchmark; its labeled scenes may become fixtures here.
- Existing model configuration files and captured prediction records are the first inspectable model/snapshot sources. The feature does not assume an existing complete OAK model registry or historical training archive.
- L2 remains an independent sampled preview until measured calibration and synchronized reference scenes are available.
- L2 may contribute board-plane or scene context before any per-piece evaluation. Whether it returns enough points on individual LEGO pieces is an empirical question, not an assumed capability.
- The baseline starts with roughly 20 pieces shaken flat and manually separated so pieces neither touch nor overlap; the exact count is recorded. Orientation does not define a different class. Progressively harder scenes are labeled by condition.
- Recordings and trained weights remain outside Git; the repository contains code, schemas, fixtures, manifests or summaries safe to share, and reproducible instructions.
- Success criteria for local fixtures can be verified without devices. Live throughput, capture integrity, training contention, and calibrated accuracy require later tests on the actual OAK, Orin, and L2.
