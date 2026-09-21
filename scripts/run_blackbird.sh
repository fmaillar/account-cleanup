#!/usr/bin/env bash
set -euo pipefail

emails_file="${1:-config/emails.txt}"
outdir="${OUTDIR:-results/blackbird}"
blackbird="${BLACKBIRD:-blackbird}"

[[ -f "$emails_file" ]] || {
  echo "Missing $emails_file (copy config/emails.txt.example first)" >&2
  exit 2
}

if ! command -v "$blackbird" >/dev/null 2>&1 && [[ ! -x "$blackbird" ]]; then
  echo "Blackbird not found. Put it in PATH or set BLACKBIRD=/path/to/blackbird.py" >&2
  exit 127
fi

mkdir -p "$outdir"

while IFS= read -r email; do
  [[ -z "$email" || "$email" == \#* ]] && continue
  safe=$(printf '%s' "$email" | tr '@/: ' '____')
  echo "==> Blackbird: $email"
  if [[ "$blackbird" == *.py ]]; then
    python3 "$blackbird" -e "$email" 2>&1 | tee "$outdir/$safe.txt"
  else
    "$blackbird" -e "$email" 2>&1 | tee "$outdir/$safe.txt"
  fi
done < "$emails_file"
