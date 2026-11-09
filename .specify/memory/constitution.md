# LEGO CV Lab Constitution

**Status**: Proposed principles for the standalone lab; subject to maintainer review.

## Core Principles

### I. Measured Claims

Separate human ground truth, predictions, local evaluation, and physical OAK verification. Accuracy claims identify images, labels, models, metric denominators, conditions, and limits. An attractive overlay is not proof of accuracy.

### II. Preserve Source Evidence

OAK snapshots are immutable source evidence. Annotations, corrections, predictions, dataset splits, and findings have separate provenance and revisions. Later experiments cannot overwrite original images or frozen held-out labels.

### III. Controlled LEGO Benchmark

Begin with roughly 20 varied pieces shaken flat and confirmed separate, non-touching, and non-overlapping. Record the actual count. Keep color and size/footprint rules stable across in-plane rotation. Increase difficulty in named stages and report changed conditions separately.

### IV. Reproducible Training and Evaluation

Keep images from one arrangement or collection session in one split. Freeze held-out test membership before tuning. Compare fine-tuned and from-scratch candidates with stated starting weights, data, budget, and shared test examples. Disclose departures from a controlled comparison.

### V. Scope and Evidence Boundaries

The lab stands independently from House V and Orin identity fusion. Unitree L2 is outside LEGO piece recognition. Local training, model conversion, and physical OAK execution are distinct states and must be labeled accurately.

## Delivery Constraints

Keep raw images, recordings, weights, private scene content, and credentials out of Git. Track code, object taxonomy, safe manifests, reproducible instructions, and evidence-backed findings. Do not claim prepared or local-only work is deployed.

## Development Workflow

Specify benchmark and annotation rules before implementation. Use independent tasks where practical. Validate scoring on labeled fixtures, then verify actual OAK behavior as a distinct gate. Require explicit owner approval before pushing, deploying, or promoting a candidate model.

## Governance

These proposed principles guide the current spec and plan. The maintainer may amend them with a reason and matching plan/test updates. They do not claim prior project ratification.

**Version**: 0.2.0-proposed | **Drafted**: 2026-11-09
