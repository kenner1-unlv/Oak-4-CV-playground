# Proposed Record Contracts (v1)

Records have `schema_version: 1` and are independent of any one trainer. Values below are illustrative. Canonical source/annotation manifests remain outside Git when they reveal private imagery or locations; synthetic fixtures and safe findings may be committed.

## OAK source image

```json
{
  "schema_version": 1,
  "image_id": "sha256:...",
  "source": "oak4",
  "device_id": "operator-recorded-id",
  "captured_at": "2026-11-09T20:00:00Z",
  "capture_clock": "device-or-host-identified",
  "ingested_at": "2026-11-09T20:01:00Z",
  "width": 1920,
  "height": 1080,
  "sha256": "...",
  "relative_path": "images/sha256/....jpg",
  "scene_id": "scene-01",
  "scene_group_id": "layout-01",
  "camera_settings": {"exposure": null, "focus": null}
}
```

An unavailable source capture time is `null` and an explicit metadata gap; it is not replaced with ingestion time. Such an image is `metadata_incomplete` and cannot be accepted into a trusted OAK dataset until the missing provenance is supplied. Image bytes are immutable. A hash mismatch marks the image untrusted.

## Scene and annotation

The scene record holds protocol version, board dimensions, camera pose/distance, lighting, shake procedure, actual count, stage, changed condition, and `baseline_eligible`. For the separated baseline, all counted pieces must be flat, visible under the documented inclusion rule, and not touching or overlapping.

Each piece annotation holds `piece_instance_id`, original-image box or polygon coordinates, color category, footprint/size category, optional orientation and part ID, visibility/truncation, uncertainty, reviewer, and revision. Human truth and model predictions are separate record types. Unknown color/footprint values are permitted but reported as excluded from that metric denominator. Exact commercial part identity is optional.

## Frozen split and model run

The split record names dataset/annotation/taxonomy hashes and sorted whole scene-group IDs for `train`, `val`, `test`, plus a frozen test membership hash. A group in multiple partitions is invalid. A model run names `strategy` (`pretrained_fine_tune` or `scratch`), architecture/framework version, starting weights hash or random initialization, training image count, split hash, augmentation, seed, epochs/steps, batch size, compute device, wall time, code revision, status, and checkpoint hash. Interrupted status cannot be reported as completed training.

## Prediction and finding

A prediction set names model artifact, image IDs, inference thresholds, input transform, and per-piece boxes/masks plus optional color/footprint outputs. An output confidence is a model score, not human truth. It records execution level (`local`, `oak_physical`) separately from model state.

A finding names protocol/stage and changed condition, truth method, test membership, baseline and candidate model hashes, matched or differing training budgets, hardware, metrics with numerator/denominator and exclusions, per-scene/stage/orientation breakdown, error examples by image ID, and limitations. The Git-safe export omits raw images, weights, private absolute paths, and credentials.

## Metric contract

- Count: truth count, predicted count, absolute error, missed and extra instances, exact-count rate across scenes.
- Localization: matching policy and threshold, true/false positives, false negatives, precision/recall, box IoU and mask IoU when masks exist.
- Attributes: color and footprint confusion/counts on matched pieces with known labels; no fake zero for unknown labels.
- Separation: split and merge errors, with touching/overlap stage named.
- Robustness: per-stage and orientation-stratum results; keep the truth taxonomy unchanged under in-plane rotation.
- Every metric carries eligible denominator, excluded count, model/prediction set, and truth/split hashes. Zero eligible denominator means `unavailable`.
