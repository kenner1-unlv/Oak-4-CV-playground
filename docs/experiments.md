# Experiment menu

This repository is for comparing **purpose-built pipelines**, not declaring
one model the final answer. Give each new app its own `apps/<name>/` directory,
task statement, hardware/model configuration, result contract, repeatable
scene, and measured limitations.

The switchable detection-only view is tracked in
[issue #1](https://github.com/kenner1-unlv/Oak-4-CV-playground/issues/1).
An early green depth-edge view was rejected after live inspection; it drew
unhelpful room lines. The current mode retains red target geometry without
those lines. Dense-scene accuracy remains open.

## First benchmark: a dense object pile

A fixed camera and a pile of varied objects make an accessible segmentation
stress test. Start with a sparse arrangement, then add objects and overlap in
repeatable steps. Include small, reflective, dark, similarly colored, and
partially hidden items. Keep lighting, camera pose, and distance recorded.
Place some objects across the four tile boundaries to expose seam behavior.

For each arrangement:

1. Record a scene ID, object inventory, approximate dimensions, positions,
   lighting, and a reference photo. Create a small set of hand-labeled masks
   or outlines and object IDs for objective comparisons.
2. Sweep the live **confidence** and **IoU suppression** sliders while keeping
   the scene fixed. Record the exact values; the app resets them at restart.
3. Count missed objects, false labels, duplicate detections, merged/split
   masks, and label/ID changes over time. Pay special attention to objects
   crossing tile boundaries and to heavy occlusion.
4. Compare predicted masks with the hand labels using per-instance IoU or
   another stated overlap metric. Separate model score from mask quality.
5. Record range availability and repeatability, FPS, network throughput, and
   end-to-end latency. Preserve raw observations and the evaluation script so
   another run can reproduce the summary.
6. Repeat selected scenes with the IR dot projector off and at a recorded
   intensity. Compare depth-valid fraction and distance repeatability, while
   keeping other camera and threshold settings fixed.

Do not infer model accuracy from the current live FPS checks or from a few
visually convincing frames. The same scenes should be rerun when testing a
different model, tile size, threshold, or camera pipeline.

## Fixed lidar reference: preview running, calibration planned

A Unitree L2 in a fixed pose could provide independent range measurements for
the same scenes. Before comparing it with OAK stereo, measure the rigid
camera-to-lidar transform, align the two timestamps, and define which lidar
returns correspond to each visible object or mask. Measure both sensors on
simple targets at known distances first. Then report camera range error,
missing-depth rate, and error versus surface type, distance, and occlusion.

The Orin now relays a sampled L2 cloud into the browser for an unaligned
preview. The camera app does not fuse it with detections or assign labels to
LiDAR points. A rigid camera-to-LiDAR mount, measured spacing and orientation,
and timestamp alignment are still needed before comparing sensors. Treat the
L2 as a separate sensor with its own uncertainty, not automatically perfect
ground truth.

## Candidate apps

| Pipeline | Question to answer | Evidence to collect |
| --- | --- | --- |
| Current spatial segmentation | Which objects are present and where are they in 3D? | Mask quality, class errors, dense-scene recall, range error |
| Current detections-only browser mode | Are target locks useful without receiving H.264 video? | HTTP payload rate, target alignment, stale-data behavior |
| Future room geometry | Can stereo or lidar reveal real wall boundaries without noisy lines? | Hand-marked edge alignment, false edges, missing geometry |
| Alternative inference crops or a second model | Can distant/small objects improve without losing full-scene context? | Recall versus FPS, latency, and network cost |
| Open-vocabulary detection | Can text-specified targets be found reliably in this scene? | Prompt sensitivity, false positives, class coverage |
| Motion/identity tracking | Can an object keep one ID through movement and brief occlusion? | ID switches, recovery time, track fragmentation |
| Stereo/lidar comparison and fusion | When does each sensor provide a reliable distance? | Calibrated error, missing data, synchronization error |

For every candidate, state what runs on the OAK versus the Orin. Keep the
camera result format versioned so later consumers can compare outputs without
assuming that all apps use the same model or sensor mix.

For a future wall overlay, start with a stationary camera and hand-marked room
edges. Compare depth, surface-normal, plane, and eventually lidar cues against
those marks before displaying any wall claim. A 3D map would need pose and
coordinate-frame work. In the current switchable app, Detections only removes
the browser video connection; the camera encoder remains active for instant
switching back to color video.
