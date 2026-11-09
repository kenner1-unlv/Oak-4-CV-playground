# Data Model: LEGO CV Lab

All persistent records have `schema_version` and stable IDs. The canonical annotation format is independent of the selected training framework. Large image and weight files live in a configurable data root outside Git; manifests use content hashes and relative paths.

## CaptureSession and ImageAsset

`CaptureSession`: `session_id`, human name, source (`oak4`, `imported`, other), `scene_group_id`, board protocol/version, stage, setup note, camera ID/settings if known, operator, start/end times, state (`open`, `complete`, `incomplete`), image count, and missing/corrupt count. Capture is explicit; an import creates a session with original source metadata retained.

`ImageAsset`: `image_id`, session/scene group, relative path, SHA-256, bytes, width/height, media type, source capture timestamp and clock domain if known, ingest timestamp, camera/exposure/focus settings if known, source identity, and integrity state (`verified`, `metadata_incomplete`, `missing`, `corrupt`). An unknown capture timestamp remains null and is not replaced with ingest time; such an image is visible but not accepted into a trusted OAK dataset until provenance is repaired. Original images are immutable.

## BoardScene and PieceTruth

`BoardScene`: `scene_id`, layout/group ID, protocol version, board dimensions/reference image, source image IDs, actual inventory/count, camera pose/distance, lighting, shake and placement notes, stage (`separated_flat`, `increased_count`, `narrow_gap`, `touching`, `overlap`, `occlusion`, `lighting_change`), changed variable/value, baseline eligibility, and reviewer/time. The separated baseline uses around 20 known pieces, flat with no touching or overlap after the shake. A failed eligibility check cannot be silently relabeled as baseline.

`PieceTruth`: `piece_instance_id`, scene/image ID, annotation revision, color category, size/footprint category, optional measured dimensions/stud count, optional verified commercial part ID, box and/or polygon in original image coordinates, orientation if measured, visibility, contact/overlap flag, label uncertainty, and human reviewer. Count is derived from visible eligible instances. In-plane rotation does not change a piece's color or footprint truth. Unknown color/size is valid but excluded from that category's accuracy denominator with the exclusion reported.

## AnnotationRevision and Taxonomy

`AnnotationRevision`: immutable revision ID, parent revision, image/scene, author, timestamp, changed PieceTruth records, review state (`draft`, `reviewed`, `rejected`), and reason. Editing creates a new revision; raw images remain unchanged.

`Taxonomy`: versioned piece presence class, color vocabulary, footprint/size vocabulary and measurement rule, unknown/ambiguous states, and optional part identity namespace. Detection/segmentation training may use a single `piece` class; color and size predictions are separately scored and may be separate heads or post-processing. The dataset export records the mapping used.

## DatasetManifest and Split

`DatasetManifest`: dataset ID/version, source image hashes, reviewed annotation revision IDs, taxonomy ID, eligibility/exclusion decisions, export format/version, and manifest hash.

`Split`: split ID, dataset hash, grouping key (`scene_group_id`), sorted train/validation/test group IDs, frozen test membership hash, random seed/selection method, creation time, state (`draft`, `frozen`). An image/layout group cannot appear in more than one partition. Orientation variants and nearby captures from one layout share a group. Changes create a new split version.

## ModelRun, ModelArtifact, PredictionSet, Finding

`ModelRun`: run ID, task (`detection`, `instance_segmentation`, optional color/footprint classification), strategy (`pretrained_fine_tune`, `scratch`), architecture/framework/version, initial weights identity or random initialization, dataset/split/taxonomy hashes, augmentation, seed, hyperparameters, code revision, compute device, start/end/duration, status, logs, and measured resources. A scratch comparison is marked exploratory if data or compute is insufficient for a matched study.

`ModelArtifact`: artifact ID/hash, path, run ID, task, input shape/transform, output classes/semantics, format, validation status, and optional later RVC4 conversion/deployment records. A configured OAK YAML reference is not a LEGO-trained artifact.

`PredictionSet`: prediction ID/hash, model artifact, dataset/split, threshold and inference configuration, image IDs, per-instance boxes/masks, piece scores and optional color/footprint outputs, execution mode (`off_device_test`, `oak_device_test`), and timestamp. It is output evidence, not a checkpoint.

`Finding`: Git-safe report ID/hash, benchmark protocol and stages, ground-truth method, dataset/split/annotation and model/configuration hashes, hardware, verification level (`synthetic_fixture`, `physical_board`, `device_inference`), metric numerators/denominators and per-stage/orientation breakdown, observed errors, and limitations. It contains no source imagery or weights.

## Metric record

For every metric store `name`, `value`, `numerator`, `denominator`, unit, matching/IoU threshold where applicable, excluded/unknown counts, scene/stage/orientation grouping, and model/prediction set. Required families: absolute count error (and exact-count rate), instance precision/recall and box/mask IoU, color confusion, footprint confusion, separated/touching split or merge errors, and runtime latency. A metric with zero eligible denominator is `unavailable`, not zero accuracy.

## Relationships and integrity

- Session owns images; board scene references images and human truth; annotation revisions never modify image bytes.
- Dataset manifest selects reviewed truth and images; split freezes whole scene groups; run references exact manifest and split; prediction set references exact model and images; finding references all upstream hashes.
- A missing or hash-mismatched image, label, or weight is excluded from trusted evaluation with a stated reason.
- Training and inference outputs remain outside Git. The small `Finding` record and protocol can be committed after private-content review.
