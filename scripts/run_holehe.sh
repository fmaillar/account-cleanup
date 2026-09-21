#!/usr/bin/env bash
set -euo pipefail

emails_file="${1:-config/emails.txt}"
outdir="${OUTDIR:-results/holehe}"

command -v holehe >/dev/null || {
  echo "holehe not found in PATH" >&2
  exit 127
}

[[ -f "$emails_file" ]] || {
  echo "Missing $emails_file (copy config/emails.txt.example first)" >&2
  exit 2
}

mkdir -p "$outdir"

while IFS= read -r email; do
  [[ -z "$email" || "$email" == \#* ]] && continue
  safe=$(printf '%s' "$email" | tr '@/: ' '____')
  echo "==> Holehe: $email"
  holehe "$email" 2>&1 | tee "$outdir/$safe.txt"
done < "$emails_file"
