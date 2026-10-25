# Mode 2: Training Lab

Training Lab is a separate House V mode for collecting and evaluating
cross-camera object identity evidence. Mode 1 remains the live spatial
segmentation viewer. The two modes can share the same color, left mono, right
mono, targets-only, spatial-field, and target-index layout. Training Lab adds
recording, review, and experiment panels; it must label unavailable features
honestly instead of showing fabricated scores.

The [RGB and mono fusion pipeline](mono-fusion-pipeline.md) specifies the live
default view and the camera-to-Orin result contract. Synchronization and ID
fusion continue while recording is off; recording only adds durable capture.

## First research question

Can an Orin fusion model keep one object ID when RGB segmentation and smaller
detectors on the left and right mono cameras intermittently disagree or lose
the object? The three detector scores are separate observations, not a
probability that may be added or averaged. The initial candidate may be a
conventional association/classification model; reinforcement learning is a
later experiment that requires explicit actions and measurable rewards.

## Viewer layout

| Region | Training Lab behavior |
| --- | --- |
| Main view | Switch color, left mono, right mono, and targets-only; preserve the existing video/spatial PiP. |
| Track panel | Show one provisional Orin ID, current class, range, and RGB/left/right observations with timestamps and model versions. Mark missing observations as missing. |
| Review controls | For selected observations, record `same object`, `different object`, `wrong class`, or `uncertain`. Permit correction of the class and of a track split/merge. |
| Capture bar | Start/stop a named recording session and show elapsed time, frame counts, disk usage, dropped samples, and synchronization status. |
| Experiment panel | Select a frozen dataset split and candidate model; show validation and held-out test metrics alongside the current tracker. Training and deployment are distinct actions. |

The current second-model placeholder remains a placeholder until a real mono
model produces observations. Do not display the RGB model's alternate class
vote as though it came from a second model.

## Capture contract

The OAK continues real-time inference and streaming. The Orin records only
when a session is explicitly started. Each sample needs a session ID, scene
ID, camera/pose/lighting notes, synchronized device timestamps, camera socket,
calibration identifier, model identifier, input dimensions and transforms,
raw detector scores, geometry, and provisional/final track IDs. Keep the
source images or crops required for later human review and reprocessing;
metadata alone cannot support retraining a detector. Record dropped or
unmatched frames instead of silently pairing nearby observations.

The Orin stores corrections separately from raw observations so a later
candidate can be evaluated against the original capture. Capture manifests
must reference immutable files and hashes; model predictions and human labels
need separate provenance.

## Train, validate, test

1. Build recordings with sparse and dense scenes, movement, occlusion, changes
   in lighting, and objects near image boundaries. Add deliberate track loss
   and return cases.
2. Assign whole recording sessions (or object/scene groups) to train,
   validation, and test. Adjacent frames of the same scene cannot cross a
   split. Freeze and version the test manifest before tuning.
3. Start with a lightweight Orin association model using RGB/mono class
   evidence, geometric consistency, depth, time gap, and optional appearance
   features. Compare it with the existing tracker on the same recordings.
4. Report ID switches, false merges, fragmentation, recovery after occlusion,
   class accuracy, depth availability, calibration of any fused score, and
   inference latency. Break out hard scenes rather than hiding them in one
   aggregate number.
5. Run a candidate in shadow mode on live data. Promote it only after the
   frozen test and live latency checks pass. Preserve the previous model for
   rollback.

Training may compete with live inference for Orin GPU, memory, and thermal
capacity. Measure this on the actual Orin before enabling background training.
If contention is material, queue training for an idle period while capture
and inference continue.

## Reinforcement experiment, after a labeled baseline

A policy could choose among `keep ID`, `split ID`, `merge with earlier ID`, or
`request another mono inference`. A replay environment would provide
observations from recorded sequences and score correct persistent IDs while
penalizing false merges, ID churn, extra inference, and late decisions. Human
labels and a fixed evaluation split anchor the reward. Agreement among the
camera models alone is not a ground-truth reward and must not silently retrain
the live detector.

## Implementation boundary

Mode 1's OAK app is the source of current RGB detections, stereo range, and
camera views. The first Training Lab increment should add an Orin recording
service and a separate `/training` viewer route that consumes the same live
scene feed. Left/right mono detections, dataset review, fusion training, and
RL policy training are successive increments, each gated by recorded evidence
and measured performance. No training or mono YOLO inference is implemented by
this design document.
