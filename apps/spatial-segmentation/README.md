# Spatial segmentation and browser view modes

This RVC4 OAK App runs YOLOv8 Large instance segmentation, aligned stereo
depth, mask-interior XYZ/range measurements, and short-term target tracking.
The House V browser page offers four views without changing the camera's
inference pipeline:

Version 0.9.0 adds two YOLOv6 Nano mono detector passes (same model on left
and right) to the experimental app. The `/training` page uses the same camera
views and shows independent RGB/mono agreement or disagreement beside the
existing Orin global IDs. It does not yet record or train a model; the mono
votes are matched to RGB tracks by timestamp and projected center, so missing
evidence stays unknown. The installed 0.8.15 app is the rollback baseline.

| View | Browser data | Detection toggle |
| --- | --- | --- |
| Color video | 2560×1408 H.264 in a House V viewer powered by DepthAI; spatial field can be main or PiP | Color-aligned mask contours, segmented reticles, and labels on/off |
| Left mono | On-demand JPEG from the left 640×400 grayscale stereo camera | Projected 3D target reticles on/off |
| Right mono | On-demand JPEG from the right 640×400 grayscale stereo camera | Projected 3D target reticles on/off |
| Detections only | JSON target records on a dark, color-camera-aligned canvas | Distance-colored reticles and mask contours are the view |

The mono images have different optical centers and field of view from RGB.
The app transforms each target's measured RGB-frame 3D point into the selected
mono camera using device calibration, then projects a **center marker**. It
does not copy RGB mask pixels onto a mono image. No marker is drawn when range
is unavailable or the projected point is outside the mono image. The mono
view uses raw grayscale JPEGs; minor edge misalignment from lens distortion
remains to be measured.

The IR dot projector defaults to **ON at 0.50 intensity** on this OAK 4 D Pro.
Its on/off button and 0.05–1.0 intensity slider call DepthAI's device API
live. The button reports the last setting accepted by the device; the app does
not measure emitted light. The flood LED is separate and remains untouched.
[Luxonis describes the dot projector](https://docs.luxonis.com/hardware/products/OAK%204%20D%20Pro)
as useful for stereo matching on low-texture surfaces.

## Pipeline

- Model: `luxonis/yolov8-instance-segmentation-large:coco-640x352`, declared
  in [the model YAML](models/yolov8_seg_large.RVC4.yaml). The build bundles
  the model into the `.oakapp` package.
- Video: 2560×1408 H.264 at a 30 FPS target, 60 Mbps encoder target in the
  deployed runtime. Detections only removes the browser Visualizer iframe and
  stops H.264 **delivery to that browser**. The encoder remains in the running
  camera graph for immediate switching back to video.
- Inference: one full 1280×704 RGB frame downscaled into the fixed 640×352
  model input each pass. The full field refreshes at the 30-pass/s target;
  distant/small objects lose detail compared with the earlier 2×2 baseline.
- Depth: stereo left/right plus synchronized color/depth alignment. Valid
  points inside each segmentation mask produce robust XYZ and range; poor
  depth leaves range unknown.
- Tracking: short-term IoU/3D association and accumulated class evidence.
  IDs persist through brief missed detections, without long-term re-identification.
- Controls: live confidence and IoU suppression sliders send
  `DetectionParserConfig` to the native parser. Defaults are 0.25 and 0.50
  after restart.
- Orin feed: optional compact JSON datagrams on UDP port 8766 containing
  timestamps, boxes, IDs, labels, XYZ, range, and track state. No video frames
  or recordings are saved by this app.

See [the architecture](../../docs/architecture.md) for the processing graph,
browser delivery, and result format.

## Build and install from the Orin

With `oakctl` installed and this repository cloned on the Orin, substitute
the addresses for your lab. Build a package and install it; `oakctl app run`
is not this deployment path.

```bash
export OAK_DEVICE=192.168.50.60:9998
export ORIN_WIRED_IP=192.168.50.2
mkdir -p /data/oak4/packages
oakctl app build apps/spatial-segmentation --device "$OAK_DEVICE" \
  --output /data/oak4/packages
oakctl app install /data/oak4/packages/com-sauce-oak4-perception_0-9-0.oakapp \
  --device "$OAK_DEVICE" --force-new --start false --enable false \
  --env ORIN_RESULT_HOST="$ORIN_WIRED_IP" --env OAK4_FPS=30 \
  --env OAK4_SCAN_MODE=full --env OAK4_VIDEO_SCALE=4 \
  --env OAK4_VIDEO_BITRATE_KBPS=60000 --env OAK4_MONO_FPS=10
oakctl app list --format json --device "$OAK_DEVICE"
oakctl app start APP_ID_FROM_LIST --device "$OAK_DEVICE"
```

Close the desktop OAK Viewer before starting this app; both compete for the
camera pipeline. Confirm all views and the Orin result feed, then use
`oakctl app enable APP_ID_FROM_LIST --device "$OAK_DEVICE"` for automatic
start on future boots. The current v0.8.15 lab trial package has SHA-256
`e1d5cfca1d846025ef827ac37eea4efe49458e448dc02a526a8e226a46e32c60`.

## Browser and result checks

The H.264 browser viewer needs a localhost browser context. Forward the page
and WebSocket through the Orin from the development PC:

```powershell
ssh -N -L 127.0.0.1:8082:192.168.50.60:8082 -L 127.0.0.1:8765:192.168.50.60:8765 sauce@192.168.1.2
```

Open `http://127.0.0.1:8082/`. The House V HUD uses the Luxonis decoder under
its color video stage and draws distance-colored target reticles and a spatial panel.
In Color mode, **SPATIAL MAIN / VIDEO MAIN** swaps the large view and the
picture-in-picture without recreating the video iframe. The spatial canvas
can likewise swap with either mono camera. It returns to the target panel in
Detections only mode.
The **YOLO PASS/S** slider gates inference from 10 to 30 passes/s without
changing the 30 FPS video. The header reports measured result passes/s. A
time-based browser filter steadies target position and range across distinct
frames; it does not change the raw Orin result records. The target index shows
the strongest competing class and its share of decayed temporal label evidence
when one exists. This is not a second model probability.
The nearest list can show Orin global IDs when its service is reachable.
**LONGEST IDS** switches the panel to the two longest-observed recent Orin
identities with a live YOLO column. The second model column explicitly remains
pending. See the [Orin identity guide](../../bridges/README.md) and
[issue #2](https://github.com/kenner1-unlv/Oak-4-CV-playground/issues/2).
The L2 toggle draws sampled cyan points from the Orin relay via the same-origin
`/api/lidar` endpoint. This first projection uses an assumed mount orientation
and field of view. It is explicitly uncalibrated and does not assign semantic
labels to LiDAR points. See the [relay guide](../../bridges/README.md).
On mono views, the
independent Detections ON/OFF button controls projected markers. Detections
only displays targets on a dark canvas and disconnects browser video.

On the Orin, use [the result listener](../../scripts/oak4-result-listener.py):

```bash
python3 scripts/oak4-result-listener.py --bind "$ORIN_WIRED_IP" --sample-frames 120
```

## Verification and limits

- Version `0.8.15` is running and enabled for boot on the lab OAK. The earlier
  spatial, tracker, control, mono JPEG, and projection checks passed on the
  Orin; this update was checked for JavaScript syntax, live reticles, the
  vertical-return overhead, nearest-first target-index ordering, and both PiP
  directions with the same live video iframe. The local trial also passed 28
  Orin tests, live 10/20/30 passes/s checks, and left/right mono PiP checks.
  Ten Orin identity tests cover geometric reattachment, simultaneous-track
  separation, service state, camera restarts, and confirmation of new IDs.
  Live reattachments are
  provisional until tested against known object identities.
- The IR dot command succeeded at 0.50 intensity; live off and on commands
  were accepted. Both mono JPEG endpoints returned distinct grayscale frames.
- The browser displayed 2560×1408 color video, left/right mono, an independent
  overlay toggle, Detections only, a live target index, and an X/Z spatial
  panel. A 120-frame Orin sample delivered 30.2 full-scene passes/s with 745
  ranged object records in this room scene.
- The Orin L2 driver published about 12 clouds/s and 250 IMU messages/s.
  A cloud contained about 5,400 points at 32 bytes per point. The browser
  relay sampled every second point. A live page showed a few hundred likely
  vertical returns per scan after the overhead filter and distance-colored
  camera reticles. The target index listed tracked objects in ascending range.
- A 40-poll detection-only HTTP sample on the earlier v0.5.2 baseline averaged
  7.2 KB of scene JSON per response, or 0.473 Mbps of response payload. The
  2560×1408 video view showed 30 FPS and about 56 Mbps in a resolution test.
  These are not controlled accuracy
  measurements or full network accounting.
- Mono marker position is an estimate based on the target's median depth and
  factory camera calibration. Quantitative reprojection error, mask quality,
  class accuracy, range error, and latency remain to be measured. The
  [dense-object experiment](../../docs/experiments.md) is the next benchmark.
