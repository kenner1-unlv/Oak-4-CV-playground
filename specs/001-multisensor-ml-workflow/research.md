# Research and Architecture Decisions

**Date**: 2026-11-09 | **Basis**: repository code and docs, proposed constitution, feature spec. The hardware behavior below is a proposed validation path unless explicitly marked as an existing observation.

## 1. Compute and storage owner

**Decision**: Keep real-time OAK inference and House V view on the camera. Make the Orin the durable capture, review, dataset, and evaluation host.

**Rationale**: Current OAK app already produces RGB segmentation, mono detections, stereo range, model state, and compact UDP records. Orin already receives identities and Unitree L2 ROS clouds. Current UDP payload has no images; adding ML evidence requires a separate, opt-in image/crop path. An Orin-side bounded queue and disk service can expose capture health without blocking the camera graph.

**Alternatives considered**: Record everything inside the OAK app (competes with live inference and offers limited durable storage); transfer unbounded H.264 continuously (cost and privacy without explicit capture); rebuild the browser as an Orin application (duplicates the current viewer).

## 2. Source times and synchronization

**Decision**: Preserve original source timestamp, sequence, clock domain, and Orin receipt timestamp for every asset/observation. Store a separate measured alignment record and skew. Pair only when frame identity or validated clock conversion supports it; otherwise state `unmatched` or `offset_unknown`.

**Rationale**: Existing mono JPEG endpoints do not expose source-frame timestamp headers. Scene, identity, and L2 are polled independently, so browser retrieval times are not a synchronized capture. OAK device time, ROS header time, and Orin wall time need an explicit mapping. Source restarts and clock jumps create discontinuities.

**Alternatives considered**: Use nearest wall-clock poll (false pairing); assume OAK and ROS stamps share an epoch (unverified); silently discard missing passes (biased evaluation).

## 3. Durable format and recovery

**Decision**: Immutable content-hashed asset files plus a versioned session manifest and SQLite index. A session is `recording`, `complete`, or `incomplete`; write assets with temporary file and atomic rename, then finalize the manifest. Recover a crash as incomplete, preserving readable assets and gap markers.

**Rationale**: The manifest is portable and auditable; SQLite supports catalog queries and correction history without requiring a database service. Hash checks detect missing or changed artifacts. The index can be rebuilt from manifests if needed. Keep the data root outside Git and configurable.

**Alternatives considered**: Single mutable JSON document (crash and concurrent update risk); raw video only (insufficient model and sensor provenance); large binary assets in Git (size and private scene exposure).

## 4. Model and snapshot catalog

**Decision**: Catalog current OAK model YAML references and installed package metadata, then register future artifact hashes, task, input shape/transform, classes, and provenance. Keep prediction snapshots distinct from model weights and raw capture. Display `unknown` where a historical artifact or metadata is absent.

**Rationale**: The repository has four model YAML references for segmentation, mono detection, DINO appearance, and pose, but not a full model registry or historical training archive. The `.oakapp` bundles resolved models. [Luxonis model conversion guidance](https://docs.luxonis.com/software-v3/ai-inference/conversion) and [NN Archive documentation](https://docs.luxonis.com/software-v3/ai-inference/nn-archive) describe a separate RVC4-compatible conversion and packaging step; an Orin training result is not automatically OAK compatible.

**Alternatives considered**: Infer weights from model names or snapshot output (unreliable); treat an output snapshot as a model artifact (loses provenance); automatically deploy a trained candidate (bypasses device conversion and acceptance).

## 5. First benchmark and label taxonomy

**Decision**: Use a controlled LEGO board as the first recording and evaluation scenario. Baseline approximately 20 pieces with known inventory, flat after a shake, no touching or overlap, and orientation varied. Record piece instance, count, color, size category and dimensions, visibility, and board/scene identifier. Progress to touching, overlap, dense piles, occlusion, and motion only as separate challenge levels. Fix lighting, camera pose, distance, and shake protocol within a benchmark version.

**Rationale**: Independent ground truth and repeatable layouts let the team distinguish generic object detection from the requested piece count/color/size task. Adjacent frames and repeated layouts must remain in one split group. Orientation invariance is measurable only with labeled repeated orientations. Report strict denominators and per-level outcomes; generic COCO detections are not proof of LEGO taxonomy accuracy.

**Alternatives considered**: Start with a dense random pile (many interacting failure modes, ambiguous ground truth); use an unlabeled recording as accuracy evidence (no objective target); random frame split (scene leakage).

## 6. Candidate evaluation

**Decision**: Freeze versioned train/validation/test manifests by whole session or scene group, hash their membership, and run fixed baselines and candidates over identical replay samples. The primary supervised path exports human-reviewed RGB image and instance labels to train a LEGO detector/segmenter on Orin or workstation, evaluating count, localization, color, size, and orientation robustness. A separate Orin association candidate evaluates persistent IDs. Store run configuration, code and model versions, per-scene metrics, latency, denominators, and failures. Keep training, evaluation, shadow mode, model conversion, and deployment as distinct states.

**Rationale**: This enables reproducible comparison and prevents nearby frames from leaking into held-out testing. [Ultralytics training documentation](https://docs.ultralytics.com/modes/train) and [dataset format documentation](https://docs.ultralytics.com/datasets/detect) show a practical custom-image training and train/validation/test export path. Ultralytics is only a provisional framework choice until LEGO task, license, hardware, and benchmark fit are checked. Orin training may contend with live inference, so concurrency needs actual CPU/GPU/memory/thermal measurements before it is allowed.

**Alternatives considered**: Compare separate live runs (different scenes); tune on test set (invalid held-out comparison); background training by default (unmeasured live impact).

## 7. Unitree L2 role and calibration gate

**Decision**: Initially capture L2 as independent, sampled board-plane/scene range context. Store ROS stamp, frame ID, source point count, sampling stride, point count, and receipt time. Before camera-to-L2 accuracy claims, require measured rigid transform, time alignment, known-distance reference targets, and point-density/resolution check at the board. Per-piece association is gated separately on demonstrated return density and spatial resolution.

**Rationale**: Current relay is an uncalibrated sampled preview. Apparent overlay alignment is not a measurement. Individual LEGO pieces may be too small or sparse for L2 resolution at the chosen range; that must be tested rather than assumed.

**Alternatives considered**: Treat L2 as ground truth for every piece (unsupported); colorize or label L2 points from camera masks before calibration (false association); exclude L2 entirely (loses useful independent scene geometry and range context).

## Open measurement gates

- Measure OAK image/crop transfer bandwidth, RGB/mono inference rates, Orin CPU/GPU load, storage consumption, and capture drops on the actual devices.
- Measure OAK-to-Orin and ROS-to-Orin clock offsets/drift or use explicit source-frame identity; choose a maximum pairing skew only after data collection.
- Verify model metadata against the installed `.oakapp` and actual source artifacts. Unknown history remains unknown.
- Verify L2 board point density and range repeatability before attempting per-piece matching.
