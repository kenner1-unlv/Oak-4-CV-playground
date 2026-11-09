# Capture Record Contracts (v1)

These proposed JSON shapes complement, rather than silently replace, the existing OAK version-1 UDP result and L2 `/scan` response. Production payloads need size limits, validation, and version negotiation. Examples use illustrative IDs and values only.

## Source observation envelope

```json
{
  "schema_version": 1,
  "session_id": "session-uuid",
  "source_id": "oak-rgb",
  "source_kind": "rgb",
  "frame_sequence": 1234,
  "source_timestamp_ns": 123456789,
  "clock_domain": "oak-device-monotonic",
  "received_at_ns": 1790000000000000000,
  "received_clock_domain": "orin-realtime",
  "time_alignment_id": null,
  "sync_state": "offset_unknown",
  "model_id": "yolov8-seg-large:package-sha",
  "calibration_id": "oak-calibration-sha",
  "input_transform_id": "rgb-640x352",
  "inference_status": "complete",
  "availability": "present",
  "asset_ids": ["sha256:example"],
  "predictions": []
}
```

`source_timestamp_ns` and `received_at_ns` are distinct. `null` means unknown, not zero. An empty prediction list after `complete` means a completed pass with no detections; `missing`, `dropped`, `stale`, and `unmatched` need an explicit availability record and reason. An observation from a current browser poll without an original frame timestamp cannot be treated as synchronized. The existing mono JPEG endpoint needs a source frame ID/timestamp extension or capture-specific tagged transfer before it can supply an aligned training sample.

## L2 source sample

L2 samples retain `ros_frame_id`, original ROS stamp, Orin receipt time, `source_points`, `stride`, `saved_points`, and a cloud asset hash. An L2 sample has no camera label, piece ID, or matched object ID by default. `alignment_state` is `unaligned`, `scene_range_validated`, or `piece_resolution_validated` and refers to a calibration record. A sampled preview may support scene context but cannot certify per-piece distance.

## Session manifest

```json
{
  "schema_version": 1,
  "session_id": "session-uuid",
  "name": "lego-board-baseline-01",
  "scene_group_id": "board-layout-01",
  "benchmark": {"protocol": "lego-board-v1", "challenge_level": "separated_flat", "inventory_hash": "sha256:..."},
  "state": "complete",
  "started_at_utc": "2026-11-09T20:00:00Z",
  "ended_at_utc": "2026-11-09T20:05:00Z",
  "sources": [],
  "assets": [],
  "observations": [],
  "gaps": [],
  "integrity": {"algorithm": "sha256", "verified": true}
}
```

Asset entries include ID, relative path, byte length, media type, hash, source ID and times. Gaps include source, time/sequence interval, reason, and whether a restart or clock discontinuity occurred. Finalization writes a temporary manifest and atomically renames it; the manifest digest is stored separately to avoid self-reference. An incomplete session remains inspectable but is excluded from trusted evaluation unless an explicit eligibility decision documents why specific samples are safe.

## Benchmark and evaluation records

The LEGO baseline records a 20-piece target inventory with piece instance ID, color, size/dimensions, orientation, noncontact/nonoverlap eligibility, board reference, setup and shake notes, scene group, and independent truth annotations. A benchmark report names protocol version, number of eligible pieces and scenes, count error, detection precision/recall, per-color and per-size confusion, instance localization/segmentation quality, orientation strata, and missing-range rate. Every metric includes numerator/denominator and model/baseline/split hashes. A result for an untrained generic model is labeled baseline, not trained LEGO performance.

The identity report separately names ID switches, false merges, fragmentation, recovery after occlusion, class quality, and latency. The L2 report, when calibrated, states board/scene reference distances, transform/timing residuals, point density, missing data, and range error. Per-piece L2 metrics are absent until spatial resolution has been measured sufficient for individual pieces.
