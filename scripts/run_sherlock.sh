#!/usr/bin/env bash
set -euo pipefail

usernames_file="${1:-config/usernames.txt}"
outdir="${OUTDIR:-results/sherlock}"

command -v sherlock >/dev/null || {
  echo "sherlock not found in PATH" >&2
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

sherlock   "${usernames[@]}"   --folderoutput "$outdir"   --txt
