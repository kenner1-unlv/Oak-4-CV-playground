# Spatial segmentation and browser view modes

This RVC4 OAK App runs YOLOv8 Large instance segmentation, aligned stereo
depth, mask-interior XYZ/range measurements, and short-term target tracking.
The House V browser page offers four views without changing the camera's
inference pipeline:

| View | Browser data | Detection toggle |
| --- | --- | --- |
| Color video | 1920×1056 H.264 in Luxonis Visualizer | Color-aligned mask, box, and label annotations on/off |
| Left mono | On-demand JPEG from the left 640×400 grayscale stereo camera | Calibrated 3D target-center markers on/off |
| Right mono | On-demand JPEG from the right 640×400 grayscale stereo camera | Calibrated 3D target-center markers on/off |
| Detections only | JSON target records on a dark, color-camera-aligned canvas | Red tracked masks and boxes are the view |

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
- Video: 1920×1056 H.264 at a 30 FPS target, 40 Mbps encoder target in the
  deployed runtime. Detections only removes the browser Visualizer iframe and
  stops H.264 **delivery to that browser**. The encoder remains in the running
  camera graph for immediate switching back to video.
- Inference: one 640×352 quadrant of a 1280×704 color inference canvas per
  frame. Four passes cover the image; each region refreshes about 7.5/s.
- Depth: stereo left/right plus synchronized color/depth alignment. Valid
  points inside each segmentation mask produce robust XYZ and range; poor
  depth leaves range unknown.
- Tracking: short-term IoU/3D association and accumulated class evidence.
  IDs persist between quadrant visits, without long-term re-identification.
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
oakctl app install /data/oak4/packages/com-sauce-oak4-perception_0-5-2.oakapp \
  --device "$OAK_DEVICE" --force-new --start false --enable false \
  --env ORIN_RESULT_HOST="$ORIN_WIRED_IP" --env OAK4_FPS=30 \
  --env OAK4_VIDEO_SCALE=3 --env OAK4_VIDEO_BITRATE_KBPS=40000
oakctl app list --format json --device "$OAK_DEVICE"
oakctl app start APP_ID_FROM_LIST --device "$OAK_DEVICE"
```

Close the desktop OAK Viewer before starting this app; both compete for the
camera pipeline. Confirm all views and the Orin result feed, then use
`oakctl app enable APP_ID_FROM_LIST --device "$OAK_DEVICE"` for automatic
start on future boots. The deployed v0.5.2 package on this lab's Orin has
SHA-256 `76c2b01596eefdfe38aea6a1e7eb529ae774288205ac0f6cb9c82bd1602088f6`.

## Browser and result checks

The H.264 browser viewer needs a localhost browser context. Forward the page
and WebSocket through the Orin from the development PC:

```powershell
ssh -N -L 127.0.0.1:8082:192.168.50.60:8082 -L 127.0.0.1:8765:192.168.50.60:8765 sauce@192.168.1.2
```

Open `http://127.0.0.1:8082/`. The page is branded House V; it embeds the
Luxonis Visualizer only while Color video is selected. On mono views, the
independent Detections ON/OFF button controls projected markers. Detections
only displays red targets on a dark canvas and disconnects browser video.

On the Orin, use [the result listener](../../scripts/oak4-result-listener.py):

```bash
python3 scripts/oak4-result-listener.py --bind "$ORIN_WIRED_IP" --sample-frames 120
```

## Verification and limits

- Version `0.5.2` is running and enabled for boot on the lab OAK. Twenty
  spatial, tracker, control, mono JPEG, and projection tests passed on the Orin.
- The IR dot command succeeded at 0.50 intensity; live off and on commands
  were accepted. Both mono JPEG endpoints returned distinct grayscale frames.
- The browser displayed color video with House V branding, left/right mono,
  a separate overlay toggle, and Detections only. A 120-frame Orin sample
  delivered 30.1 passes/s, 30 per quadrant, with 1,117 ranged object records
  in this room scene.
- A 40-poll detection-only HTTP sample averaged 7.2 KB of scene JSON per
  response, or 0.473 Mbps of response payload. The color video view showed
  about 37 Mbps in an earlier room check. These are not controlled accuracy
  measurements or full network accounting.
- Mono marker position is an estimate based on the target's median depth and
  factory camera calibration. Quantitative reprojection error, mask quality,
  class accuracy, range error, and latency remain to be measured. The
  [dense-object experiment](../../docs/experiments.md) is the next benchmark.
