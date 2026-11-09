# Validation Quickstart: Standalone LEGO CV Lab

This is an acceptance guide for a planned implementation, not a claim that the commands in [workflow-cli.md](contracts/workflow-cli.md) already exist. The first working version can import OAK RGB snapshots; direct OAK acquisition and a local dashboard may follow. Run local fixtures before any physical or deployment claim.

## Prerequisites

- Establish the proposed standalone repository and a pinned Python environment. Configure a data root outside Git for images, annotations, checkpoints, and predictions.
- Prepare synthetic fixture images for deterministic tests and, separately, OAK 4 RGB snapshots with source/device and capture-time metadata.
- Inventory around 20 mixed-color, mixed-size LEGO pieces and a board. Fix camera pose/distance and lighting. Record the shake procedure and verify all baseline pieces are flat, separated, non-touching, and non-overlapping. Record actual count rather than assuming exactly 20.
- Define and version color, footprint/size, partly visible, unknown, and instance geometry rules before labeling.

## 1. Image ingestion and integrity

Import a small fixture set and then OAK source snapshots. Reopen the image and scene manifests. Each accepted image must retain source, capture time, dimensions, scene group, and SHA-256. Deliberately omit capture time from a negative fixture; the gap must be explicit. Alter one image byte after import; trusted dataset export must reject the hash mismatch. Reimporting the same bytes may deduplicate storage but must not erase capture context.

**Pass**: 100% of accepted source images retain required provenance, missing metadata is visible, and corrupted images cannot silently enter training.

## 2. Board and human labels

Create one separated-flat baseline scene from roughly 20 pieces, with actual count, board setup, camera settings, lighting, and no-contact/no-overlap eligibility. Annotate each visible piece with an original-image box or polygon, color, footprint category, reviewer, and revision. Use `unknown` when color or size is ambiguous; commercial part ID is optional. Revise one annotation and verify both revisions survive while the image hash stays unchanged.

Create a negative scene with two touching pieces. It must be rejected as `separated_flat` or assigned to the touching stage. Create an edge-truncated piece and apply the documented count/size inclusion rule. Rotate pieces in-plane in another image of the same layout; truth color and footprint rules must remain unchanged.

**Pass**: Every counted baseline piece has reviewed geometry and required labels; no source image is modified; baseline eligibility is enforced.

## 3. Frozen dataset export

Export a canonical reviewed annotation revision to the chosen detection or segmentation format. Validate that each image has matching labels, coordinates are in bounds, and class mappings match the taxonomy. Split by whole physical layout or collection session, then freeze test membership. Attempt to put nearby frames or rotated variants of the same arrangement in different partitions; expect rejection. Alter a label after freezing; a new dataset/split version is required.

**Pass**: Train, validation, and test groups are disjoint and repeatable by hash; no counted piece silently disappears from export.

## 4. Actual training comparison

Run one fine-tune from identified pretrained weights and one from-scratch initialization using the same architecture and held-out images. On a tiny synthetic fixture, this validates orchestration and provenance only, not accuracy. For a real comparison, document training-image count, augmentation, epochs/steps, seeds, batch size, hardware, wall time, initial weights, and any budget differences. Interrupt a fixture run; it must remain incomplete rather than producing a completed result.

**Pass**: Both candidate artifacts and run records exist with starting state and budget. A scratch run with too little data is labeled exploratory if a controlled performance comparison would be misleading.

## 5. Evaluate baseline and harder stages

Run both models on the identical frozen test images and inference thresholds. Repeat evaluation with the same inputs and compare membership and metric totals. Check actual/predicted count, absolute count error, missed/extra pieces, instance precision/recall and box/mask quality, color and footprint confusion, split/merge errors, orientation strata, and eligible denominators. A model with no color or footprint output must show those metrics as unavailable.

Add at least one harder stage changing piece count, gap, touching, overlap/occlusion, or lighting. Its report must name the changed condition and remain separate from the baseline. Inspect per-image truth and predictions. Export a Git-safe finding with model/dataset/configuration hashes and limits, but no images or weights.

**Pass**: Two evaluations of a fixed fixture are identical; two difficulty stages have separate denominators; rotation does not change truth definitions.

## 6. Physical OAK evidence and later device gate

Import real OAK 4 baseline snapshots and repeat the board/label/evaluation flow. Record exact OAK source identity, image settings, geometry, and scene conditions. Report this as physical capture and off-device model evaluation. A local checkpoint is `experimental`; it is not `oak_tested` or `deployed`. If later pursuing RVC4 execution, separately verify conversion, package integration, exact device input transforms, FPS and accuracy, and rollback before changing those states.

**Pass**: A reviewer can tell whether each finding came from synthetic fixtures, physical OAK capture with off-device inference, or actual on-device inference.
