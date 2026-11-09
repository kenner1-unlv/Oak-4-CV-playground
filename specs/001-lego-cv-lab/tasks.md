# Tasks: Standalone LEGO CV Lab

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), and [contracts/](contracts/).

**Path convention**: Implementation paths below are relative to the **proposed, separately created `lego-cv-lab` repository root**. This planning package remains in the OAK playground until the target repository is established. The current House V, Orin identity, and Unitree L2 code are outside this feature. `[P]` marks ready work in separate files that can be assigned in parallel.

## Phase 1: Setup

**Purpose**: Establish an independent, reproducible experiment repository and keep data outside Git.

- [ ] T001 Create the standalone `lego-cv-lab` repository structure in `pyproject.toml`, `lego_cv_lab/__init__.py`, `tests/__init__.py`, `protocols/README.md`, and `findings/README.md`; pin the chosen Python version and test tooling.
- [ ] T002 [P] Configure a required external data root for raw images, annotations, prediction sets, logs, and weights in `lego_cv_lab/config.py` and `config.example.toml`.
- [ ] T003 [P] Exclude raw images, private manifests, SQLite files, checkpoints, and training outputs from the repository in `.gitignore`; retain only reviewed synthetic fixtures and Git-safe findings.
- [ ] T004 Document local import, optional OAK snapshot, annotation, training, evaluation, and hardware-state boundaries in `README.md`; do not claim any proposed command already runs.

## Phase 2: Foundational Contracts and Integrity

**Purpose**: Give acquisition, labels, training, and findings the same versioned record and hash rules.

- [ ] T005 Implement validated version-1 records for capture session, image asset, board scene, piece truth, annotation revision, taxonomy, dataset, split, model run, artifact, prediction set, and finding in `lego_cv_lab/records.py` per `contracts/records.md`.
- [ ] T006 [P] Add small synthetic RGB images and example version-1 records with no private scene data in `tests/fixtures/`.
- [ ] T007 Implement configured-root path validation, content-hashed immutable image/weight storage, atomic manifest writes, and integrity checks in `lego_cv_lab/storage.py`; depend on T005.
- [ ] T008 Verify invalid paths, missing source time, corrupt hashes, duplicate image bytes, and interrupted manifest writes in `tests/test_records_storage.py`; depend on T005-T007.

**Checkpoint**: Source images, labels, checkpoints, predictions, and findings have distinct records and verified references.

## Phase 3: User Story 1 - Collect Repeatable LEGO Scenes (P1, MVP)

**Goal**: Import or explicitly capture OAK RGB snapshots with a repeatable board setup, independent of House V.

**Independent test**: Import baseline snapshots, reopen the image and scene manifests, and see actual count, setup, stage, integrity, and missing metadata.

- [ ] T009 [P] [US1] Version the board size, camera pose/distance, lighting, shake procedure, approximate 20-piece mixed inventory, actual-count field, and flat/separate eligibility checklist in `protocols/lego_board_v1.yaml` and `protocols/README.md`.
- [ ] T010 [US1] Implement OAK/image-file snapshot import with capture source/time/clock, dimensions, camera settings when known, scene group, and SHA-256 in `lego_cv_lab/capture/import_images.py`; depend on T005 and T007.
- [ ] T011 [P] [US1] Implement an explicit OAK 4 RGB snapshot command in `lego_cv_lab/capture/oak_snapshot.py` that writes through T010, records the exact device/API settings, and leaves the existing OAK application untouched; depend on T010.
- [ ] T012 [US1] Implement board scene creation and `separated_flat` eligibility validation, including actual inventory/count, no contact/overlap, setup notes, and changed conditions in `lego_cv_lab/capture/scenes.py`; depend on T009-T010.
- [ ] T013 [US1] Expose `import-images` and `scene create/review` commands with explicit errors for missing metadata or files in `lego_cv_lab/cli.py`; depend on T010-T012.
- [ ] T014 [US1] Verify import provenance, image immutability, repeated captures in one scene group, and rejected ineligible baseline layouts with `tests/fixtures/` in `tests/test_capture_scenes.py`; depend on T010-T013.
- [ ] T015 [US1] Perform a real OAK 4 snapshot trial and record device identity, resolution, capture rate, timestamp source, and unverified fields in `protocols/field-trials.md`; depend on T011-T014. Keep private snapshots in the external data root.

## Phase 4: User Story 2 - Annotate and Review Pieces (P2)

**Goal**: Produce reviewed, versioned instance truth without editing the source image.

**Independent test**: Label all visible pieces in one fixture, revise one label, and show both revisions and the unchanged source hash.

- [ ] T016 [P] [US2] Version the `piece` presence class, color and size/footprint vocabularies, measurement rules, unknown/ambiguous states, and partly visible inclusion rule in `protocols/taxonomy_v1.yaml` and `protocols/README.md`.
- [ ] T017 [US2] Implement original-image box/polygon validation, stable piece IDs, color/footprint labels, optional part ID/orientation, reviewer attribution, and append-only revisions in `lego_cv_lab/dataset/annotations.py`; depend on T005, T007, and T016.
- [ ] T018 [US2] Implement annotation completeness and review-state checks, including count versus visible instances and rejected/out-of-bounds geometry, in `lego_cv_lab/dataset/validate.py`; depend on T017.
- [ ] T019 [US2] Add `annotate` and `dataset validate` CLI operations that preserve prior revisions and refuse unreviewed training export in `lego_cv_lab/cli.py`; depend on T017-T018.
- [ ] T020 [P] [US2] Add a small local image/annotation review view with source image, overlays, unknown labels, revision history, and explicit save/review state in `lego_cv_lab/dashboard/app.py` and `lego_cv_lab/dashboard/static/`; depend on T017-T018.
- [ ] T021 [US2] Test annotation revisions, visible-piece count, unknown label exclusions, partial visibility, and geometry bounds in `tests/test_annotations.py`; depend on T017-T019.

## Phase 5: User Story 3 - Train and Compare Models (P3)

**Goal**: Train a real LEGO detector or instance segmenter by fine-tuning, then make a controlled from-scratch comparison when data and compute permit.

**Independent test**: Freeze a scene-grouped fixture split, train or replay two candidates, evaluate both on identical held-out images, and reproduce the split and comparison totals.

- [ ] T022 [US3] Build versioned dataset manifests from verified images, reviewed annotation revisions, taxonomy, and eligibility decisions in `lego_cv_lab/dataset/manifest.py`; depend on T018.
- [ ] T023 [US3] Implement scene/layout-grouped train/validation/test assignment, overlap rejection, and immutable held-out membership hash in `lego_cv_lab/dataset/split.py`; depend on T022.
- [ ] T024 [US3] Export reviewed boxes or masks to the pinned trainer format with image/label mapping and provenance in `lego_cv_lab/dataset/export.py`; depend on T022-T023.
- [ ] T025 [US3] Select and pin a suitable licensed detection or instance-segmentation framework, architecture, pretrained checkpoint, input transform, and training configuration in `pyproject.toml` and `configs/lego_detector.yaml`; document the selection in `README.md`.
- [ ] T026 [US3] Implement actual off-OAK pretrained fine-tuning with seed, split, hyperparameters, augmentation, device, duration, logs, resource use, and checkpoint hash in `lego_cv_lab/training/train.py`; depend on T024-T025.
- [ ] T027 [US3] Add from-scratch initialization using the same architecture and held-out membership, recording training budget differences and marking underpowered runs exploratory in `lego_cv_lab/training/train.py`; depend on T026.
- [ ] T028 [P] [US3] Implement checkpoint loading and versioned per-image prediction sets with thresholds, boxes/masks, scores, and optional color/footprint outputs in `lego_cv_lab/training/predict.py`; depend on T025.
- [ ] T029 [US3] Implement controlled fine-tune-versus-scratch comparison with basic count error and detection precision/recall totals, rejecting differing test membership and listing weights, data, augmentation, seed, and compute-budget differences in `lego_cv_lab/evaluation/compare.py`; depend on T023 and T026-T028.
- [ ] T030 [US3] Expose `dataset export`, `split freeze`, `train`, `predict`, and `evaluate` CLI operations with separate run/checkpoint/prediction IDs in `lego_cv_lab/cli.py`; depend on T022-T029.
- [ ] T031 [US3] Test adjacent-frame/orientation leakage, frozen membership, interrupted runs, prediction provenance, and comparison mismatch rejection in `tests/test_training_workflow.py`; depend on T022-T030.

## Phase 6: User Story 4 - Benchmark Baseline and Harder Stages (P4)

**Goal**: Report per-piece and aggregate performance for the separate-piece baseline and progressively harder board scenes.

**Independent test**: Score two labeled synthetic scenes at different stages and inspect count, localization, color/size, separation, and orientation metrics with denominators.

- [ ] T032 [US4] Version stage definitions that vary one condition at a time among count, spacing, contact, overlap/occlusion, and lighting in `protocols/lego_stages_v1.yaml`; depend on T009.
- [ ] T033 [P] [US4] Add synthetic baseline, touching/merge, missed-piece, extra-piece, rotated, and unknown-attribute cases in `tests/fixtures/benchmark/`; depend on T016 and T032.
- [ ] T034 [US4] Extend basic comparison metrics with exact-count rate, instance matching/IoU or mask IoU, color and footprint confusion, split/merge, exclusions, and zero-denominator `unavailable` states in `lego_cv_lab/evaluation/metrics.py`; depend on T017, T028, and T029.
- [ ] T035 [US4] Implement per-scene, stage, changed-condition, and orientation strata reports with model/split/truth hashes and matching thresholds in `lego_cv_lab/evaluation/report.py`; depend on T029 and T032-T034.
- [ ] T036 [US4] Add a local snapshot/label/prediction/run browser that shows actual measured results and model state (`experimental`, `converted`, `oak_tested`, `deployed`, `unknown`) in `lego_cv_lab/dashboard/app.py` and `lego_cv_lab/dashboard/static/`; depend on T020 and T035.
- [ ] T037 [US4] Test count/color/size truth under rotation, stage isolation, split/merge, unknown-label exclusions, and report determinism against `tests/fixtures/benchmark/` in `tests/test_metrics_report.py`; depend on T033-T035.
- [ ] T038 [US4] Implement Git-safe findings export with scene/stage, truth method, dataset/model/configuration, comparison budget, denominators, error IDs, and limits but no image bytes or weights in `lego_cv_lab/evaluation/findings.py`; depend on T035-T037.
- [ ] T039 [US4] Document a real board baseline trial followed by one controlled harder stage and distinguish physical results from synthetic fixtures in `findings/README.md` and `protocols/field-trials.md`; depend on T015 and T035-T038.

## Phase 7: Polish and Optional Device Path

- [ ] T040 Run all synthetic capture, annotation, split, training-workflow, and metric checks; record commands and actual results in `README.md`.
- [ ] T041 Review `git status` and tracked paths for private images, raw manifests, checkpoints, credentials, and absolute paths before publishing any finding; record the review boundary in `findings/README.md`.
- [ ] T042 Keep optional RVC4 conversion, exact-device input-transform/performance verification, owner-approved deployment, and rollback as a separately gated follow-on plan in `protocols/oak_deployment_gate.md`; do not label local replay as OAK-tested.

## Dependencies and Execution Order

- T001-T004 establish the new repository and external data root. T005-T008 define records and integrity before source acquisition.
- US1 T009-T015 produces auditable RGB scenes. OAK physical capture T015 may await hardware; imported fixtures keep later development moving.
- US2 T016-T021 produces reviewed instance truth. Its taxonomy T016 can proceed beside US1 acquisition once foundational records exist.
- US3 T022-T031 requires reviewed truth and verified images. Split/export precede training. A fine-tuned candidate precedes the optional matched scratch comparison; both evaluate on one frozen held-out set.
- US4 T032-T039 can define stages and fixture cases alongside training, but metric/report integration waits for prediction and split contracts. The first physical trial follows the fixture pipeline.
- T040-T042 close the selected increment. OAK conversion/deployment remains a later, separate gate.

## Parallel Execution Examples

- After T005-T008, acquisition owner can build T009-T015 while annotation owner defines T016 and benchmark owner drafts T032 in separate `capture/`, `dataset/`, and `protocols/` files; coordinate shared `protocols/README.md` edits.
- After T022-T025, a training owner can build T026-T027 while a prediction owner builds T028 in separate `training/` modules, then integrate comparison T029.
- A dashboard owner can build T020 after the annotation contract while a metrics owner builds T034 and fixtures T033; integrate stage reports only when both are ready.

## Provisional Issue Mapping and Incremental Delivery

The OAK playground currently holds planning issues. Transfer or recreate them in the separate `lego-cv-lab` repository once its location is chosen, preserving links and scope history.

1. **Issue #3, repository and OAK snapshots (MVP)**: T001-T015 and T041. Independent import precedes physical OAK capture.
2. **Issue #4, taxonomy, reviewed annotations, and frozen dataset**: T016-T024.
3. **Issue #6, actual fine-tuning, scratch comparison, and training CLI**: T025-T031 and T042. Use identical held-out images and disclose budget differences. OAK conversion/deployment remains a later gate.
4. **Issue #5, staged benchmark, local browser, findings, and final regression**: T032-T040.

Existing cross-camera fusion issue #2 and dense-scene benchmark issue #1 are unrelated to this standalone study. The earlier L2 planning issue #7 is closed and supplies no task here.
