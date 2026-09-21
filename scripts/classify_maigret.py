#!/usr/bin/env python3
"""Classify Maigret claimed profiles into deterministic cleanup queues."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from cleanup_rules import ACTIONS, classify_row, load_lines, load_rules


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, nargs="?", default=Path("results/extracts/maigret-claimed.tsv"))
    ap.add_argument("--rules", type=Path, default=Path("config/account-rules.tsv"))
    ap.add_argument("--keep-sites", type=Path, default=Path("config/keep-sites.txt"))
    ap.add_argument("--ignore-sites", type=Path, default=Path("config/ignore-sites.txt"))
    ap.add_argument("--outdir", type=Path, default=Path("results/extracts"))
    args = ap.parse_args()

    rules = load_rules(args.rules)
    keep = load_lines(args.keep_sites)
    ignore = load_lines(args.ignore_sites)
    args.outdir.mkdir(parents=True, exist_ok=True)

    with args.input.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    for row in rows:
        action, reason = classify_row(row, rules=rules, keep_sites=keep, ignore_sites=ignore)
        row["classification"] = action
        row["reason"] = reason

    fields = list(rows[0].keys()) if rows else [
        "query_username", "detected_username", "site", "status", "url", "metadata",
        "source", "classification", "reason"
    ]

    buckets = {action: [] for action in ACTIONS}
    for row in rows:
        buckets[row["classification"]].append(row)

    with (args.outdir / "maigret-classified.tsv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(rows)

    for action in sorted(ACTIONS):
        path = args.outdir / f"maigret-{action}.tsv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
            w.writeheader()
            w.writerows(buckets[action])

    print("classified " + ", ".join(f"{a}={len(buckets[a])}" for a in sorted(ACTIONS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
