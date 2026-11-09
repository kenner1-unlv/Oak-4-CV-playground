# Proposed Local Workflow Contract

This is a design contract for the standalone LEGO CV lab, not a claim that commands currently exist. The core workflow is CLI reproducible and can later be wrapped by a local browser. Commands below state expected behavior; exact executable names are implementation choices.

| Operation | Inputs | Outputs and validation |
| --- | --- | --- |
| `import-images` | OAK snapshot files plus source/device metadata, capture times, scene group and board protocol | Immutable image hashes, dimensions, import manifest, explicit missing metadata. Duplicate hashes may reference one asset but retain distinct capture records. |
| `scene create/review` | Board setup, actual inventory/count, stage/changed condition, images | Versioned scene record and baseline eligibility. Contact/overlap blocks `separated_flat` eligibility. |
| `annotate` | Image, per-piece box or polygon, color, footprint, optional orientation/part ID, reviewer | New annotation revision; source image unchanged. Invalid/out-of-bounds geometry rejected. |
| `dataset validate/export` | Reviewed annotation revision, taxonomy, export format | Completeness report and format-specific image/label files. A counted piece without reviewed geometry/required labels blocks export. |
| `split freeze` | Dataset manifest and whole scene/layout/session groups | Versioned train/validation/test manifest and frozen test hash; overlap rejected. |
| `train` | Frozen split, pretrained checkpoint or scratch initialization, architecture, config, seed, compute | Run manifest, logs, resource/budget record, checkpoint hash; interrupted run marked incomplete. |
| `predict` | Model artifact and frozen images, threshold/config | Versioned prediction set with per-image outputs; no source or truth mutation. |
| `evaluate` | Prediction set(s), same frozen test manifest and truth, matching policy | Per-image and stage/orientation metrics with denominators, comparison report hash. Reject differing test membership for controlled comparison. |
| `findings export` | Completed report | Git-safe summary without raw images or weights; identifies data/model/config/scene provenance and limits. |

## State and evidence rules

- `pretrained_fine_tune` and `scratch` are separate strategies. A controlled comparison uses the same architecture, held-out test membership, and stated training budget; any difference must be shown in the report.
- Model state is `experimental`, `converted`, `oak_tested`, `deployed`, or `unknown`. Local training and prediction only establish `experimental`. Conversion and physical OAK tests require separate evidence.
- Snapshot means an original RGB image or a saved model prediction tied to it, with the type explicit. Neither is a trained checkpoint.
- Local tooling must verify hashes before trusted export or evaluation and fail with a specific reason on missing/corrupt files.
- No raw data or trained weights are written to the Git worktree by default. A configurable data root and an output review step control shareable findings.
