#!/usr/bin/env bash
set -euo pipefail

# Run on the Orin. A local OTA file is transferred by oakctl over the wired link.
# Both values are required so a copied script cannot update the wrong camera.
camera=${OAK_DEVICE:-}
expected_serial=${OAK_SERIAL:-}

usage() {
  cat <<'EOF'
Usage:
  OAK_DEVICE=CAMERA_IP:9998 OAK_SERIAL=SERIAL bash scripts/oak4-update.sh check
  OAK_DEVICE=CAMERA_IP:9998 OAK_SERIAL=SERIAL bash scripts/oak4-update.sh verify /absolute/path/full_update_luxonis_ext4-VERSION.zip [SHA256]
  OAK_DEVICE=CAMERA_IP:9998 OAK_SERIAL=SERIAL bash scripts/oak4-update.sh apply /absolute/path/full_update_luxonis_ext4-VERSION.zip [SHA256]

The verify command checks the local ZIP and optional SHA-256 without updating.
Apply performs the same checks, then asks oakctl to transfer and apply it.
Keep the camera on PoE power throughout the update.
EOF
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

[[ $# -ge 1 ]] || { usage; exit 2; }
mode=$1
shift
case "$mode" in
  check) [[ $# -eq 0 ]] || die 'check takes no arguments' ;;
  verify|apply) [[ $# -ge 1 && $# -le 2 ]] || die "$mode needs a ZIP path and optional SHA-256" ;;
  -h|--help|help) usage; exit 0 ;;
  *) usage; exit 2 ;;
esac

[[ -n "$camera" && -n "$expected_serial" ]] || die 'set OAK_DEVICE and OAK_SERIAL'

for tool in oakctl python3; do
  command -v "$tool" >/dev/null || die "$tool is required on the Orin"
done

device_info=$(oakctl device info -d "$camera" --format json)
version=$(printf '%s\n' "$device_info" | python3 -c '
import json, sys
lines = [line for line in sys.stdin.read().splitlines() if line.lstrip().startswith("{")]
if not lines:
    raise SystemExit("oakctl returned no device JSON")
device = json.loads(lines[-1])
serial = device.get("serial_number", {}).get("RVC4")
if serial != sys.argv[1]:
    raise SystemExit(f"unexpected camera serial: {serial}")
print(device["os_version"])
' "$expected_serial")
printf 'OAK4-D %s at %s: Luxonis OS %s\n' "$expected_serial" "$camera" "$version"

if [[ "$mode" == check ]]; then
  oakctl device update -d "$camera" --info --format json --yes
  exit 0
fi

artifact=$1
expected_hash=${2:-}
[[ "$artifact" = /* ]] || die 'use an absolute path to a ZIP on the Orin'
[[ -f "$artifact" && -r "$artifact" ]] || die "cannot read $artifact"
command -v unzip >/dev/null || die 'unzip is required to validate the OTA ZIP'
unzip -tq "$artifact" >/dev/null || die 'OTA ZIP failed its integrity test'

actual_hash=$(sha256sum "$artifact")
actual_hash=${actual_hash%% *}
printf 'OTA SHA-256: %s\n' "$actual_hash"
if [[ -n "$expected_hash" ]]; then
  [[ "$expected_hash" =~ ^[[:xdigit:]]{64}$ ]] || die 'expected SHA-256 must be 64 hex characters'
  [[ "${actual_hash,,}" == "${expected_hash,,}" ]] || die 'SHA-256 mismatch'
fi

if [[ "$mode" == verify ]]; then
  printf 'OTA file verified; no update was applied.\n'
  exit 0
fi

oakctl device update -d "$camera" --path "$artifact" --yes
printf 'Update command finished. Run this script with `check` after the camera reboots.\n'
