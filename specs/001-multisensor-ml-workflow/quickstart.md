# Validation Quickstart

This is a validation guide for the planned feature. The capture API and LEGO training commands do not exist yet; use the fixture scenarios as implementation acceptance checks. Existing camera and Orin paths are described in `../../docs/lab-setup.md`, `../../docs/architecture.md`, and `../../bridges/README.md`. Keep real recordings and weights in the Orin data root outside Git.

## Prerequisites

- A local Python environment able to run the repository's tests. Existing test discovery can be run from repository root with `python -m unittest discover -s bridges/tests -p 'test_*.py'`; OAK tests may require their application path on `PYTHONPATH` and installed dependencies.
- For hardware checks, the named OAK, Orin, and L2 with documented network access, an Orin data root with free space, and the House V browser tunnel on 8082/8765.
- A small synthetic fixture for API, crash, split, and metric checks. Use no private scene captures in Git.
- For the physical LEGO baseline, an inventoried mixed-color/mixed-size set of roughly 20 pieces, a fixed board/camera setup, a human-labeled reference image, and a recorded shake/placement procedure. Check every piece is flat, non-touching, and non-overlapping before marking baseline eligible.

## 1. Contract and recording fixture

1. Start the planned Orin capture service against a temporary data root using synthetic OAK/mono/identity/L2 records. Open the existing Training Lab page.
2. Confirm recording starts off. Start a named session and inspect `GET /api/capture/status` (contract: `contracts/capture-api.md`). Check active ID, counts by source, bytes, queue, drops, and sync state.
3. Feed a missing mono frame, an L2 sample with its ROS time, and an OAK source restart. Check gap/discontinuity records and independent source/receipt timestamps. In particular, a mono JPEG fetched from the existing endpoint or separately polled scene/identity/L2 data must not be reported as a synchronized triple.
4. Stop the session. Reopen its manifest, verify asset SHA-256 values and immutable paths, and confirm `complete`. Interrupt another session before stop and restart service; it must reopen `incomplete` with readable prior assets.
5. Simulate insufficient disk or quota exhaustion. Capture should fail or stop cleanly, retain already written data, and leave the live viewer usable.

**Pass condition**: Every saved sample has source and time provenance; every injected gap is visible; no unmatched source is silently paired. The physical five-minute success criterion is checked separately on the devices.

## 2. Review and catalog fixture

1. Open one session and select an observation. Confirm available RGB, left/right mono, stereo, identity, and L2 entries display source time, receive time, model/calibration IDs, score semantics, and missing/stale status.
2. List OAK model references and prediction snapshots. A YAML reference without artifact hash or installed-package evidence must show `unknown`, while a verified artifact shows its task, input transform, classes, and source. Deliberately corrupt one fixture asset and confirm integrity failure blocks trusted evaluation.
3. Append a `wrong_class` correction and a `same_object` correction, then revise one. Confirm both revisions remain visible and the raw record/hash is unchanged.

**Pass condition**: Corrections and predictions have separate provenance; unavailable model history is never invented.

## 3. LEGO baseline and stages

1. Record the actual inventory/count, colors, size or footprint categories, board dimensions, camera pose/distance, lighting, and shake procedure. Confirm the separated-flat baseline eligibility. A scene with contact or overlap must be reclassified to a harder stage or excluded from baseline.
2. Capture repeated layouts and rotate pieces in-plane. Give each visible piece an independent instance annotation; retain the same class/color/size truth through rotation. Put orientation variants of one layout in a single scene group.
3. Add a second stage with one changed difficulty variable, such as narrower gaps, touching, overlap, count, or lighting. Keep its results separate from baseline.
4. Run a generic or trained candidate over both fixtures. Confirm reports include count error, per-instance detection/mask quality, color and size/footprint outcomes, split/merge and touching errors, orientation strata, sample denominators, and model/configuration identity.

**Pass condition**: The approximately 20-piece baseline is auditable per piece; orientation does not change truth labels; difficulty stages are not pooled without labels. Do not describe generic COCO output as validated LEGO recognition.

## 4. Frozen splits and candidate evaluation

1. Create train/validation/test membership by whole scene/session groups, then freeze the test membership hash. Try to place adjacent frames or orientation variants from one scene in different partitions; expect rejection.
2. Export reviewed RGB images and instance labels for supervised LEGO detector/segmenter training on Orin or workstation. Record taxonomy, split, configuration, artifact hash, and off-device execution mode. Training does not change the live OAK app.
3. Run a detector baseline and candidate against identical frozen replay examples; separately run the current Orin identity baseline and an association candidate on the same identity fixture. Repeat each evaluation with the same inputs.
4. Compare membership and metric totals between repeats. Inspect per-scene/stage counts, denominators, model IDs, code/configuration revisions, latency, and failures. Verify that replay is labeled experimental, not live or deployed.
5. Simulate Orin resource pressure. Training should queue, pause, or reject with a visible reason until device limits have been measured.

**Pass condition**: Repeated runs are identical on fixed fixture inputs; test leakage is rejected; no candidate is automatically promoted or converted for RVC4.

## 5. L2 validation gate

1. With no calibration, open an L2 fixture. It must show an unaligned preview and no stereo-versus-L2 accuracy or per-piece identity claim.
2. Add a measured transform, timing alignment, known-distance board/reference scene, and a point-density record at the board. Run board-plane/scene range comparison and inspect transform/time residuals, missing readings, uncertainty, and error denominators.
3. Use a sparse cloud fixture with too few returns per LEGO piece. Per-piece L2 metrics must remain absent even when board-plane comparison is valid.

**Pass condition**: Calibration and density gates control claims independently; L2 remains useful as scene context when it cannot resolve pieces.

## Physical-device acceptance record

After implementation, capture at least five minutes on the actual OAK/Orin/L2 setup. Record exact device/app/model versions, hashes, source and receipt clocks, RGB/mono rates, dropped samples, disk consumption, thermal/CPU/GPU load, browser behavior, and whether the real session reopens. Run the LEGO baseline and staged scene with human truth. Record which checks were physically verified and which remain fixture-only. RVC4 model conversion, installation, live promotion, and rollback require a separate owner-approved execution plan.
