"""Small same-origin web control panel for live YOLO parser thresholds."""

import json
import http.client
import logging
import math
import os
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


LOG = logging.getLogger("oak4-perception.controls")
L2_RELAY_HOST = os.environ.get("ORIN_L2_RELAY_HOST", "192.168.50.2")
IDENTITY_HOST = os.environ.get("ORIN_IDENTITY_HOST", "192.168.50.2")
PAGE = Path(__file__).with_name("model_controls.html")
ASSETS = {
    "/housev.css": (Path(__file__).with_name("housev.css"), "text/css"),
    "/housev.js": (Path(__file__).with_name("housev.js"), "text/javascript"),
}


class SceneState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: dict = {"frame_id": None, "objects": []}
        self._wall_time = 0.0
        self._result_times = deque(maxlen=90)

    def publish(self, scene: dict) -> None:
        with self._lock:
            self._latest = scene
            self._wall_time = time.monotonic()
            self._result_times.append(self._wall_time)

    def read(self) -> dict:
        with self._lock:
            now = time.monotonic()
            recent = [stamp for stamp in self._result_times
                      if now - stamp <= 1.5]
            result_fps = ((len(recent) - 1) / (recent[-1] - recent[0])
                          if len(recent) >= 2 and recent[-1] > recent[0]
                          else None)
            return {**self._latest,
                    "age_ms": round((now - self._wall_time) * 1000)
                    if self._wall_time else None,
                    "result_fps": round(result_fps, 1)
                    if result_fps is not None else None}


class MonoFrameStore:
    """Latest raw left/right grayscale frames; JPEG only the requested view."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frames = {}

    def publish(self, name: str, frame) -> None:
        with self._lock:
            self._frames[name] = (frame, time.monotonic())

    def jpeg(self, name: str) -> bytes | None:
        if name not in {"left", "right"}:
            return None
        with self._lock:
            saved = self._frames.get(name)
        if saved is None or time.monotonic() - saved[1] > 1.0:
            return None
        import cv2
        ok, encoded = cv2.imencode(".jpg", saved[0],
                                   [cv2.IMWRITE_JPEG_QUALITY, 78])
        return encoded.tobytes() if ok else None


class IRProjectorControl:
    """Last successfully commanded laser-dot state, with bounded intensity."""

    def __init__(self, device) -> None:
        self.device = device
        self.lock = threading.Lock()
        self.enabled = False
        self.intensity = 0.5

    def read(self) -> dict:
        with self.lock:
            return {"enabled": self.enabled, "intensity": self.intensity}

    def apply(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or not payload or set(payload) - {
            "enabled", "intensity"
        }:
            raise ValueError("Specify enabled and/or intensity")
        if "enabled" in payload and not isinstance(payload["enabled"], bool):
            raise ValueError("enabled must be true or false")
        value = payload.get("intensity", self.intensity)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not 0.05 <= value <= 1.0):
            raise ValueError("intensity must be 0.05 to 1.0")
        with self.lock:
            enabled = payload.get("enabled", self.enabled)
            if not self.device.setIrLaserDotProjectorIntensity(
                float(value) if enabled else 0.0
            ):
                raise RuntimeError("IR dot projector did not accept the setting")
            self.enabled = enabled
            self.intensity = float(value)
            return {"enabled": self.enabled, "intensity": self.intensity}


class ZoomControl:
    """Send a movable, fixed-size zoom ROI to the device Script node."""

    def __init__(self, queue, buffer_factory, canvas_size: tuple[int, int],
                 zoom_size: tuple[int, int]) -> None:
        self.queue = queue
        self.buffer_factory = buffer_factory
        self.canvas_size = canvas_size
        self.zoom_size = zoom_size
        self.lock = threading.Lock()
        self.x0 = (canvas_size[0] - zoom_size[0]) // 2
        self.y0 = (canvas_size[1] - zoom_size[1]) // 2

    def read(self) -> dict:
        with self.lock:
            width, height = self.canvas_size
            zoom_w, zoom_h = self.zoom_size
            return {
                "center_x": round((self.x0 + zoom_w / 2) / width, 3),
                "center_y": round((self.y0 + zoom_h / 2) / height, 3),
                "box_xyxy_norm": [self.x0 / width, self.y0 / height,
                                  (self.x0 + zoom_w) / width,
                                  (self.y0 + zoom_h) / height],
            }

    def apply(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or not payload or set(payload) - {
            "center_x", "center_y"
        }:
            raise ValueError("Specify center_x and/or center_y")
        for key, value in payload.items():
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError(f"{key} must be a number from 0 to 1")
        with self.lock:
            width, height = self.canvas_size
            zoom_w, zoom_h = self.zoom_size
            cx = payload.get("center_x", (self.x0 + zoom_w / 2) / width)
            cy = payload.get("center_y", (self.y0 + zoom_h / 2) / height)
            x0 = max(0, min(width - zoom_w, round(cx * width - zoom_w / 2)))
            y0 = max(0, min(height - zoom_h, round(cy * height - zoom_h / 2)))
            message = self.buffer_factory()
            message.setData([x0 & 255, x0 >> 8, y0 & 255, y0 >> 8])
            self.queue.send(message)
            self.x0, self.y0 = x0, y0
        return self.read()


class InferenceRateControl:
    """Gate model passes while leaving camera capture and video unchanged."""

    def __init__(self, queue, buffer_factory, video_fps: int,
                 on_change=None) -> None:
        self.queue = queue
        self.buffer_factory = buffer_factory
        self.video_fps = video_fps
        self.on_change = on_change
        self.fps = min(30, video_fps)
        self.lock = threading.Lock()

    def read(self) -> dict:
        with self.lock:
            return {"fps": self.fps, "video_fps": self.video_fps}

    def apply(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or set(payload) != {"fps"}:
            raise ValueError("Specify fps")
        value = payload["fps"]
        if (isinstance(value, bool) or not isinstance(value, int) or
                not 10 <= value <= min(30, self.video_fps)):
            raise ValueError("fps must be an integer from 10 to 30")
        with self.lock:
            message = self.buffer_factory()
            message.setData([value])
            self.queue.send(message)
            self.fps = value
            if self.on_change is not None:
                self.on_change(value)
            return {"fps": self.fps, "video_fps": self.video_fps}


class ModelControls:
    def __init__(self, parser, config_queue, config_factory) -> None:
        self.values = {
            "confidence": parser.getConfidenceThreshold(),
            "iou": parser.getIouThreshold(),
        }
        self.config_queue = config_queue
        self.config_factory = config_factory
        self.lock = threading.Lock()

    def read(self) -> dict[str, float]:
        with self.lock:
            return self.values.copy()

    def apply(self, payload: dict) -> dict[str, float]:
        if not isinstance(payload, dict) or not payload or set(payload) - {
            "confidence", "iou"
        }:
            raise ValueError("Specify confidence and/or iou")
        for key, value in payload.items():
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError(f"{key} must be a number from 0 to 1")
        with self.lock:
            values = {**self.values, **payload}
            config = self.config_factory()
            config.setConfidenceThreshold(float(values["confidence"]))
            config.setIouThreshold(float(values["iou"]))
            self.config_queue.send(config)
            self.values = values
            return self.values.copy()


def make_handler(controls: ModelControls, viewer_port: int = 8084,
                 scene_state: SceneState | None = None,
                 mono_frames: MonoFrameStore | None = None,
                 ir_projector: IRProjectorControl | None = None,
                 zoom_control: ZoomControl | None = None,
                 inference_control: InferenceRateControl | None = None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format_string: str, *args) -> None:
            LOG.debug(format_string, *args)

        def respond(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def proxy_viewer(self) -> None:
            path = self.path.removeprefix("/viewer") if self.path.startswith(
                "/viewer/"
            ) else self.path
            upstream = http.client.HTTPConnection("127.0.0.1", viewer_port, timeout=5)
            try:
                upstream.request("GET", path)
                response = upstream.getresponse()
                body = response.read()
                self.respond(response.status, body,
                             response.getheader("Content-Type", "application/octet-stream"))
            except OSError as exc:
                LOG.warning("Visualizer proxy error: %s", exc)
                self.respond(502, b"Visualizer unavailable", "text/plain")
            finally:
                upstream.close()

        def do_GET(self) -> None:
            if self.path == "/api/model":
                self.respond(200, json.dumps(controls.read()).encode(),
                             "application/json")
            elif self.path == "/api/scene" and scene_state is not None:
                self.respond(200, json.dumps(scene_state.read()).encode(),
                             "application/json")
            elif self.path == "/api/lidar":
                upstream = http.client.HTTPConnection(L2_RELAY_HOST, 8770, timeout=2)
                try:
                    upstream.request("GET", "/scan")
                    response = upstream.getresponse()
                    self.respond(response.status, response.read(), "application/json")
                except OSError as exc:
                    LOG.debug("LiDAR relay unavailable: %s", exc)
                    self.respond(503, b'{"points":[]}', "application/json")
                finally:
                    upstream.close()
            elif self.path == "/api/identities":
                upstream = http.client.HTTPConnection(IDENTITY_HOST, 8771,
                                                      timeout=2)
                try:
                    upstream.request("GET", "/identities")
                    response = upstream.getresponse()
                    self.respond(response.status, response.read(), "application/json")
                except OSError as exc:
                    LOG.debug("Orin identity service unavailable: %s", exc)
                    self.respond(503, b'{"longest_recent":[],"source_to_global":{}}',
                                 "application/json")
                finally:
                    upstream.close()
            elif self.path.startswith("/api/mono/") and mono_frames is not None:
                name = self.path.removeprefix("/api/mono/").split(".")[0]
                jpeg = mono_frames.jpeg(name)
                if jpeg is None:
                    self.respond(503, b"Mono frame unavailable", "text/plain")
                else:
                    self.respond(200, jpeg, "image/jpeg")
            elif self.path == "/api/ir" and ir_projector is not None:
                self.respond(200, json.dumps(ir_projector.read()).encode(),
                             "application/json")
            elif self.path == "/api/zoom" and zoom_control is not None:
                self.respond(200, json.dumps(zoom_control.read()).encode(),
                             "application/json")
            elif self.path == "/api/inference" and inference_control is not None:
                self.respond(200, json.dumps(inference_control.read()).encode(),
                             "application/json")
            elif self.path == "/training":
                self.send_response(302)
                self.send_header("Location", "/#training")
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
            elif self.path in ("/", "/index.html"):
                self.respond(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path in ASSETS:
                path, content_type = ASSETS[self.path]
                self.respond(200, path.read_bytes(), content_type)
            else:
                self.proxy_viewer()

        def do_PUT(self) -> None:
            if self.path not in ("/api/model", "/api/ir", "/api/zoom",
                                 "/api/inference"):
                self.respond(404, b"Not found", "text/plain")
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.respond(415, b"JSON required", "text/plain")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 256:
                    raise ValueError("Invalid request length")
                payload = json.loads(self.rfile.read(size))
                if self.path == "/api/model":
                    result = controls.apply(payload)
                elif self.path == "/api/ir" and ir_projector is not None:
                    result = ir_projector.apply(payload)
                elif self.path == "/api/zoom" and zoom_control is not None:
                    result = zoom_control.apply(payload)
                elif (self.path == "/api/inference" and
                      inference_control is not None):
                    result = inference_control.apply(payload)
                else:
                    self.respond(404, b"Not found", "text/plain")
                    return
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self.respond(400, str(exc).encode(), "text/plain")
                return
            except RuntimeError as exc:
                self.respond(503, str(exc).encode(), "text/plain")
                return
            self.respond(200, json.dumps(result).encode(), "application/json")

    return Handler


def start_control_server(parser, config_queue, config_factory,
                         scene_state: SceneState, mono_frames: MonoFrameStore,
                         ir_projector: IRProjectorControl,
                         port: int,
                         zoom_control: ZoomControl | None = None,
                         inference_control: InferenceRateControl | None = None
                         ) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port),
                                 make_handler(ModelControls(
                                     parser, config_queue, config_factory
                                 ), scene_state=scene_state,
                                 mono_frames=mono_frames,
                                 ir_projector=ir_projector,
                                 zoom_control=zoom_control,
                                 inference_control=inference_control))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    LOG.info("Live model controls listening on port %s", port)
    return server
