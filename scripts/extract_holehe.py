#!/usr/bin/env python3
"""Extract concise Holehe results from one or more text reports."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

LINE_RE = re.compile(r"^\[([+\-x])\]\s+(.+?)\s*$")
LABELS = {"+": "used", "-": "not-used", "x": "indeterminate"}


def parse(path: Path):
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE_RE.match(raw.strip())
        if not m:
            continue
        mark, site = m.groups()
        # Ignore Holehe's own legend.
        if site.startswith("Email used,"):
            continue
        yield mark, site


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument(
        "--all",
        action="store_true",
        help="include negatives and rate-limited/indeterminate entries",
    )
    args = ap.parse_args()

    print("source\tstatus\tsite")
    for path in args.paths:
        for mark, site in parse(path):
            if not args.all and mark != "+":
                continue
            print(f"{path}\t{LABELS[mark]}\t{site}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
