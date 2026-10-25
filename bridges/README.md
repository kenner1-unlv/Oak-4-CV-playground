# Unitree L2 browser relay

The camera app continues to process RGB, stereo depth, and detections on the
OAK. On the Orin, `l2_cloud_relay.py` subscribes to the existing ROS 2
`/unilidar/cloud` topic and exposes a sampled JSON scan over HTTP. The camera
page proxies that feed at `/api/lidar`, so the browser uses its existing
`8082` connection. The relay does not label or fuse points.

The first overlay assumes LiDAR +X forward, +Y left, and +Z up and uses an
approximate camera field of view. It is explicitly **uncalibrated**. The cyan
points are a visual preview only; the distance-colored target reticles and
ranges still come from the OAK. Do not interpret apparent overlap as a
geometric match.
The browser retains each unique LiDAR scan for 250 ms with a gradual fade;
polling the same scan twice does not refresh its lifetime.
The overhead uses 0.35 m ground-plane cells and keeps columns with returns in
at least three distinct 0.25 m height bands. This filters many floor and
ceiling returns while retaining likely vertical faces, but it is not a
calibrated plane or wall detector. Horizontal LiDAR distance colors those
overhead points from red near the sensor to cyan at 8 m or more.

For this lab, the Unitree ROS 2 launch file in `/data/ros_ws` uses LiDAR
`192.168.50.62`, Orin `192.168.50.2`, and UDP port `6201`. The
[Unitree L2 SDK2](https://github.com/unitreerobotics/unilidar_sdk2) supplies
the ROS 2 package and is not vendored in this repository. Start its driver
before the relay. The relay can run independently of the other robot nodes:

```bash
source /opt/ros/humble/setup.bash
source /data/ros_ws/install/setup.bash
export ROS_DOMAIN_ID=0 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ros2 launch unitree_lidar_ros2 launch.py
```

In a second shell on the Orin:

```bash
source /opt/ros/humble/setup.bash
source /data/ros_ws/install/setup.bash
export ROS_DOMAIN_ID=0 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
L2_RELAY_HOST=192.168.50.2 python3 /data/oak4/l2_cloud_relay.py
```

The camera app uses `ORIN_L2_RELAY_HOST=192.168.50.2` by default. If the
relay is absent, the camera and target views continue to work and the page
shows `L2 OFFLINE`. The L2 toggle only affects browser drawing.

The current lab driver and relay were started as transient user services.
They run independently of the Orin's full robot bringup and need to be
started again after a reboot.

## Provisional Orin identities

`orin_identity.py` listens for the OAK result datagrams on the Orin's wired
`192.168.50.2:8766` and serves `/identities` on port `8771`. It preserves
global numbering and identity summaries in `/data/oak4/identity-state.json`.
House V accesses it through the camera app's same-origin `/api/identities`
proxy. Camera track IDs can be reattached to a recent global ID using 3D
distance, image overlap, class, and elapsed time. The restart path allows a
longer gap only with stricter geometry. A genuinely new ID requires three
continuous observations spanning at least 0.35 seconds, so short false
detections do not consume global ID numbers. Matching scores are heuristics, not
probabilities, and no appearance model is running yet.

Run it on the Orin independently of the full robot bringup:

```bash
python3 /data/oak4/orin_identity.py
```

The **LONGEST IDS** panel shows two
recent global IDs by accumulated observed time, with YOLO in the first model
column. The spatial baseline's second column remains pending; the Training Lab
view shows real left/right mono evidence. See
[issue #2](https://github.com/kenner1-unlv/Oak-4-CV-playground/issues/2).

# Boot service for the identity feed

The v0.9.0 trial uses the checked-in
[`housev-identity.service`](systemd/housev-identity.service). Copy it to
`~/.config/systemd/user/housev-identity.service` on the Orin, then run
`systemctl --user daemon-reload` and
`systemctl --user enable --now housev-identity.service`. With user lingering
enabled, the Orin starts the identity endpoint after reboot. The Unitree L2
relay has a separate service and is not made persistent by this unit.
