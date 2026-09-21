#!/usr/bin/env bash
set -euo pipefail
scripts/extract_all.sh
python3 scripts/build_cleanup_report.py
printf '\nUseful queues:\n'
printf '  results/extracts/maigret-cleanup.tsv\n'
printf '  results/extracts/maigret-mine.tsv\n'
printf '  results/extracts/maigret-review.tsv\n'
printf '  results/extracts/maigret-requested.tsv\n'
printf '  results/cleanup-report.html\n'
