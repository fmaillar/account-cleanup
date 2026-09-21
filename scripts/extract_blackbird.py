#!/usr/bin/env python3
"""Extract positive Blackbird hits from terminal/text reports."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# Example:
# ✔️  [Spotify] https://example/...
HIT_RE = re.compile(r"^\s*✔️?\s*\[([^]]+)\]\s+(https?://\S+)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args()

    print("source\tsite\turl")
    for path in args.paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for raw in text.splitlines():
            m = HIT_RE.match(raw)
            if m:
                site, url = m.groups()
                print(f"{path}\t{site}\t{url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
