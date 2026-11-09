# Oak 4 CV Playground Constitution

**Status**: Proposed project principles for this feature; subject to maintainer review.

## Core Principles

### I. Measured Claims

Distinguish a live observation, a recorded benchmark, a simulated replay, and a planned capability. Model predictions, provisional object IDs, and an uncalibrated LiDAR preview are never labeled ground truth. Every performance or accuracy claim cites its dataset, method, hardware, and limits.

### II. Preserve Raw Evidence

Raw captured evidence, human corrections, derived labels, model outputs, and evaluation results retain separate provenance. Capture manifests identify sensor, model, calibration, time, and immutable content. A later model run cannot overwrite the original evidence or a held-out test set.

### III. Live Operation Stays Safe

Recording is opt-in. The live OAK view and current Orin identity path remain usable while the training workflow is introduced. Training and model promotion are distinct from capture and review; candidate models run in replay or shadow mode until measured gates are met. Preserve a rollback path for any live-model change.

### IV. Treat Sensors Independently Until Calibrated

RGB, left mono, right mono, stereo depth, and Unitree L2 observations carry source and time. Missing or stale sensor data remains missing or stale. LiDAR points cannot inherit camera labels or support distance-accuracy claims without measured spatial calibration, time alignment, and labeled reference scenes.

### V. Reproducible Evaluation

For each experiment, record task, scene and session identifiers, hardware and model versions, configuration, dataset split, baseline, metrics, and known gaps. Split by session or scene to prevent adjacent-frame leakage. Freeze the held-out test split before tuning and compare candidates on the same examples. Progressively harder LEGO board stages must identify the changed condition; color, count, size, and separation claims require human-reviewed labels and stated denominators.

## Delivery Constraints

Keep large recordings, private scene content, training artifacts, and device credentials out of Git. Record code, object taxonomy, Git-safe findings, provenance, and reproducible instructions in the repository. Treat local tests, replay, and physical-device verification as separate evidence levels. Do not represent a prepared feature as deployed.

## Development Workflow

Specify user-visible outcomes first, then plan bounded increments and explicit acceptance checks. Prefer independent tasks that can be implemented and tested in parallel. Verify compatibility across OAK, Orin, and browser contracts before changing deployed behavior. Require explicit owner approval before pushing, deploying, or promoting a candidate model.

## Governance

This proposed constitution guides the current feature specification and plan. The maintainer may amend it; changes should state why and update affected plans and tests. It does not claim prior project ratification.

**Version**: 0.1.0-proposed | **Drafted**: 2026-11-09
