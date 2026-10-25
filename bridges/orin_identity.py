"""Provisional long-lived IDs for OAK detections on the Orin.

The current matcher uses camera-frame geometry and class history. Its score is
a matching heuristic, not a probability or appearance-based identification.
"""

import json
import math
import os
import signal
import socket
import threading
import time
from dataclasses import asdict, dataclass
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def box_iou(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


@dataclass
class Identity:
    global_id: int
    camera_track_id: int
    label: str
    bbox: tuple[float, float, float, float]
    xyz_mm: tuple[float, float, float] | None
    first_seen: float
    last_seen: float
    observed_seconds: float = 0.0
    observations: int = 1
    match_kind: str = "new"
    match_score: float | None = None
    detector_score: float | None = None
    alternate_label: str | None = None
    alternate_evidence_share: float | None = None
    mono_evidence: dict | None = None


class IdentityResolver:
    def __init__(self, max_gap_s: float = 4.0,
                 min_confirmations: int = 1,
                 min_confirmation_s: float = 0.0) -> None:
        self.max_gap_s = max_gap_s
        self.min_confirmations = min_confirmations
        self.min_confirmation_s = min_confirmation_s
        self.next_id = 1
        self.identities: dict[int, Identity] = {}
        self.source_to_global: dict[int, int] = {}
        self.last_frame_id: int | None = None
        self.last_device_ns: int | None = None
        self.restart_match_until = 0.0
        self.reid_events = 0
        self.recent_reid = deque(maxlen=8)
        self.pending: dict[int, dict] = {}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {"next_id": self.next_id,
                "identities": [asdict(item) for item in self.identities.values()],
                "source_to_global": self.source_to_global,
                "last_frame_id": self.last_frame_id,
                "last_device_ns": self.last_device_ns}
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(body, separators=(",", ":")),
                             encoding="utf-8")
        temporary.replace(path)

    def load(self, path: Path) -> None:
        if not path.exists():
            return
        body = json.loads(path.read_text(encoding="utf-8"))
        identities = {}
        for raw in body.get("identities", []):
            raw["bbox"] = tuple(raw["bbox"])
            raw["xyz_mm"] = tuple(raw["xyz_mm"]) if raw.get("xyz_mm") else None
            item = Identity(**raw)
            identities[item.global_id] = item
        self.identities = identities
        self.next_id = max(int(body.get("next_id", 1)),
                           max(identities, default=0) + 1)
        if "source_to_global" in body:
            self.source_to_global = {
                int(source): int(global_id)
                for source, global_id in body["source_to_global"].items()
                if int(global_id) in identities
            }
        else:  # Upgrade state written before source mappings were persisted.
            by_source = {}
            for item in identities.values():
                previous = by_source.get(item.camera_track_id)
                if previous is None or item.observed_seconds > previous.observed_seconds:
                    by_source[item.camera_track_id] = item
            self.source_to_global = {
                source: item.global_id for source, item in by_source.items()
            }
        self.last_frame_id = body.get("last_frame_id")
        self.last_device_ns = body.get("last_device_ns")

    def _match_score(self, identity: Identity, obj: dict, now: float):
        dt = now - identity.last_seen
        if dt < 0:
            return None
        label = obj.get("label") or obj.get("detector_label")
        overlap = box_iou(identity.bbox, obj["bbox_xyxy_norm"])
        xyz = obj.get("xyz_mm")
        if dt > self.max_gap_s:
            if (now > self.restart_match_until or dt > 30 or
                label != identity.label or overlap < 0.4 or
                identity.xyz_mm is None or xyz is None):
                return None
            distance_m = math.dist(identity.xyz_mm, xyz) / 1000
            if distance_m > 0.5:
                return None
            return (0.45 * (1 - distance_m / 0.5) +
                    0.45 * overlap + 0.15 - 0.01 * dt)
        if identity.xyz_mm is not None and xyz is not None:
            distance_m = math.dist(identity.xyz_mm, xyz) / 1000
            limit_m = min(2.0, 0.55 + 0.35 * dt)
            if distance_m > limit_m:
                return None
            score = 0.62 * (1 - distance_m / limit_m) + 0.23 * overlap
        else:
            if overlap < 0.5 or label != identity.label:
                return None
            score = 0.7 * overlap
        if label == identity.label:
            score += 0.15
        elif label is not None:
            score -= 0.12
        return score - 0.025 * dt

    def ingest(self, packet: dict, now: float | None = None) -> dict:
        if packet.get("schema_version") != 1 or not isinstance(packet.get("objects"), list):
            raise ValueError("invalid OAK result record")
        now = time.time() if now is None else now
        frame_id = packet.get("frame_id")
        device_ns = packet.get("device_timestamp_ns")
        if ((self.last_frame_id is not None and frame_id is not None and
             frame_id < self.last_frame_id - 100) or
            (self.last_device_ns is not None and device_ns is not None and
             device_ns < self.last_device_ns)):
            self.source_to_global.clear()  # Camera app restarted its IDs.
            self.pending.clear()
            self.restart_match_until = now + 5
        self.last_frame_id = frame_id
        self.last_device_ns = device_ns

        observed = [obj for obj in packet["objects"]
                    if obj.get("track_state") == "tracked" and
                    isinstance(obj.get("track_id"), int) and
                    isinstance(obj.get("bbox_xyxy_norm"), list) and
                    len(obj["bbox_xyxy_norm"]) == 4]
        tracked_source_ids = {obj["track_id"] for obj in observed}
        for source_id, pending in list(self.pending.items()):
            if now - pending["last"] > 2:
                del self.pending[source_id]
        assigned_global: set[int] = set()
        for obj in observed:
            source_id = obj["track_id"]
            global_id = self.source_to_global.get(source_id)
            identity = self.identities.get(global_id) if global_id else None
            kind, score = "direct", None
            if identity is None or identity.global_id in assigned_global:
                identity = None
                candidates = []
                for old in self.identities.values():
                    if (old.global_id in assigned_global or
                        (old.camera_track_id in tracked_source_ids and
                         old.camera_track_id != source_id)):
                        continue  # Never merge two current camera tracks.
                    match = self._match_score(old, obj, now)
                    if match is not None and match >= 0.36:
                        candidates.append((match, old))
                if candidates:
                    score, identity = max(candidates, key=lambda pair: pair[0])
                    kind = "provisional_reid"
                    self.pending.pop(source_id, None)
                    self.reid_events += 1
                    self.recent_reid.append({"global_id": identity.global_id,
                                             "new_camera_track_id": source_id,
                                             "score": round(score, 3),
                                             "at": now})
                else:
                    pending = self.pending.get(source_id)
                    if (pending is None or now - pending["last"] > 0.25 or
                        box_iou(pending["bbox"], obj["bbox_xyxy_norm"]) < 0.2):
                        pending = {"first": now, "last": now,
                                   "count": 0,
                                   "bbox": obj["bbox_xyxy_norm"]}
                    pending["count"] += 1
                    pending["last"] = now
                    pending["bbox"] = obj["bbox_xyxy_norm"]
                    self.pending[source_id] = pending
                    if (pending["count"] < self.min_confirmations or
                        now - pending["first"] < self.min_confirmation_s):
                        continue
                    self.pending.pop(source_id, None)
                    identity = Identity(
                        self.next_id, source_id,
                        obj.get("label") or obj.get("detector_label") or "unknown",
                        tuple(obj["bbox_xyxy_norm"]),
                        tuple(obj["xyz_mm"]) if obj.get("xyz_mm") else None,
                        pending["first"], now,
                    )
                    identity.observations = pending["count"]
                    identity.observed_seconds = min(now - pending["first"], 0.25)
                    self.identities[self.next_id] = identity
                    self.next_id += 1
                    kind = "new"
            else:
                gap = max(0.0, now - identity.last_seen)
                if gap > 0.25:
                    kind = "direct_after_gap"

            if kind != "new":
                if kind != "provisional_reid":
                    identity.observed_seconds += min(
                        max(0.0, now - identity.last_seen), 0.25
                    )
                identity.observations += 1
            identity.camera_track_id = source_id
            identity.label = obj.get("label") or obj.get("detector_label") or identity.label
            identity.bbox = tuple(obj["bbox_xyxy_norm"])
            if obj.get("xyz_mm") is not None:
                identity.xyz_mm = tuple(obj["xyz_mm"])
            identity.last_seen = now
            identity.match_kind = kind
            identity.match_score = round(score, 3) if score is not None else None
            identity.detector_score = obj.get("detector_score")
            identity.alternate_label = obj.get("alternate_label")
            identity.alternate_evidence_share = obj.get("alternate_evidence_share")
            identity.mono_evidence = obj.get("mono_evidence") or {}
            self.source_to_global[source_id] = identity.global_id
            assigned_global.add(identity.global_id)

        recent = [item for item in self.identities.values()
                  if now - item.last_seen <= 10]
        longest = sorted(recent, key=lambda item:
                         (-item.observed_seconds, -item.observations))[:2]
        return {
            "updated_at": now,
            "frame_id": frame_id,
            "source_to_global": {str(obj["track_id"]): self.source_to_global[obj["track_id"]]
                                 for obj in packet["objects"]
                                 if isinstance(obj.get("track_id"), int) and
                                 obj["track_id"] in self.source_to_global},
            "longest_recent": [asdict(item) for item in longest],
            "global_count": len(self.identities),
            "pending_count": len(self.pending),
            "reid_events": self.reid_events,
            "recent_reid": list(self.recent_reid),
        }


class IdentityService:
    def __init__(self, bind_host: str, udp_port: int, http_port: int) -> None:
        self.resolver = IdentityResolver(min_confirmations=3,
                                         min_confirmation_s=0.35)
        self.state_path = Path(os.getenv("IDENTITY_STATE_PATH",
                                         "/data/oak4/identity-state.json"))
        self.resolver.load(self.state_path)
        self.last_save = 0.0
        self.lock = threading.Lock()
        self.latest = {"updated_at": None, "longest_recent": [],
                       "source_to_global": {}, "global_count": 0}
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind((bind_host, udp_port))
        self.udp.settimeout(0.5)
        self.running = True

        service = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/identities":
                    self.send_error(404)
                    return
                with service.lock:
                    data = dict(service.latest)
                data["age_s"] = (max(0.0, time.time() - data["updated_at"])
                                 if data.get("updated_at") is not None else None)
                body = json.dumps(data, separators=(",", ":")).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        self.http = ThreadingHTTPServer((bind_host, http_port), Handler)

    def receive(self):
        while self.running:
            try:
                data, _address = self.udp.recvfrom(65535)
                packet = json.loads(data)
                with self.lock:
                    self.latest = self.resolver.ingest(packet)
                    if time.monotonic() - self.last_save >= 5:
                        self.resolver.save(self.state_path)
                        self.last_save = time.monotonic()
            except socket.timeout:
                continue
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                continue

    def run(self):
        worker = threading.Thread(target=self.receive, daemon=True)
        worker.start()
        def stop(_signum, _frame):
            threading.Thread(target=self.http.shutdown, daemon=True).start()
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        try:
            self.http.serve_forever()
        finally:
            self.running = False
            with self.lock:
                self.resolver.save(self.state_path)
            self.http.server_close()
            self.udp.close()


if __name__ == "__main__":
    IdentityService(os.getenv("ORIN_WIRED_IP", "192.168.50.2"),
                    int(os.getenv("OAK_RESULT_PORT", "8766")),
                    int(os.getenv("IDENTITY_HTTP_PORT", "8771"))).run()
