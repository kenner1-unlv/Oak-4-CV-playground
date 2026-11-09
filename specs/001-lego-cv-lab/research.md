# Research and Design Decisions: LEGO CV Lab

**Date**: 2026-11-09. The experiment design below is proposed; no LEGO model has been trained or measured in this planning turn.

## Standalone project boundary

**Decision**: Recommend a separate `lego-cv-lab` repository, with this Spec Kit package as the proposal/backlog until that repo is established. The OAK 4 initially supplies RGB snapshots. Existing House V, Orin identity, mono fusion, and Unitree L2 code are outside the first implementation.

**Rationale**: The user's central task is to train and evaluate a LEGO piece detector or segmenter against human truth. Reusing a spatial viewer and multi-sensor fusion service would add dependencies without improving the first controlled benchmark. A standalone codebase makes its taxonomy, dataset, training runs, and findings reviewable as an ML project.

**Alternatives considered**: Add training panels to House V (ties the experiment to a live camera app); start with L2/depth fusion (unneeded for the first RGB piece task); modify the current COCO model in place (incorrect taxonomy and deployment coupling).

## Capture and annotation

**Decision**: Import OAK 4 RGB stills first; synthetic fixture images support local tests. Store originals outside Git with SHA-256, source, capture time, resolution, settings, scene/layout group, and board protocol version. Use human-reviewed boxes or polygons per visible instance, with color and footprint labels and an `unknown` option. Keep annotation revisions separate from originals.

**Rationale**: Actual model training needs labeled images, not only OAK metadata. A still-image path is simpler to audit and avoids imposing streaming/synchronization requirements. A model checkpoint is separate from a camera snapshot and a prediction snapshot.

**Alternatives considered**: Record video first (more duplicate frames and labeling burden); infer labels from current OAK COCO detections (not ground truth); store only crops (can lose separation and context).

## Board protocol

**Decision**: Start with approximately 20 inventoried mixed-color and mixed-size pieces. Shake them flat on a board, then check/adjust so none touch or overlap. Record actual count, lighting, camera pose/distance, board dimensions, setup photo, and piece-level labels. Repeat layouts and rotate pieces in-plane. Progress to stages with one changed factor: count, smaller gap, touching, overlap/occlusion, or lighting.

**Rationale**: Separated pieces provide a tractable first benchmark. Orientation invariance can be tested on labeled rotations without changing the truth identity. Progressive stages reveal which condition causes an error. A baseline scene with contact is marked invalid or assigned to a harder stage.

**Alternatives considered**: Dense pile as the first task (ambiguous and confounded); arbitrary scene images with no setup metadata (hard to reproduce); pool all stages into one score (hides failure modes).

## Model path and training comparison

**Decision**: Choose a suitable pretrained instance detector or segmenter as the primary baseline and fine-tune it on reviewed LEGO data. Consider a same-architecture from-scratch run with matched split, augmentation, training budget, and evaluation when the dataset is sufficiently large. Select and pin the framework after checking task fit, hardware, and license. An Ultralytics YOLO experiment is a provisional candidate: its [training](https://docs.ultralytics.com/modes/train), [instance-segmentation dataset](https://docs.ultralytics.com/datasets/segment), and [validation](https://docs.ultralytics.com/modes/val) documentation provide a concrete path, but this plan does not lock in its current release.

**Rationale**: Fine-tuning is a useful starting experiment with limited labeled data; scratch training asks whether the dataset supports learning without pretrained features. Those are different experiments, not interchangeable labels. Real metrics must come from the frozen held-out set.

**Alternatives considered**: Training from scratch alone (likely data-hungry; no pretrained comparison); only run the existing OAK COCO model (no LEGO-specific learning); claim a training result from configured YAML or snapshots (no model training occurred).

## Dataset and evaluation

**Decision**: Freeze train/validation/test by entire layout/scene group, including adjacent images and orientation variants. Export format-specific labels from a canonical human-reviewed annotation manifest. Record dataset, label revision, taxonomy, random seeds, initial weights, model config, code version, compute, and checkpoint hash. Evaluate matched candidate and baseline predictions on the identical frozen test set.

**Rationale**: Frame-level random splits leak scene appearance. Canonical labels preserve provenance if frameworks change. Built-in mAP alone is insufficient for the user goal: report piece count error, per-instance precision/recall and IoU or mask IoU, color and footprint confusion, contact/split/merge errors, orientation strata, and stage breakdowns with denominators. The [Ultralytics dataset format](https://docs.ultralytics.com/datasets/detect) illustrates train/val/test manifests and class mappings, but the canonical record should not be framework-specific.

**Alternatives considered**: Tune against held-out test (invalid comparison); report only aggregate mAP (misses count/color/size and orientation); let export rewrite truth (loses annotation history).

## Dashboard and storage

**Decision**: Keep core operations runnable from CLI; add a local image/run browser only if it materially improves review after the pipeline works. Show unavailable metrics as unavailable. Store raw images, reviewed labels, weights, and predictions in a configurable local/Orin data root outside Git; commit schemas, code, synthetic fixtures, protocol, and safe summary findings.

**Rationale**: The user wants an inspectable CV and ML project, not just documents. CLI reproducibility makes the result testable; a later UI can help visual review. A content hash makes references stable without committing private imagery.

**Alternatives considered**: UI-only workflow (hard to automate/reproduce); Git LFS by default (still publishes imagery and weights); mutable single results file (obscures which training run produced an output).

## Optional OAK deployment

**Decision**: Keep trained models off-device until measured evaluation justifies an RVC4 conversion experiment. [Luxonis model conversion guidance](https://docs.luxonis.com/software-v3/ai-inference/conversion) and [NN Archive format](https://docs.luxonis.com/software-v3/ai-inference/nn-archive) document distinct compatibility steps. Conversion, package integration, device FPS/accuracy check, and rollback are separate gated tasks.

**Rationale**: A PyTorch checkpoint is not automatically executable on OAK 4. The first valid deliverable is an off-device, reproducible LEGO recognition benchmark; deployment is optional.

**Alternatives considered**: Automatically package the first checkpoint (no format or performance validation); keep current COCO OAK model as a mandatory base (the custom task may use different weights and labels).

## Open measurements

- Confirm OAK still-image capture API and exact source metadata on the installed unit before claiming device integration. Imported fixture images enable local development first.
- Measure real annotation agreement/quality and dataset size before deciding whether a scratch run is informative.
- Measure Orin and/or workstation train time, memory, inference latency, and actual test accuracy. No numbers are predicted here.
