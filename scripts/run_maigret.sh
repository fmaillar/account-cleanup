#!/usr/bin/env bash
set -euo pipefail

usernames_file="${1:-config/usernames.txt}"
outdir="${OUTDIR:-results/maigret}"
connections="${MAIGRET_CONNECTIONS:-50}"

command -v maigret >/dev/null || {
  echo "maigret not found in PATH" >&2
  exit 127
}

[[ -f "$usernames_file" ]] || {
  echo "Missing $usernames_file (copy config/usernames.txt.example first)" >&2
  exit 2
}

mapfile -t usernames < <(
  sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$usernames_file"
)

(("${#usernames[@]}" > 0)) || {
  echo "No usernames configured" >&2
  exit 2
}

mkdir -p "$outdir"

# Results are snapshots, not an append-only cache. Remove old Maigret reports so
# recursive usernames from an earlier run cannot survive in a new archive.
find "$outdir" -maxdepth 1 -type f \
  \( -name 'report_*.csv' -o -name 'report_*_simple.json' -o -name 'report_*_plain.html' \) \
  -delete

echo "Scanning ${#usernames[@]} username(s) with Maigret..."
maigret   "${usernames[@]}"   --no-recursion   --max-connections "$connections"   --folderoutput "$outdir"   --html   --csv   --json simple
