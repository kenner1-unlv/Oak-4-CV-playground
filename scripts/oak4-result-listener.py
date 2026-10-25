"""Print compact OAK4 perception records arriving on the Orin's wired link."""

import argparse
import json
import socket
import time


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="0.0.0.0",
                        help="local interface to listen on (default: all)")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--until-range", action="store_true",
                        help="print the first frame with measured range, then exit")
    parser.add_argument("--max-frames", type=int, default=100,
                        help="limit frames checked with --until-range")
    parser.add_argument("--sample-frames", type=int, default=0,
                        help="measure result rate and payload size over N frames")
    args = parser.parse_args()
    checked = 0
    first_wall = None
    first_device_ns = None
    total_bytes = 0
    ranged_objects = 0
    tile_counts: dict[str, int] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as listener:
        listener.bind((args.bind, args.port))
        print(f"Listening on {args.bind}:{args.port}", flush=True)
        while True:
            packet, address = listener.recvfrom(65535)
            try:
                record = json.loads(packet)
                if record.get("schema_version") != 1:
                    raise ValueError("unsupported schema version")
                if not isinstance(record.get("objects"), list):
                    raise ValueError("objects must be a list")
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                print(f"Ignored invalid packet from {address[0]}: {exc}", flush=True)
                continue
            if args.sample_frames:
                checked += 1
                now = time.monotonic()
                if first_wall is None:
                    first_wall = now
                    first_device_ns = record.get("device_timestamp_ns")
                total_bytes += len(packet)
                ranged_objects += sum(item.get("range_m") is not None
                                      for item in record["objects"])
                tile_key = str(record.get("tile_id", "full"))
                tile_counts[tile_key] = tile_counts.get(tile_key, 0) + 1
                if checked >= args.sample_frames:
                    elapsed = max(now - first_wall, 1e-9)
                    device_elapsed_ns = (record.get("device_timestamp_ns", 0)
                                         - first_device_ns)
                    print(json.dumps({
                        "frames": checked,
                        "received_fps": round((checked - 1) / elapsed, 2),
                        "device_fps": round((checked - 1) * 1e9
                                            / device_elapsed_ns, 2)
                        if device_elapsed_ns > 0 else None,
                        "avg_payload_bytes": round(total_bytes / checked),
                        "ranged_objects": ranged_objects,
                        "tile_counts": tile_counts,
                    }), flush=True)
                    return
            elif args.until_range:
                checked += 1
                measured = [item for item in record["objects"]
                            if item.get("range_m") is not None]
                if measured:
                    print(json.dumps({"frame_id": record["frame_id"],
                                      "measured": measured},
                                     separators=(",", ":")), flush=True)
                    return
                if checked >= args.max_frames:
                    print(f"No measured range in {checked} frames", flush=True)
                    return
            else:
                print(json.dumps(record, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
