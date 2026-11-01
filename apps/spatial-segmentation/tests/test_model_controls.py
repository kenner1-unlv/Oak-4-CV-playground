import json
import sys
import threading
import unittest
from types import SimpleNamespace
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model_controls import (IRProjectorControl, ModelControls, MonoFrameStore,
                            SceneState, ZoomControl, InferenceRateControl,
                            LabModeControl,
                            make_handler)
from feature_state import FeatureState
from pose_state import PoseState
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeParser:
    conf_threshold = 0.25
    iou_threshold = 0.5

    def getConfidenceThreshold(self):
        return self.conf_threshold

    def getIouThreshold(self):
        return self.iou_threshold


class FakeConfig:
    def setConfidenceThreshold(self, value):
        self.confidence = value

    def setIouThreshold(self, value):
        self.iou = value


class FakeQueue:
    def __init__(self):
        self.sent = []

    def send(self, config):
        self.sent.append(config)


class FakeDevice:
    def __init__(self):
        self.commands = []
        self.accept = True

    def setIrLaserDotProjectorIntensity(self, value):
        self.commands.append(value)
        return self.accept


class FakeBuffer:
    def setData(self, value):
        self.data = value


class FakeCropStore:
    def jpeg(self, bbox, timestamp_ns):
        if bbox == [0.1, 0.2, 0.5, 0.7] and timestamp_ns == 123:
            return b"jpeg-crop", 120
        return None


class ModelControlTests(unittest.TestCase):
    def test_pose_state_schedules_only_fresh_tracked_people(self):
        state = PoseState(max_per_second=2)
        state.apply({"enabled": True})
        now = 10_000_000_000
        scene = {"age_ms": 10, "device_timestamp_ns": now,
                 "frame_id": 42, "objects": [
                     {"track_id": 2, "track_state": "tracked",
                      "label": "person", "detector_score": 0.9,
                      "bbox_xyxy_norm": [0.2, 0.1, 0.6, 0.9]},
                     {"track_id": 3, "track_state": "held",
                      "label": "person", "detector_score": 0.9,
                      "bbox_xyxy_norm": [0.1, 0.1, 0.4, 0.8]},
                 ]}
        selected = state.select(scene, now)
        self.assertIsNotNone(selected)
        sequence, item = selected
        self.assertEqual(item["track_id"], 2)
        self.assertIsNone(state.select(scene, now))
        state.set_training(True)
        self.assertFalse(state.read()["enabled"])
        state.set_training(False)
        self.assertTrue(state.read()["enabled"])

    def test_pose_http_get_put_and_validation(self):
        controls = ModelControls(FakeParser(), FakeQueue(), FakeConfig)
        pose = PoseState(skeleton_edges=((0, 1), (1, 2)))
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(controls, pose_state=pose))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/api/pose") as response:
                initial_pose = json.load(response)
                self.assertFalse(initial_pose["requested"])
                self.assertEqual(initial_pose["skeleton_edges"],
                                 [[0, 1], [1, 2]])
            request = Request(base + "/api/pose", data=b'{"enabled":true}',
                              headers={"Content-Type": "application/json"},
                              method="PUT")
            with urlopen(request) as response:
                self.assertTrue(json.load(response)["enabled"])
            request = Request(base + "/api/pose", data=b'{"enabled":1}',
                              headers={"Content-Type": "application/json"},
                              method="PUT")
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_lab_mode_gates_both_mono_models(self):
        queues = [FakeQueue(), FakeQueue()]
        class DinoGate:
            enabled = True
            def set_enabled(self, enabled):
                self.enabled = enabled
        dino = DinoGate()
        mode = LabModeControl(queues, FakeBuffer, dino_state=dino)
        self.assertEqual(mode.read(), {"training": False})
        self.assertEqual(mode.apply({"training": True}), {"training": True})
        self.assertFalse(dino.enabled)
        self.assertEqual([queue.sent[-1].data for queue in queues], [[1], [1]])
        self.assertEqual(mode.apply({"training": False}), {"training": False})
        self.assertTrue(dino.enabled)
        self.assertEqual([queue.sent[-1].data for queue in queues], [[0], [0]])
        for invalid in ({"training": 1}, {"training": "yes"}, {},
                        {"training": True, "other": 1}):
            with self.assertRaises(ValueError):
                mode.apply(invalid)

    def test_feature_state_reports_normalized_positions(self):
        features = FeatureState()
        point = SimpleNamespace(id=7, position=SimpleNamespace(x=320, y=100))
        features.publish("left", 123, [point], (640, 400))
        self.assertEqual(features.read()["left"]["points"], [[7, 0.5, 0.25]])

    def test_thresholds_change_live_and_invalid_values_leave_both_unchanged(self):
        parser = FakeParser()
        queue = FakeQueue()
        controls = ModelControls(parser, queue, FakeConfig)
        self.assertEqual(controls.apply({"confidence": 0.42, "iou": 0.31}),
                         {"confidence": 0.42, "iou": 0.31})
        for bad in ({"confidence": -0.1}, {"iou": float("nan")},
                    {"confidence": True}, {"unknown": 0.5}):
            with self.assertRaises(ValueError):
                controls.apply(bad)
        self.assertEqual(controls.read(), {"confidence": 0.42, "iou": 0.31})
        self.assertEqual(len(queue.sent), 1)
        self.assertEqual((queue.sent[0].confidence, queue.sent[0].iou),
                         (0.42, 0.31))

    def test_http_page_and_api(self):
        controls = ModelControls(FakeParser(), FakeQueue(), FakeConfig)
        rate_queue = FakeQueue()
        inference = InferenceRateControl(rate_queue, FakeBuffer, 30)
        lab_queues = [FakeQueue(), FakeQueue()]
        lab_mode = LabModeControl(lab_queues, FakeBuffer)
        features = FeatureState()
        scene = SceneState()
        scene.publish({"frame_id": 7, "objects": []})
        server = ThreadingHTTPServer(("127.0.0.1", 0),
                                     make_handler(controls, scene_state=scene,
                                                  inference_control=inference,
                                                  lab_mode_control=lab_mode,
                                                  feature_state=features,
                                                  crop_store=FakeCropStore()))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/") as response:
                self.assertIn(b'id="confidence"', response.read())
            with urlopen(base + "/training") as response:
                self.assertIn(b'TRAINING LAB', response.read())
                self.assertEqual(response.geturl(), base + "/#training")
            with urlopen(base + "/housev.css") as response:
                self.assertIn(b".target-card", response.read())
            with urlopen(base + "/housev.js") as response:
                self.assertIn(b"drawHud", response.read())
            request = Request(base + "/api/model", data=b'{"iou":0.7}',
                              headers={"Content-Type": "application/json"},
                              method="PUT")
            with urlopen(request) as response:
                self.assertEqual(json.load(response)["iou"], 0.7)
            with urlopen(base + "/api/model") as response:
                self.assertEqual(json.load(response)["confidence"], 0.25)
            with urlopen(base + "/api/scene") as response:
                self.assertEqual(json.load(response)["frame_id"], 7)
            scene.publish({"frame_id": 8, "device_timestamp_ns": 123,
                           "objects": [
                               {"track_id": 7, "track_state": "tracked",
                                "bbox_xyxy_norm": [0.1, 0.2, 0.5, 0.7]},
                               {"track_id": 9, "track_state": "held",
                                "bbox_xyxy_norm": [0.1, 0.2, 0.5, 0.7]}]})
            with urlopen(base + "/api/crop/7.jpg") as response:
                self.assertEqual(response.read(), b"jpeg-crop")
                self.assertEqual(response.headers["X-Frame-Timestamp-Ns"],
                                 "120")
                self.assertEqual(response.headers["X-Source-Track-Id"], "7")
            with self.assertRaises(HTTPError) as error:
                urlopen(base + "/api/crop/9.jpg")
            self.assertEqual(error.exception.code, 404)
            error.exception.close()
            with urlopen(base + "/api/features") as response:
                self.assertEqual(json.load(response), {})
            request = Request(base + "/api/lab-mode",
                              data=b'{"training":true}',
                              headers={"Content-Type": "application/json"},
                              method="PUT")
            with urlopen(request) as response:
                self.assertTrue(json.load(response)["training"])
            self.assertEqual([queue.sent[-1].data for queue in lab_queues],
                             [[1], [1]])
            request = Request(base + "/api/inference", data=b'{"fps":18}',
                              headers={"Content-Type": "application/json"},
                              method="PUT")
            with urlopen(request) as response:
                self.assertEqual(json.load(response)["fps"], 18)
            self.assertEqual(rate_queue.sent[-1].data, [18])
            with urlopen(base + "/api/inference") as response:
                self.assertEqual(json.load(response),
                                 {"fps": 18, "video_fps": 30})
            for bad in (b'{"fps":9}', b'{"fps":31}', b'{"fps":20.5}',
                        b'{"fps":true}'):
                invalid = Request(base + "/api/inference", data=bad,
                                  headers={"Content-Type": "application/json"},
                                  method="PUT")
                with self.assertRaises(HTTPError) as error:
                    urlopen(invalid)
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
            invalid = Request(base + "/api/model", data=b'{"iou":2}',
                              headers={"Content-Type": "application/json"},
                              method="PUT")
            with self.assertRaises(HTTPError) as error:
                urlopen(invalid)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_viewer_assets_are_proxied_to_internal_port(self):
        class ViewerHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = self.path.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        viewer = ThreadingHTTPServer(("127.0.0.1", 0), ViewerHandler)
        controls = ModelControls(FakeParser(), FakeQueue(), FakeConfig)
        panel = ThreadingHTTPServer(("127.0.0.1", 0),
                                   make_handler(controls, viewer.server_port))
        workers = [threading.Thread(target=server.serve_forever, daemon=True)
                   for server in (viewer, panel)]
        for worker in workers:
            worker.start()
        try:
            base = f"http://127.0.0.1:{panel.server_port}"
            with urlopen(base + "/viewer/?ws_url=example") as response:
                self.assertEqual(response.read(), b"/?ws_url=example")
            with urlopen(base + "/assets/viewer.js") as response:
                self.assertEqual(response.read(), b"/assets/viewer.js")
        finally:
            for server in (viewer, panel):
                server.shutdown()
                server.server_close()
            for worker in workers:
                worker.join()

    def test_mono_jpeg_is_valid_grayscale_and_sources_are_distinct(self):
        import cv2
        import numpy as np

        frames = MonoFrameStore()
        frames.publish("left", np.full((40, 60), 40, dtype=np.uint8))
        frames.publish("right", np.full((40, 60), 180, dtype=np.uint8))
        left = cv2.imdecode(np.frombuffer(frames.jpeg("left"), np.uint8),
                            cv2.IMREAD_GRAYSCALE)
        right = cv2.imdecode(np.frombuffer(frames.jpeg("right"), np.uint8),
                             cv2.IMREAD_GRAYSCALE)
        self.assertEqual(left.shape, (40, 60))
        self.assertLess(float(left.mean()), float(right.mean()))
        self.assertIsNone(frames.jpeg("other"))

    def test_ir_dot_on_off_and_failed_command(self):
        device = FakeDevice()
        control = IRProjectorControl(device)
        self.assertEqual(control.apply({"enabled": True})["intensity"], 0.5)
        self.assertEqual(control.apply({"intensity": 0.3})["enabled"], True)
        self.assertEqual(control.apply({"enabled": False})["enabled"], False)
        self.assertEqual(device.commands, [0.5, 0.3, 0.0])
        with self.assertRaises(ValueError):
            control.apply({"intensity": 1.5})
        device.accept = False
        with self.assertRaises(RuntimeError):
            control.apply({"enabled": True})
        self.assertFalse(control.read()["enabled"])

    def test_zoom_roi_moves_and_clamps_to_canvas(self):
        queue = FakeQueue()
        zoom = ZoomControl(queue, FakeBuffer, (1280, 704), (640, 352))
        self.assertEqual(zoom.read()["box_xyxy_norm"],
                         [0.25, 0.25, 0.75, 0.75])
        result = zoom.apply({"center_x": 1.0, "center_y": 0.0})
        self.assertEqual(result["box_xyxy_norm"], [0.5, 0.0, 1.0, 0.5])
        self.assertEqual(queue.sent[-1].data, [128, 2, 0, 0])
        with self.assertRaises(ValueError):
            zoom.apply({"center_x": -0.1})
