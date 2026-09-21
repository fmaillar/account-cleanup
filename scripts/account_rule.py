#!/usr/bin/env python3
"""Manage the private exact/wildcard account classification rule file."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from cleanup_rules import ACTIONS, load_rules

FIELDS = ["username", "site", "action", "reason"]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in FIELDS})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=Path("config/account-rules.tsv"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    pset = sub.add_parser("set")
    pset.add_argument("username")
    pset.add_argument("site")
    pset.add_argument("action", choices=sorted(ACTIONS))
    pset.add_argument("reason", nargs="?", default="")

    sub.add_parser("list")

    pdel = sub.add_parser("delete")
    pdel.add_argument("username")
    pdel.add_argument("site")

    args = ap.parse_args()

    if args.cmd == "list":
        if not args.file.exists():
            return 0
        print(args.file.read_text(encoding="utf-8"), end="")
        return 0

    rows = read_rows(args.file)
    key = (args.username.casefold(), args.site.casefold())
    rows = [r for r in rows if (r.get("username", "").casefold(), r.get("site", "").casefold()) != key]

    if args.cmd == "set":
        rows.append({"username": args.username, "site": args.site, "action": args.action, "reason": args.reason})

    write_rows(args.file, rows)
    load_rules(args.file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
