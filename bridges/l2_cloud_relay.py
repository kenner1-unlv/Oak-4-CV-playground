"""Expose a recent Unitree L2 ROS cloud to the House V browser.

This bridge runs on the Orin. It deliberately serves raw, uncalibrated points;
the browser makes an approximate projection for a first-look overlay.
"""

import json
import math
import os
import signal
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2


PORT = int(os.environ.get("L2_RELAY_PORT", "8770"))
HOST = os.environ.get("L2_RELAY_HOST", "127.0.0.1")
STRIDE = max(1, int(os.environ.get("L2_RELAY_STRIDE", "2")))
state_lock = threading.Lock()
latest = None


def on_cloud(cloud: PointCloud2) -> None:
    global latest
    fields = {field.name: field.offset for field in cloud.fields}
    if not {"x", "y", "z"} <= fields.keys() or cloud.is_bigendian:
        return
    points = []
    for index in range(0, cloud.width * cloud.height, STRIDE):
        offset = index * cloud.point_step
        xyz = [struct.unpack_from("<f", cloud.data, offset + fields[axis])[0]
               for axis in ("x", "y", "z")]
        if all(math.isfinite(value) for value in xyz):
            points.append([round(value, 3) for value in xyz])
    record = {
        "frame_id": cloud.header.frame_id,
        "stamp_ns": cloud.header.stamp.sec * 1_000_000_000 + cloud.header.stamp.nanosec,
        "received_ms": round(time.time() * 1000),
        "source_points": cloud.width * cloud.height,
        "stride": STRIDE,
        "points": points,
    }
    with state_lock:
        latest = record


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/scan":
            self.send_error(404)
            return
        with state_lock:
            record = latest
        body = json.dumps(record or {"points": []}, separators=(",", ":")).encode()
        self.send_response(200 if record else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        pass


def main() -> None:
    rclpy.init()
    node = rclpy.create_node("housev_l2_relay")
    node.create_subscription(PointCloud2, "/unilidar/cloud", on_cloud,
                             qos_profile_sensor_data)
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    def stop_server(_signum, _frame) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop_server)
    signal.signal(signal.SIGINT, stop_server)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
