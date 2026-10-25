# Resolution and scan experiment — 2026-10-25

The earlier v0.5.2 baseline rotated four model crops. This experiment tested
how much of the RGB scene one YOLOv8 Large segmentation pass should see. The model archive has
a fixed **640×352 input**. A larger video stream improves the browser image;
it does not increase the model tensor size. All variants used the same model,
confidence `0.25`, IoU `0.50`, stereo path, and 30-pass/s target.

| Variant | Source region per model pass | Passes per scene sweep | Live result rate | Mean visible/ranged tracks in a short browser sample | Observation |
| --- | --- | ---: | ---: | ---: | --- |
| Earlier 2×2 baseline | 640×352 tile of 1280×704 canvas | 4 | 30.02/s over 300 frames | 10.62 / 10.07 | Small objects retain detail; each region revisited ~7.5/s. |
| 3×3 scan | 640×352 tile of 1920×1056 canvas | 9 | 30.00/s over 300 frames | 10.05 / 9.57 | Tighter crops repeatedly labeled indoor fragments as airplane, kite, and bird. Rejected. |
| Two overlapping left/right crops | 960×528 crop from 1280×704, resized to model input | 2 | 30.39/s over 300 frames after depth fix | 11.60 / 11.50 | Context improved, but overlap made boxes and direct detection counts busy. Rejected as the default. |
| Single full-field pass | 1280×704 canvas downscaled to 640×352 | 1 | 29.99/s over 300 frames | 7.75 / 7.75 | Cleanest geometry and 30 visits/s per object; loses some small-object detail. Selected for the current baseline. |

The first two-pass build returned null range because it expected the model mask
to match the larger source crop. Resampling the 640×352 mask into the matching
RGB-aligned depth region restored range. Synthetic mapping tests and a live
300-frame sample confirmed the correction. The rejected 3×3 run also had 32
direct `airplane` and 23 `kite` labels in one 300-frame sample. A later 2×2
sample had no airplane/kite and one bird label. Those raw class counts are
scene observations, not an accuracy score.

## Higher output video resolution

The browser H.264 stream was raised from 1920×1056 at a 40 Mbps encoder
target to **2560×1408 at a 60 Mbps target**. The Luxonis Visualizer reported
30 FPS network/decode/render and 55.96 Mbps throughput with the two-pass
candidate. The selected single-pass app also starts at 2560×1408 and delivered
30.2 result passes/s over its final 120-frame check. The inference image
remains 1280×704 before downscaling to the 640×352 model input.

## House V UI progression

Version `0.8.3` adds a custom, code-native House V HUD around the video
decoder: compact red target brackets, a live target index, and a top-down X/Z
plot using measured target coordinates. It keeps Color, Left mono, Right mono,
and Targets only modes, independent lock overlays, live model thresholds,
and IR dot intensity. At the tested browser width the camera takes full width
and the target index/map sit below it. The app passed 26 Orin tests and the
frontend JavaScript syntax check.

The camera now runs the v0.8.12 House V spatial preview with segmented
distance-colored reticles, the unaligned Unitree L2 overlay, and a video/spatial
PiP switch. See the [app guide](../apps/spatial-segmentation/README.md) and
[L2 relay guide](../bridges/README.md) for the current deployment and limits.
The v0.5.2 package remains installed but stopped as rollback.

## Limits and next experiment

The room and people changed during these sequential checks, and no hand-labeled
objects or masks were collected. Counts across scan patterns are not
comparable recall measurements. The single-pass result is a deliberate trade:
steadier full-scene context at the cost of far/small-object detail. A separate
higher-input model or a second model/pipeline could revisit distant objects
later without making this first baseline more complicated. Compare both on the
same labeled dense-object arrangement before claiming an accuracy gain.
