#!/usr/bin/env python3
"""Classify Maigret claimed profiles into cleanup, keep, and likely false positives."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def load_tokens(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    return [
        line.strip().casefold()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def is_mismatch(query: str, detected: str) -> bool:
    return bool(detected.strip()) and query.casefold() != detected.casefold()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "input",
        type=Path,
        default=Path("results/extracts/maigret-claimed.tsv"),
        nargs="?",
    )
    ap.add_argument("--keep-sites", type=Path, default=Path("config/keep-sites.txt"))
    ap.add_argument("--ignore-sites", type=Path, default=Path("config/ignore-sites.txt"))
    ap.add_argument("--outdir", type=Path, default=Path("results/extracts"))
    args = ap.parse_args()

    keep = load_tokens(args.keep_sites)
    ignore = load_tokens(args.ignore_sites)
    args.outdir.mkdir(parents=True, exist_ok=True)

    with args.input.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    buckets = {"cleanup": [], "keep": [], "false-positive": [], "review": []}

    for row in rows:
        site = row["site"].casefold()
        query = row["query_username"]
        detected = row["detected_username"]

        if any(token in site for token in keep):
            bucket, reason = "keep", "site configured to keep"
        elif any(token in site for token in ignore):
            bucket, reason = "false-positive", "site configured to ignore"
        elif is_mismatch(query, detected):
            bucket, reason = "false-positive", "detected username differs from scanned username"
        else:
            bucket, reason = "review", "manual ownership check required"

        row["classification"] = bucket
        row["reason"] = reason
        buckets[bucket].append(row)

    fields = list(rows[0].keys()) if rows else [
        "query_username", "detected_username", "site", "status", "url",
        "metadata", "source", "classification", "reason"
    ]

    for bucket, bucket_rows in buckets.items():
        path = args.outdir / f"maigret-{bucket}.tsv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
            w.writeheader()
            w.writerows(bucket_rows)

    print(
        "classified "
        + ", ".join(f"{name}={len(items)}" for name, items in buckets.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
