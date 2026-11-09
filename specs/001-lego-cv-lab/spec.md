# Feature Specification: Standalone LEGO CV Lab

**Feature Branch**: plan/multisensor-ml-workflow
**Created**: 2026-11-09
**Status**: Draft, revised for corrected scope
**Input**: Collect OAK 4 snapshots of LEGO pieces, annotate them, train and compare instance-recognition models, and measure results on progressively harder scenes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Collect Repeatable LEGO Scenes (Priority: P1)

As an experimenter, I can collect OAK 4 source images and describe each board arrangement so that I can label, train, and compare models later.

**Why this priority**: Controlled source images are the foundation for credible ML results.
**Independent Test**: Import baseline snapshots and reopen the scene and source records without House V.

**Acceptance Scenarios**:

1. **Given** about 20 mixed-color, mixed-size pieces shaken flat and separated on a board, **when** I record a baseline scene, **then** the actual count, lighting, camera and board setup, and non-touching/non-overlapping status are recorded.
2. **Given** multiple OAK snapshots of one arrangement, **when** I ingest them, **then** each retains source, capture time, scene and stage, dimensions, and integrity identity.
3. **Given** a missing image or metadata item, **when** I open the scene, **then** the gap is visible and cannot silently support a claim requiring that evidence.

---

### User Story 2 - Annotate and Review Pieces (Priority: P2)

As a reviewer, I can mark each visible piece and its color and size/footprint, inspect predictions, and correct annotations without changing the source image.

**Why this priority**: Human-reviewed labels must be distinct from model guesses.
**Independent Test**: Label every piece in one fixture, revise one label, and confirm prior revisions and the source remain available.

**Acceptance Scenarios**:

1. **Given** a baseline image, **when** I annotate it, **then** each visible piece has its own box or mask, color category, size/footprint category, and review state.
2. **Given** a rotated piece, **when** I label it, **then** in-plane orientation does not change its color, size category, or instance identity; orientation may be recorded for analysis.
3. **Given** a prediction, **when** I review it, **then** predicted and human-reviewed values are visibly separate and corrections have history.
4. **Given** an unknown commercial part ID, **when** I label the piece, **then** I can use color and footprint without inventing an exact part ID.

---

### User Story 3 - Train and Compare Models (Priority: P3)

As an experimenter, I can fine-tune a detector or instance segmenter on reviewed LEGO images, compare it with training from scratch, and inspect reproducible results before considering OAK deployment.

**Why this priority**: The lab must produce and evaluate actual ML models, not merely display CV output.
**Independent Test**: Train or replay two candidates on a small labeled fixture with a frozen test split and reproduce their comparison records.

**Acceptance Scenarios**:

1. **Given** reviewed images, **when** I prepare a dataset, **then** images of one physical arrangement or collection session stay in one train, validation, or held-out test partition.
2. **Given** fine-tuned and from-scratch candidates, **when** I compare them, **then** starting weights, training image count, budget, configuration, and shared held-out examples are stated.
3. **Given** a completed run, **when** I inspect it, **then** model artifact, training provenance, metrics, and actual OAK execution status are identifiable; unknown facts are marked unknown.
4. **Given** local-only results, **when** I inspect the model, **then** it is shown as experimental rather than physically tested or deployed.

---

### User Story 4 - Benchmark Baseline and Harder Stages (Priority: P4)

As an experimenter, I can measure count, color, size, instance separation, and orientation robustness on the easy board first, then study harder scenes without mixing their results.

**Why this priority**: Staged measurements expose failure modes and demonstrate whether training improves the intended tasks.
**Independent Test**: Score two labeled fixtures at different difficulty stages and inspect per-stage metrics and errors.

**Acceptance Scenarios**:

1. **Given** a flat, non-touching, non-overlapping baseline, **when** I score a model, **then** count error, missed and extra pieces, instance matching, color, size/footprint, and split/merge outcomes include denominators.
2. **Given** pieces rotated in-plane, **when** I compare results, **then** orientation-related errors are visible while ground-truth count, color, and size rules stay the same.
3. **Given** more pieces, smaller gaps, touching, overlap/occlusion, or changed lighting, **when** I evaluate a harder scene, **then** the changed condition and per-stage results are explicit.
4. **Given** a finding prepared for Git, **when** it is shared, **then** it contains model, dataset, scene, metric, and limitation provenance without raw images or weights.

### Edge Cases

- Pieces touch or overlap in a proposed baseline: classify the scene as a harder stage or invalid baseline.
- A piece is partly outside the image: record truncation and apply a documented count/size rule.
- Lighting or reflection makes color ambiguous: retain review uncertainty rather than fabricate certainty.
- Size/footprint cannot be judged reliably: mark uncertain instead of inventing a category.
- Multiple frames of the same arrangement risk split leakage: keep them in one partition.
- Source image or artifact integrity fails: flag and exclude it from trusted scoring.
- Training is interrupted: preserve run status without treating partial results as complete.
- Candidate runs differ in data or compute budget: report differences and avoid a controlled-comparison claim.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The lab MUST accept OAK 4 snapshots with source device, capture time, scene, image dimensions, and integrity provenance.
- **FR-002**: The baseline MUST support approximately 20 shaken-flat, non-touching, non-overlapping pieces of varied colors and sizes, recording the actual count and conditions.
- **FR-003**: Source images MUST remain separate from annotations, predictions, and derived datasets.
- **FR-004**: Reviewers MUST be able to annotate or correct each visible instance with a box or mask, color, size/footprint, and review state. Exact commercial part ID MUST be optional.
- **FR-005**: Color and size/footprint taxonomies and the inclusion rule for partly visible pieces MUST be documented and versioned.
- **FR-006**: Train, validation, and held-out test manifests MUST keep all images of one arrangement/session in one partition and freeze test membership before tuning.
- **FR-007**: The workflow MUST support custom object detection or instance segmentation training using reviewed LEGO images and distinguish fine-tuning from training from scratch, including starting weights, data, configuration, budget, and results.
- **FR-008**: A controlled fine-tune versus scratch comparison MUST use the same held-out examples and state any training data or budget differences.
- **FR-009**: Evaluation MUST report count error, instance detection or mask quality, color and size/footprint results, missed/extra pieces, and split/merge errors with denominators.
- **FR-010**: Evaluation MUST keep count, color, and size ground truth invariant under in-plane rotation and report orientation breakdown when test labels permit.
- **FR-011**: The benchmark MUST support separately reported stages varying count, spacing, touching, overlap/occlusion, or lighting, with changed conditions recorded.
- **FR-012**: Model artifacts and prediction snapshots MUST show training and evaluation provenance and distinguish experimental, converted, physically OAK-tested, deployed, and unknown states.
- **FR-013**: Local training or replay MUST NOT alone be presented as physical OAK verification.
- **FR-014**: Git-safe findings MUST include scene/stage, label method, dataset/model versions, comparison budget, denominators, and limits without raw images or trained weights.

### Key Entities

- **Source Snapshot**: Immutable OAK image identity, source, capture time, dimensions, and scene.
- **LEGO Scene**: Board setup, actual count, lighting, camera pose, separation state, and stage.
- **Piece Annotation**: Reviewed geometry, color, footprint, optional orientation or part ID, and revision.
- **Dataset Split**: Versioned partitions grouped by arrangement/session, including frozen test membership.
- **Model Run**: Candidate type, starting weights, data, configuration, budget, status, and artifact.
- **Prediction Snapshot**: Model output tied to a known source image and execution status.
- **Benchmark Finding**: Per-scene/stage results, denominators, comparison details, and limits.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A baseline OAK scene of about 20 separate pieces can be reopened; 100% of accepted images retain source, scene, capture time, dimensions, and integrity identity.
- **SC-002**: Every counted piece in a baseline fixture can receive a reviewed instance annotation; export contains no unlabeled counted pieces.
- **SC-003**: A baseline report states actual count, count error, missed/extra pieces, color and footprint accuracy, and separation quality with denominators.
- **SC-004**: Two evaluations of the same frozen fixture and outputs produce identical sample membership and metric totals.
- **SC-005**: A split that places images of one physical arrangement in different partitions is rejected.
- **SC-006**: A fine-tune versus scratch report states starting weights, training-image count, budget, and shared held-out examples.
- **SC-007**: At least two difficulty stages have separate summaries naming changed conditions; orientation tests preserve ground-truth count, color, and footprint definitions.
- **SC-008**: A reviewer can distinguish experimental, converted, and physically tested candidates from their records.

## Assumptions

- This lab may live in a separate repository. The existing OAK project provides image-source context, but House V, Orin identity fusion, and the live pipeline are not prerequisites.
- Initial images come from OAK 4 snapshots. Repeatable import suffices initially; live recording controls may be later work.
- Reviewers define practical color and size/footprint categories before scoring. Exact commercial part identification is outside the initial goal.
- Baseline pieces are shaken flat and confirmed separate, non-touching, and non-overlapping. About 20 is a setup target; actual count is recorded.
- Training and evaluation run away from the live OAK pipeline. OAK model conversion and physical inference require separate verification.
- Unitree L2 and Orin identity are outside the LEGO lab. L2 is not a source of piece labels or ground truth.
- Raw images, recordings, and weights stay out of Git; code, taxonomy, safe manifests/summaries, and reproducible findings may be tracked.
