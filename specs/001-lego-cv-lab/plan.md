# Implementation Plan: Standalone LEGO CV Lab

**Planning branch**: `plan/multisensor-ml-workflow` | **Date**: 2026-11-09 | **Spec**: [spec.md](spec.md)

## Summary

Build a focused, reproducible LEGO piece recognition lab. The OAK 4 initially supplies RGB snapshots through repeatable import; acquisition automation may follow. Human-reviewed annotations become a versioned dataset. Train an instance detector or segmenter by fine-tuning suitable pretrained weights, then compare a from-scratch run with disclosed data and budget. Evaluate piece count, instance localization/masks, color, size or footprint, separation, and orientation robustness on frozen scene-grouped test data. A simple local image/run browser is optional once the core CLI workflow works. The proposed implementation home is a separate `lego-cv-lab` repository so the existing OAK spatial viewer remains a distinct project. This planning package lives here until the target repository is established.

## Technical Context

**Language/Version**: Python 3 for capture, annotation export, training, and evaluation; a small web UI may use plain JavaScript or an existing Python UI framework after a prototype. Pin interpreter and package versions in the new repository.

**Primary Dependencies**: Initial capture uses OAK image access only; no existing OAK segmentation pipeline dependency. Training framework is provisional: compare suitability and licensing before selecting a pinned Ultralytics detector or segmenter release. NumPy/OpenCV for image operations, Python test tooling, and a local metadata store are likely.

**Storage**: Local/Orin configurable data root outside Git for source images, labels, weights, and predictions. Git holds code, taxonomy, protocol, schemas, synthetic fixtures, and shareable findings. Immutable image hashes and versioned manifests link them.

**Testing**: Synthetic fixtures for import/capture metadata, annotation validation, scene-group split leakage, metrics, and deterministic report generation; separate real OAK capture and LEGO board trials.

**Target Platform**: Capture on OAK 4 or from imported RGB images; train and evaluate on Jetson Orin or a workstation. RVC4 conversion and camera deployment are optional later work after an off-device model passes a held-out benchmark.

**Project Type**: Standalone CV/ML experiment repository with image import, annotation/dataset tooling, trainer/evaluator, and optional lightweight local review UI.

**Performance Goals**: Start with correct, auditable labels and metrics. Record capture throughput, image resolution, training duration, inference latency, and hardware used; set live-rate targets only after a trained candidate exists.

**Constraints**: Traceable snapshot import, no background recording; no train/test scene leakage; no raw images or weights in Git; no claim that current COCO OAK output recognizes LEGO taxonomy; no automatic OAK deployment.

**Scale/Scope**: Single operator and one board protocol initially. Baseline around 20 known pieces, flat and physically separate after a shake, with progressive challenge stages.

## Constitution Check

*Gate: proposed constitution read before design and rechecked after the design artifacts.*

| Principle | Plan response | Gate |
| --- | --- | --- |
| Measured claims | Reports distinguish fixture, physical trial, pretrained fine-tune, scratch run, and deployed model. | Pass |
| Preserve evidence | Source image, human annotation, derived export, prediction, and report have separate hashes and provenance. | Pass |
| Controlled LEGO benchmark | Baseline and stage eligibility, count/color/footprint and orientation rules are versioned. | Pass |
| Reproducible training and evaluation | Whole board scene/layout groups stay in one split; test membership freezes before tuning; fine-tune/scratch budgets are reported. | Pass |
| Scope and evidence boundaries | No House V/identity/L2 dependency; conversion and physical OAK test are separate states. | Pass |
| Delivery constraints | Private images and weights stay outside Git; code and safe findings remain shareable. | Pass |

**Post-design recheck**: Contracts and validation guide enforce the revised LEGO CV Lab constitution. No exception is requested.

## Project Structure

### Planning artifacts in this repository

```text
specs/001-lego-cv-lab/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── workflow-cli.md
│   └── records.md
└── tasks.md
```

### Proposed implementation in standalone `lego-cv-lab`

```text
lego_cv_lab/
├── capture/        # OAK RGB snapshot import; optional later acquisition
├── dataset/        # manifests, taxonomy, annotation validation, split/export
├── training/       # pretrained fine-tune and from-scratch configurations
├── evaluation/     # count, instance, color, size, orientation, stage reports
└── dashboard/      # optional local snapshot/annotation/run browser
tests/              # synthetic contract, split, and metric fixtures
protocols/          # board setup and progressive challenge definitions
findings/           # Git-safe benchmark summaries
```

**Structure decision**: Separate experiment code and data contracts from the existing spatial-segmentation app. The OAK is an image source initially; the current House V UI, Orin identity bridge, mono detector, DINO embedding, stereo depth, and Unitree L2 relay are neither prerequisites nor sources of claimed LEGO ground truth. The Orin can run training, but a workstation is equally valid. Exact repository creation and remote location are an owner workflow decision.

## Delivery Sequence

1. **Repo and image import**: Establish standalone repo, pinned environment, configurable data root, and repeatable OAK snapshot import. Record image hash, capture time/source, resolution, camera settings, board setup, and scene group. A later direct OAK snapshot command is optional. Do not rely on current mono JPEG/scene polling or existing OAK model outputs.
2. **Taxonomy and truth**: Define piece instance, color category, size/footprint category, unknown/ambiguous labels, and optional verified part ID. Annotate each visible piece with box or polygon; retain original images and annotation revisions separately. Use a manual quality review before export.
3. **Board protocol**: Inventory around 20 mixed pieces. Shake flat, then confirm no pieces touch or overlap. Fix board, camera distance/pose, and lighting; record actual count and scene layout. Repeat orientations and layouts. Add one changed difficulty variable per stage: count, gap, contact, overlap/occlusion, or lighting.
4. **Frozen dataset**: Assign whole board layout/scene groups to train, validation, and held-out test. Freeze and hash membership, taxonomy, and annotation revision. Export detection or instance segmentation labels matching the selected framework. Never split adjacent images or rotated variants of one layout across partitions.
5. **Actual model training**: Fine-tune a suitable pretrained detector or segmenter first as the practical baseline. Run a from-scratch comparison with the same architecture and held-out test examples, stating any differences in training data, augmentation, or budget. Record initial weights/source, random seed, hyperparameters, code commit, device, duration, and output hash. If scratch is underpowered, report it as exploratory rather than a controlled superiority claim.
6. **Evaluation and inspection**: Evaluate on frozen test images with matching thresholds. Produce per-image prediction/truth views and reports: count absolute error, precision/recall and IoU/mask quality, color and size confusion, touching/merge errors, orientation strata, and stage breakdowns with denominators. An optional local UI may browse images, labels, runs, and findings; core results must be CLI reproducible.
7. **Later optional OAK path**: If off-device results justify it, export/convert for RVC4, test input transforms and performance on the exact OAK unit, and separately approve deployment and rollback. This is not required for the first LEGO lab result.

## Integration and Risk Decisions

- The existing model YAMLs are reference examples only. The LEGO model may use entirely different weights and taxonomy. Current COCO output is not a required baseline.
- Color and size may require explicit secondary measurement/classification after instance detection. Evaluate those outputs independently; do not equate a high detection score with correct color or footprint.
- A snapshot is a captured RGB image plus metadata, not a model checkpoint. A training checkpoint and a prediction snapshot are distinct artifacts.
- Variations of the same physical arrangement stay in the same scene group. Rotating a piece does not change its ground-truth color/size class.
- Training on Orin must be measured for resources; a workstation is allowed. Neither route should alter the existing live OAK application.

## Complexity Tracking

No constitution violation. A small local UI may aid human review, while the core image/dataset/training/evaluation pipeline remains CLI-testable.
