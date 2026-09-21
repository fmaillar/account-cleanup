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

echo "Scanning ${#usernames[@]} username(s) with Maigret..."
maigret   "${usernames[@]}"   --max-connections "$connections"   --folderoutput "$outdir"   --html   --csv   --json simple
