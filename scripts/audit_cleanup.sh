#!/usr/bin/env bash
set -euo pipefail

bash scripts/process_results.sh
python3 scripts/probe_site_channels.py
python3 scripts/prepare_deletion_plan.py

echo
echo "Deletion/contact channel audit:"
echo "  results/site-channels.tsv"
echo "  results/deletion-plan.tsv"
