#!/usr/bin/env bash
set -euo pipefail

run_if_available() {
  local command=$1 script=$2
  if command -v "$command" >/dev/null 2>&1; then
    "$script"
  else
    printf 'skip: %s not found\n' "$command" >&2
  fi
}

run_if_available holehe scripts/run_holehe.sh

if [[ -n "${BLACKBIRD:-}" ]] || command -v blackbird >/dev/null 2>&1; then
  scripts/run_blackbird.sh
else
  printf 'skip: Blackbird not configured (set BLACKBIRD=/path/to/blackbird.py)\n' >&2
fi

run_if_available maigret scripts/run_maigret.sh

if [[ "${RUN_SHERLOCK:-0}" == 1 ]]; then
  run_if_available sherlock scripts/run_sherlock.sh
fi

scripts/process_results.sh
