# Lab setup and access

## Physical and network layout

The OAK 4 D Pro and Jetson AGX Orin share a wired subnet through a Linovision
POE-SW508G2 switch. The switch powers the OAK and the TRENDnet TEW-821DAP.
The TRENDnet is set to 5 GHz **Client Bridge** mode, linking the wired
equipment to the existing wireless router for internet and remote SSH access.
The Orin has its own power supply. A development PC can join the wired
subnet for direct access, but it is not required for the camera app to run.

Addresses observed in this lab on 2026-10-25 (change them for another site):

| Endpoint | Address | Use |
| --- | --- | --- |
| OAK wired | `192.168.50.60/24` | `oakctl` at port 9998; browser port 8082 and color video WebSocket 8765 |
| Orin wired | `192.168.50.2/24` | App result receiver on UDP 8766 |
| Orin on home LAN via bridge | `192.168.1.2/24` | SSH from development PC |

The app's camera output does not depend on cloud adoption. The bridge is an
uplink, while camera-to-Orin metadata uses the wired path. Do not copy SSIDs,
passwords, SSH keys, or private device credentials into this repository.

## Device checks

From the Orin, with `oakctl` installed:

```bash
export OAK_DEVICE=192.168.50.60:9998
oakctl device info -d "$OAK_DEVICE" --format json
oakctl app list --device "$OAK_DEVICE" --format json
```

The tested unit reports `OAK4-D R9`, RVC4, Luxonis OS 1.45.0. On the Orin,
`cat /proc/device-tree/model` reports `NVIDIA Jetson AGX Orin Developer Kit`.
The camera OS and current app version can change; read them from the device
before deployment. Use the [app guide](../apps/spatial-segmentation/README.md)
for the build → install → start → enable sequence.

## Browser and metadata

Forward the page and video WebSocket ports. `localhost` provides the browser
context needed by the H.264 color view:

```powershell
ssh -N -L 127.0.0.1:8082:192.168.50.60:8082 -L 127.0.0.1:8765:192.168.50.60:8765 sauce@192.168.1.2
```

Open `http://127.0.0.1:8082/`. The House V page offers color video, left and
right grayscale views, and detections only. A separate detections toggle
controls overlays on each camera view. Mono overlays are projected 3D target
markers, since color mask pixels do not align directly with the mono sensors.
The IR dot projector is enabled at 0.50 intensity by default and can be
changed live. Close the desktop OAK Viewer while the installed app owns the
camera pipeline.

To check the Orin metadata feed:

```bash
python3 scripts/oak4-result-listener.py --bind 192.168.50.2 --sample-frames 120
```

This listener prints frame rate, payload size, ranged-object count, and tile
counts; it does not save video. The camera app sends UDP records only when
`ORIN_RESULT_HOST` is configured at installation.

## OS updates

The camera OS can be checked from the Orin with
[`oak4-update.sh`](../scripts/oak4-update.sh). Set `OAK_DEVICE` and
`OAK_SERIAL` in the shell; the script checks the exact unit before applying
an OTA. `verify` checks a downloaded ZIP without changing the camera.

```bash
export OAK_DEVICE=192.168.50.60:9998
export OAK_SERIAL=YOUR_CAMERA_SERIAL
bash scripts/oak4-update.sh check
bash scripts/oak4-update.sh verify /data/path/full_update_luxonis_ext4-VERSION.zip
```

An update must use an official artifact and uninterrupted PoE power. The
script's `apply` action is a separate deliberate step after verification.
