# Implementation Plan: Multisensor ML Workflow

**Branch**: `plan/multisensor-ml-workflow` | **Date**: 2026-11-09 | **Spec**: [spec.md](spec.md)

## Summary

Extend House V Training Lab with opt-in Orin recording, source and model provenance, review corrections, frozen dataset splits, and repeatable Orin-side candidate evaluation. The OAK retains live RGB/mono/stereo inference. Unitree L2 remains an independent uncalibrated source until measured spatial and temporal alignment plus known-distance references permit comparison. The first physical benchmark is a staged LEGO board with a non-touching, non-overlapping 20-piece baseline and later harder arrangements. Existing [cross-camera fusion issue #2](https://github.com/kenner1-unlv/Oak-4-CV-playground/issues/2) and [dense-scene benchmark issue #1](https://github.com/kenner1-unlv/Oak-4-CV-playground/issues/1) remain separate work.

## Technical Context

**Language/Version**: Python 3.12 in OAK app; Orin Python 3 with ROS 2 Humble for L2; plain JavaScript in House V. Pin actual Orin interpreter and dependencies in implementation.

**Primary Dependencies**: Existing DepthAI 3.11, depthai-nodes 0.7, NumPy 2.2, OpenCV 4.10 on OAK; `rclpy` and `sensor_msgs` on Orin. Start durable service with Python standard-library HTTP, SQLite, and file IO; choose a training framework only for a measured candidate.

**Storage**: Configurable Orin-local root (default under `/data/oak4`) with immutable hashed source assets, session manifests, SQLite query index, and append-only correction history. Captures, weights, and private scenes remain outside Git.

**Testing**: Existing Python tests in `bridges/tests/` and `apps/spatial-segmentation/tests/`; add synthetic contract, crash-recovery, split-leakage, and deterministic evaluation fixtures; separate hardware verification.

**Target Platform**: OAK 4 D Pro RVC4 app, Jetson AGX Orin Linux, Unitree L2 ROS 2 `/unilidar/cloud`, browser on existing House V port 8082. Addresses are configuration.

**Project Type**: Multi-process edge CV/ML system with OAK app, Orin services, and browser dashboard.

**Performance Goals**: Preserve existing live RGB 30 result passes/s target; report actual capture rates, queue depth, drops, skew, and Orin load. No new throughput claim until physical measurement.

**Constraints**: Recording defaults off; bounded queues and storage quota; no inferred sync after restart; immutable raw assets; frozen test set; no camera-to-L2 fusion claim before calibration; no automatic candidate promotion.

**Scale/Scope**: One local operator, one OAK, one Orin, one L2 initially. Version formats for later expansion.

## Constitution Check

*Gate checked before research and again after design against the proposed constitution.*

| Principle | Design response | Gate |
| --- | --- | --- |
| Measured claims | Dashboard distinguishes live, replay, shadow, deployed, and unknown. Metrics retain denominators and provenance. | Pass |
| Preserve raw evidence | Immutable hashed assets; raw observations, corrections, predictions, and labels have distinct records. | Pass |
| Live operation stays safe | Bounded optional capture, training resource gate, shadow candidates, explicit later promotion and rollback. | Pass |
| Sensors independent until calibrated | Per-source and receipt times plus availability; L2 unaligned until spatial, timing, and reference gates. | Pass |
| Reproducible evaluation | Grouped frozen splits; baseline/candidate on identical examples; deterministic fixture checks. | Pass |
| Delivery constraints | Capture root outside Git; no credentials or private recordings in commits. | Pass |

**Post-design recheck**: The contracts and entities enforce all gates. No exception is requested. Unknown hardware resource limits and clock offsets block concurrency and sensor-fusion claims, respectively, until measured.

## Project Structure

### Documentation (this feature)

```text
specs/001-multisensor-ml-workflow/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── capture-api.md
│   └── records.md
└── tasks.md
```

### Source Code (proposed changes)

```text
apps/spatial-segmentation/
├── main.py                 # Existing OAK inference; opt-in tagged capture source
├── model_controls.py       # Existing same-origin House V proxy
├── housev.js               # Existing Training Lab panels
└── tests/
bridges/
├── orin_identity.py        # Existing provisional identity feed
├── l2_cloud_relay.py       # Existing sampled L2 preview
├── capture_service.py      # New Orin session control, ingestion, catalog API
├── capture_store.py        # New immutable assets, index, recovery
├── review_store.py         # New correction history
├── experiment.py           # New split, replay, candidate comparison
├── calibration.py          # New L2 transform and reference gate
└── tests/
```

**Structure decision**: Extend the deployed paths rather than create another viewer or move real-time inference to Orin. New files are proposed ownership boundaries, not existing code. The actual image transfer path from OAK must be measured during capture implementation; current UDP results contain metadata only. Existing mono JPEG endpoints have no source timestamp headers, and separate scene, identity, and L2 HTTP polls are non-atomic. Capture must add source frame identity and times at ingestion and store independent receipt times, observed skew, and unknown clock offset. It must not claim these existing polls are synchronized.

## Delivery Sequence

1. **Inventory and contracts**: Detect current OAK model YAMLs and installed app metadata without assuming historical weights. Specify observation, asset, session, and API versions. Measure image transfer cost; identify source timestamps and clock domains.
2. **Capture MVP**: Add explicit image/crop and observation ingestion on Orin with bounded queues, quota, hashes, atomic manifest finalization, discontinuity markers, and incomplete-session recovery. Preserve live viewer and identity feed.
3. **Review and catalog**: Add read-only session/model/snapshot browser and source timeline. Corrections are attributed, append-only, and revisable. Show missing/stale/unknown states.
4. **LEGO baseline**: Version a 20-piece inventory and board setup. Shake pieces flat, enforce no touching or overlap, vary orientation, and record independent count, color, size, and instance labels. Repeat with controlled seeds/scenes before adding contact, occlusion, dense piles, and motion challenge levels. Report counts and error denominators, per-piece metrics, orientation sensitivity, and range availability. Do not label a model trained on generic COCO classes as a verified LEGO size/color detector.
5. **Dataset and ML evaluation**: Freeze scene/session-grouped train, validation, and test memberships. Export human-reviewed RGB images and instance labels to train a supervised LEGO detector/segmenter on Orin or workstation. Compare count, localization, color, size, and orientation robustness with the frozen baseline on identical replay. In parallel, train or load an Orin association candidate and compare it with the existing identity baseline on the same recorded tracks. Expose both model families and per-scene metrics. Keep OAK RVC4 conversion/deployment behind a later gate.
6. **L2 range study**: Capture sampled clouds with ROS stamps, receipt times, and point counts. Start with independent board-plane and scene range context. Measure rigid transform, clock offset/skew, known-distance references, and point density at the board before comparing stereo error. Per-piece L2 association requires demonstrated spatial resolution; do not assume individual LEGO pieces are resolved.
7. **Physical acceptance**: Validate five-minute capture and browser states on named hardware; record RGB/mono rates, drops, storage, thermal/resource contention, and rollback behavior. Fixture tests do not substitute for these checks.

## Integration and Risk Decisions

- Existing version-1 UDP result records and `/api/scene`, `/api/identities`, `/api/lidar` remain available. Independent mono version-2 observations are tracked under issue #2. Capture accepts versioned records and marks absent sources honestly.
- OAK package model YAMLs are not a training registry. Catalog records artifact identity, source, input transform, and installed state only when verified; unavailable fields stay unknown.
- Session/scene group IDs are split units; freeze membership hash before tuning and reject train/test overlap.
- OAK device, ROS, and Orin clocks are separate domains. Preserve original and receive times and a measured alignment record; reject timestamp-only cross-source joins when offset is unknown.
- Keep recordings, private imagery, and trained weights in Orin data root; commit small synthetic fixtures, code, taxonomy, and findings only.

## Complexity Tracking

No constitution violations. Separate Orin storage, review, experiment, and calibration modules reflect required provenance and safety boundaries.
