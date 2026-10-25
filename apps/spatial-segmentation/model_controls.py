"""Small same-origin web control panel for live YOLO parser thresholds."""

import json
import http.client
import logging
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


LOG = logging.getLogger("oak4-perception.controls")
PAGE = Path(__file__).with_name("model_controls.html")


class SceneState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: dict = {"frame_id": None, "objects": []}
        self._wall_time = 0.0

    def publish(self, scene: dict) -> None:
        with self._lock:
            self._latest = scene
            self._wall_time = time.monotonic()

    def read(self) -> dict:
        with self._lock:
            return {**self._latest,
                    "age_ms": round((time.monotonic() - self._wall_time) * 1000)
                    if self._wall_time else None}


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
                 ir_projector: IRProjectorControl | None = None):
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
            elif self.path in ("/", "/index.html"):
                self.respond(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            else:
                self.proxy_viewer()

        def do_PUT(self) -> None:
            if self.path not in ("/api/model", "/api/ir"):
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
                elif ir_projector is not None:
                    result = ir_projector.apply(payload)
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
                         port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port),
                                 make_handler(ModelControls(
                                     parser, config_queue, config_factory
                                 ), scene_state=scene_state,
                                 mono_frames=mono_frames,
                                 ir_projector=ir_projector))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    LOG.info("Live model controls listening on port %s", port)
    return server
