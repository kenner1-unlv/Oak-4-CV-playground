# Tasks: Multisensor ML Workflow

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), and [contracts/](contracts/)

**Organization**: Phases follow the five user stories. `[P]` means the task can run alongside other ready tasks because it owns different files. All proposed APIs and file paths are implementation targets, not existing functionality.

## Phase 1: Setup

**Purpose**: Establish deployment boundaries and source inventory before adding capture.

- [ ] T001 Record the deployed OAK package/version, four model YAML references, Orin identity service, L2 relay, source clock domains, current ports, and unknown artifact provenance in `bridges/README.md`.
- [ ] T002 Add an Orin data-root example, size/quota settings, listen address, and secret-free configuration guidance in `bridges/capture.example.toml` and `bridges/README.md`; depend on T001.
- [ ] T003 [P] Exclude local captures, SQLite indexes, model weights, and private scene assets from Git in `.gitignore` without removing tracked fixtures.
- [ ] T004 Measure and document the capture-specific OAK image/crop transfer choice, source frame IDs, payload bounds, and expected bandwidth in `specs/001-multisensor-ml-workflow/quickstart.md`; do not treat independent browser polls as synchronized inputs.

## Phase 2: Foundational Records and Transport

**Purpose**: Define one versioned, bounded data path and durable storage boundary used by every story.

- [ ] T005 Implement validated version-1 session, asset, observation, model, snapshot, correction, split, run, and calibration records with explicit unknown/missing states in `bridges/capture_schema.py` per `contracts/records.md`.
- [ ] T006 [P] Add contract fixtures for source observations, missing samples, L2 samples, and session manifests in `bridges/tests/fixtures/capture_v1/`.
- [ ] T007 Implement configured Orin data-root validation, atomic content-hashed asset writes, relative-path enforcement, and SQLite catalog initialization in `bridges/capture_store.py`; depend on T005.
- [ ] T008 Implement bounded authenticated/local-network ingestion and source clock/sequence discontinuity detection in `bridges/capture_service.py`; depend on T005 and T007.
- [ ] T009 [P] Add source frame sequence and original timestamp metadata to the opt-in OAK capture transfer in `apps/spatial-segmentation/main.py`, preserving existing live UDP/API behavior; depend on T004 and T005.
- [ ] T010 [P] Add ROS frame ID, stamp, source count, stride, saved count, and Orin receipt time to the optional L2 capture handoff in `bridges/l2_cloud_relay.py`; depend on T005.
- [ ] T011 Verify version parsing, size limits, path rejection, unknown clocks, hash failures, and interrupted writes with synthetic fixtures in `bridges/tests/test_capture_contract.py` and `bridges/tests/test_capture_store.py`; depend on T005-T008.

**Checkpoint**: Tagged OAK/Orin/L2 records can be stored without assuming camera-to-L2 synchronization. Existing live views still run with capture disabled.

## Phase 3: User Story 1 - Record a Reproducible Session (P1, MVP)

**Goal**: Explicitly start/stop an Orin recording from Training Lab and reopen its durable manifest.

**Independent test**: Capture a short local fixture, stop, reopen and hash-check its manifest/assets; simulate missing source, storage exhaustion, and a crash to confirm visible gaps and `incomplete` state.

- [ ] T012 [US1] Implement idempotent start, stop, status, single-active-session rule, quota reservation, bounded queue flush, and atomic manifest finalization in `bridges/capture_service.py`; depend on T007-T008.
- [ ] T013 [P] [US1] Implement incomplete-session recovery and explicit dropped, unmatched, restart, and clock-jump markers in `bridges/capture_store.py`; depend on T007.
- [ ] T014 [US1] Expose `GET /api/capture/status`, `POST /api/capture/sessions`, stop, list, detail, observations, and verified asset endpoints in `bridges/capture_service.py` per `contracts/capture-api.md`; depend on T012-T013.
- [ ] T015 [US1] Add a bounded same-origin capture proxy with configurable Orin address and error propagation in `apps/spatial-segmentation/model_controls.py`; depend on T014.
- [ ] T016 [US1] Add disabled-by-default Training Lab start/stop controls and live elapsed time, per-source counts, drops, bytes, queue, sync state, and error display in `apps/spatial-segmentation/housev.js` and `apps/spatial-segmentation/housev.css`; depend on T015.
- [ ] T017 [US1] Test idempotent control, quota/storage failure, crash recovery, source gaps, and asset integrity in `bridges/tests/test_capture_service.py`; depend on T012-T014.
- [ ] T018 [US1] Run and document the five-minute OAK/Orin/L2 capture acceptance on named hardware, including sample sources/times, drops, throughput, storage, and live-view continuity in `specs/001-multisensor-ml-workflow/quickstart.md`; depend on T016-T017.

## Phase 4: User Story 2 - Inspect and Correct Evidence (P2)

**Goal**: Browse sessions, model references, and prediction snapshots; compare available evidence and append attributed corrections.

**Independent test**: Reopen a fixture session, inspect all available source timelines and an unknown model field, revise a correction, and confirm raw hashes and prior correction revisions stay intact.

- [ ] T019 [P] [US2] Inventory the four OAK model YAML references and verified installed package metadata as model artifacts, marking unavailable source/training metadata `unknown`, in `bridges/model_catalog.py`; depend on T005.
- [ ] T020 [P] [US2] Implement append-only attributed correction revisions and active-revision lookup in `bridges/review_store.py`; depend on T005 and T007.
- [ ] T021 [US2] Add model, snapshot, correction create/list, session timeline, and integrity-failure API handlers in `bridges/capture_service.py`; depend on T019-T020.
- [ ] T022 [US2] Add recordings, source evidence timeline, model/snapshot catalog, score semantics, stale/missing/unaligned labels, and correction history to `apps/spatial-segmentation/housev.js` and `apps/spatial-segmentation/housev.css`; depend on T021.
- [ ] T023 [US2] Verify immutable raw records, superseding corrections, model metadata mismatch, missing assets, and explicit unknown provenance in `bridges/tests/test_review_store.py` and `bridges/tests/test_model_catalog.py`; depend on T019-T021.

## Phase 5: User Story 3 - Run the LEGO Board Benchmark (P3)

**Goal**: Establish repeatable, labeled piece-level measurements before training claims.

**Independent test**: Score a synthetic approximately 20-piece shaken-flat board with mixed colors and sizes, no contact/overlap, and varied orientations; reject an ineligible baseline layout and report per-piece and aggregate denominators.

- [ ] T024 [P] [US3] Version the board dimensions, lighting, camera pose/distance, shake procedure, piece inventory, color/size taxonomy, orientation variation, and baseline eligibility rules in `benchmarks/lego_board/protocol.yaml` and `benchmarks/lego_board/README.md`.
- [ ] T025 [P] [US3] Create small synthetic baseline and invalid-layout scene/instance truth fixtures, including stable piece IDs, polygons/boxes, color, footprint/size, separation, and orientation, in `benchmarks/lego_board/fixtures/`; depend on T024.
- [ ] T026 [US3] Validate `BenchmarkScene` and `PieceTruth` records, independent annotation provenance, and baseline eligibility in `bridges/lego_truth.py`; depend on T024-T025.
- [ ] T027 [US3] Implement LEGO count error, per-instance detection/mask quality, per-color and per-size confusion, touching/split/merge errors, orientation strata, and missing-range denominators in `bridges/lego_benchmark.py`; depend on T026.
- [ ] T028 [US3] Add benchmark scene/stage selection, ground-truth review, and per-piece result display to `apps/spatial-segmentation/housev.js` and `apps/spatial-segmentation/housev.css`; depend on T026-T027.
- [ ] T029 [US3] Test eligibility, actual-count versus target-count handling, orientation invariance, empty/missing predictions, and metric numerators/denominators with `benchmarks/lego_board/fixtures/` in `bridges/tests/test_lego_benchmark.py`; depend on T026-T027.
- [ ] T030 [US3] Define stage progression for changed piece count, gap/contact, overlap/occlusion, dense layouts, motion, and lighting, with a separate result per changed condition, in `benchmarks/lego_board/stages.yaml` and `benchmarks/lego_board/README.md`; depend on T024 and T029.
- [ ] T031 [US3] Publish a Git-safe findings template that names ground-truth method, scene/stage, model and configuration, sample denominators, limits, and hashes without raw media or weights in `benchmarks/lego_board/findings/README.md`; depend on T027.

## Phase 6: User Story 4 - Train and Evaluate Candidates (P4)

**Goal**: Freeze grouped datasets, train a supervised LEGO candidate away from OAK, and compare LEGO and Orin identity candidates with baselines on identical held-out evidence.

**Independent test**: Reject scene leakage, freeze a small fixture split, run detector and identity baseline/candidate comparisons twice, and get identical membership and totals while deployment state stays unchanged.

- [ ] T032 [US4] Implement versioned, scene/session-grouped train/validation/test manifests, immutable held-out membership hash, truth revision, and overlap rejection in `bridges/dataset_split.py`; depend on T005, T020, and T026.
- [ ] T033 [US4] Export only reviewed RGB assets and instance labels, with taxonomy and source hashes, in a training-ready manifest under the configured Orin data root via `bridges/lego_dataset.py`; depend on T032.
- [ ] T034 [P] [US4] Implement an off-OAK supervised LEGO instance detection/segmentation train-and-infer CLI with pinned framework/version, dataset input, checkpoint/model hashes, configuration, and prediction snapshots in `bridges/lego_candidate.py`; depend on T005, T027, and T033.
- [ ] T035 [P] [US4] Define an Orin association candidate adapter that can replay existing identity outputs and candidate predictions without changing issue #2 fusion behavior in `bridges/identity_candidate.py`; depend on T005.
- [ ] T036 [US4] Implement explicit off-OAK training and evaluation job states, measured Orin resource gate, pause/queue/reject reason, and live-model preservation in `bridges/experiment.py`; depend on T032-T035.
- [ ] T037 [US4] Implement same-example LEGO baseline/candidate and Orin identity baseline/candidate comparisons with per-scene metrics, denominators, latency, and failure cases in `bridges/experiment.py`; depend on T027 and T036.
- [ ] T038 [US4] Expose split freeze, experiment create/status, candidate/snapshot registration, and report retrieval through `bridges/capture_service.py`; depend on T032-T037.
- [ ] T039 [US4] Add split, run, model provenance, baseline-versus-candidate reports, and explicit replay/shadow/live status to Training Lab in `apps/spatial-segmentation/housev.js` and `apps/spatial-segmentation/housev.css`; depend on T038.
- [ ] T040 [US4] Test scene and adjacent-frame leakage, held-out immutability, deterministic totals, artifact hash mismatch, resource rejection, and no implicit promotion in `bridges/tests/test_experiment.py`; depend on T032-T038.
- [ ] T041 [US4] Document a reproducible local training/evaluation command, model format requirements, separate OAK conversion/deployment gate, and rollback candidate in `specs/001-multisensor-ml-workflow/quickstart.md`; depend on T036-T040.

## Phase 7: User Story 5 - Compare Calibrated L2 and Stereo (P5)

**Goal**: Keep unaligned L2 as independent scene context; compare board/scene range only with measured transform, timing, and known-distance references.

**Independent test**: An uncalibrated fixture displays no fused range metric; a validated reference fixture reports board/scene error and uncertainty; sparse point coverage blocks per-piece claims.

- [ ] T042 [US5] Implement versioned L2-to-camera transform, clock offset/drift, reference-distance residual, validity bounds, and point-density states in `bridges/calibration.py`; depend on T005 and T010.
- [ ] T043 [US5] Implement board/scene range comparison with measurement uncertainty, absent data, and explicit per-piece resolution gate in `bridges/l2_range_study.py`; depend on T042.
- [ ] T044 [US5] Expose calibration create/read and gated range-study results through `bridges/capture_service.py`; depend on T042-T043.
- [ ] T045 [US5] Display unaligned L2 preview, age/point counts, calibration state, and only supported range comparisons in `apps/spatial-segmentation/housev.js` and `apps/spatial-segmentation/housev.css`; depend on T044.
- [ ] T046 [US5] Verify uncalibrated, stale, sparse, bad-transform, and known-distance fixture gates in `bridges/tests/test_calibration.py` and `bridges/tests/test_l2_range_study.py`; depend on T042-T044.
- [ ] T047 [US5] Record actual L2 board point density, clock alignment, transform, reference target distances, and comparison limits in `specs/001-multisensor-ml-workflow/quickstart.md`; depend on T045-T046.

## Phase 8: Polish and Cross-Cutting Verification

- [ ] T048 Run the existing OAK and Orin Python test suites plus new fixture tests; record commands and pass/fail evidence in `specs/001-multisensor-ml-workflow/quickstart.md`.
- [ ] T049 Verify the live Vision Lab, identity, mono, and L2 routes still work while recording is off and during capture; record observed device/version and any gap in `specs/001-multisensor-ml-workflow/quickstart.md`.
- [ ] T050 Inspect `git status` and `git ls-files` to confirm no recordings, private imagery, SQLite index, or model weights entered Git; document the shareable-artifact boundary in `bridges/README.md`.

## Dependencies and Execution Order

- Setup T001-T004 precedes the foundational contract and transport work T005-T011. T005 and T007-T008 gate all API-backed stories.
- US1 T012-T018 is the MVP and supplies persisted sessions for US2 review and US3 physical benchmark captures.
- US2 T019-T023 can begin after the foundation; corrections T020 are required by US4 split/training export.
- US3 T024-T031 can begin protocol and synthetic fixtures independently of live capture. US4 needs its truth schema and benchmark metrics from T026-T027.
- US4 T032-T041 needs reviewed truth and frozen split membership. The LEGO and identity candidate adapters T034-T035 can be developed in parallel after their shared record contract.
- US5 T042-T047 can begin after the source record contract and L2 handoff. Calibration cannot be inferred from the dashboard preview.
- Cross-cutting T048-T050 follows the desired story implementation and physical availability. Hardware verification is separate from passing fixture tests.

## Parallel Execution Examples

- After T005, separate owners can work on OAK tagged frames T009, L2 metadata T010, and Orin storage T007-T008 in their distinct files.
- After the foundation, one owner can implement US1 capture UI/service while another inventories the model catalog T019 and a third versions the LEGO protocol T024.
- After truth and splits are ready, detector adapter T034 and identity adapter T035 can run in parallel; both feed one experiment/report integration in T036-T039.
- US5 calibration module T042 can proceed independently of US4 candidate work, with shared `bridges/capture_service.py` integration scheduled after both owners coordinate.

## Implementation Strategy and Issue Groups

1. **MVP / [issue #3](https://github.com/kenner1-unlv/Oak-4-CV-playground/issues/3)**: T001-T018: Orin capture, tagged OAK/L2 records, Training Lab controls, immutable session manifest and recovery.
2. **[Issue #4](https://github.com/kenner1-unlv/Oak-4-CV-playground/issues/4)**: T019-T023: session/model/snapshot catalog and attributed correction revisions.
3. **[Issue #5](https://github.com/kenner1-unlv/Oak-4-CV-playground/issues/5)**: T024-T031: staged LEGO board protocol, human truth, piece-level benchmark and Git-safe findings.
4. **[Issue #6](https://github.com/kenner1-unlv/Oak-4-CV-playground/issues/6)**: T032-T041: frozen datasets, supervised LEGO and Orin identity candidate training/evaluation, experiment reports and resource gate.
5. **[Issue #7](https://github.com/kenner1-unlv/Oak-4-CV-playground/issues/7)**: T042-T047: L2 calibration, board/scene range comparison and per-piece resolution gate.
6. **Acceptance issue group**: T048-T050: fixture regression, hardware validation, and repository boundary audit.

Existing cross-camera identity fusion issue #2 and dense-scene benchmark issue #1 remain separate. This feature provides their evidence and evaluation inputs.
