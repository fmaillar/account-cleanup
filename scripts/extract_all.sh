#!/usr/bin/env bash
set -euo pipefail

mkdir -p results/extracts

shopt -s nullglob

holehe=(results/holehe/*.txt)
if (("${#holehe[@]}" > 0)); then
  python3 scripts/extract_holehe.py "${holehe[@]}"     > results/extracts/holehe-positive.tsv
fi

blackbird=(results/blackbird/*.txt)
if (("${#blackbird[@]}" > 0)); then
  python3 scripts/extract_blackbird.py "${blackbird[@]}"     > results/extracts/blackbird-positive.tsv
fi

if [[ -d results/maigret ]]; then
  python3 scripts/extract_maigret.py results/maigret     > results/extracts/maigret-claimed.tsv
  python3 scripts/extract_maigret.py results/maigret --json     > results/extracts/maigret-claimed.json
  python3 scripts/classify_maigret.py results/extracts/maigret-claimed.tsv
fi

echo "Extracts written to results/extracts/"
