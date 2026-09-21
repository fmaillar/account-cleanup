#!/usr/bin/env bash
set -euo pipefail

bash scripts/process_results.sh
python3 scripts/probe_site_channels.py

echo
echo "Deletion/contact channel audit:"
echo "  results/site-channels.tsv"
