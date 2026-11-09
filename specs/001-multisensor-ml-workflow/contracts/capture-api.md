# Proposed Orin Capture and Review API (v1)

This is a design contract, not a currently running endpoint. Orin owns durable data. House V reaches it through an explicit same-origin OAK proxy or a configured local origin; no browser-supplied filesystem paths. Current OAK `/api/scene`, `/api/mono/*`, `/api/identities`, and `/api/lidar` remain independent live feeds. They cannot be used as an atomic recording source.

All JSON responses include `schema_version: 1`. Errors use `{ "error": { "code": "...", "message": "..." } }` and a non-2xx status. State-changing requests use a generated idempotency key so browser retry cannot double-start or double-stop. Single-operator local access is assumed; binding and access controls must be configured before exposing beyond the wired lab network.

| Method/path | Request | Response/behavior |
| --- | --- | --- |
| `GET /api/capture/status` | None | `state`, active session ID, per-source counts/drops, bytes, queue, sync state and measured skew/unknown offset, latest error. |
| `POST /api/capture/sessions` | Name, scene group, notes, benchmark ID/level, idempotency key | `201` with `session_id`, `state: recording`; `409` if another recording is active; `507` if quota/reservation fails. Recording defaults off. |
| `POST /api/capture/sessions/{id}/stop` | Idempotency key | Flush and finalize; return manifest ID/hash and `complete`, or `incomplete` with reason if flush fails. |
| `GET /api/capture/sessions` | Pagination/filter query | Summary catalog with state, counts, times, benchmark level, integrity state. |
| `GET /api/capture/sessions/{id}` | None | Full manifest metadata, source roster, gaps, integrity summary; asset URLs are generated IDs, not filesystem paths. |
| `GET /api/capture/sessions/{id}/observations` | Time window, source, cursor | Ordered observations with each original time, clock domain, receipt time, availability, and association state. Ordering by receipt time does not imply synchronization. |
| `GET /api/capture/assets/{asset_id}` | None | Verified asset stream or `409` integrity failure / `404` missing. |
| `GET /api/capture/models` | None | Model artifact catalog, task/input/taxonomy/source/deployment evidence; unknown fields explicit. |
| `GET /api/capture/snapshots` | Session/model filters | Prediction snapshot catalog with mode and artifact hash. |
| `POST /api/capture/corrections` | Target observation/track IDs, kind, value, author, reason, optional `supersedes_id` | Append correction; return ID/revision. Raw observation remains immutable. |
| `GET /api/capture/corrections` | Session/target filters | History plus active revision marker. |
| `POST /api/capture/splits` | Scene/session groups, partition membership, truth revision | Reject overlap (`422`); freeze returns membership hash; later change creates new version. |
| `POST /api/capture/experiments` | Frozen split ID/hash, task (`lego_detector`, `association`, `range_study`), candidate/baseline IDs, config | Queue explicit train or evaluation run; reject test leakage/resource gate failure. Never deploys. |
| `GET /api/capture/experiments/{id}` | None | Status, measured resources, report provenance, metric numerator/denominator, per-scene results, mode. |
| `POST /api/capture/calibrations` | Transform, timing evidence, reference measurements, density check | Store versioned calibration; validation state reflects evidence. Does not activate fusion automatically. |

## Capture control invariants

- A start call requires a nonempty bounded name and valid data root with reserved free space. Only one active session per source roster.
- Stop waits for bounded queue flush and seals the manifest atomically. Crash recovery marks the prior session `incomplete`; it cannot be silently resumed.
- Quota/storage failure stops capture cleanly and retains readable assets. Live camera inference and existing identity views remain usable.
- `GET` operations never write source evidence. Corrections, splits, and experiments are append-only/versioned operations.
- The API reports actual support. Before implementation, House V shows controls as unavailable, not as simulated success.
