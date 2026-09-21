#!/usr/bin/env python3
"""Extract Maigret claimed profiles into a compact TSV or JSON document.

The parser is intentionally tolerant of small Maigret schema changes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def first(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return ""


def status_name(item: dict[str, Any]) -> str:
    status = item.get("status")
    if isinstance(status, str):
        return status
    if isinstance(status, dict):
        value = status.get("status")
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return str(first(value.get("name"), value.get("value")))
    return str(first(item.get("status_name"), item.get("status")))


def flatten_metadata(value: Any, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).startswith("_"):
                continue
            name = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten_metadata(child, name))
    elif isinstance(value, list):
        if value:
            out[prefix] = ", ".join(map(str, value))
    elif value not in (None, "") and prefix:
        out[prefix] = str(value)
    return out


def iter_reports(root: Path):
    if root.is_file():
        yield root
        return
    yield from sorted(root.rglob("report_*_simple.json"))


def parse_report(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return

    for site, item in data.items():
        if not isinstance(item, dict):
            continue

        status = item.get("status")
        status_dict = status if isinstance(status, dict) else {}
        ids = first(status_dict.get("ids"), item.get("ids"), {})
        metadata = flatten_metadata(ids)

        username = first(
            status_dict.get("username"),
            item.get("username"),
            metadata.get("username"),
        )
        url = first(
            status_dict.get("url"),
            item.get("url_user"),
            item.get("url"),
        )

        yield {
            "source": str(path),
            "site": str(site),
            "status": status_name(item),
            "username": str(username),
            "url": str(url),
            "metadata": metadata,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="Maigret result directory or simple JSON report")
    ap.add_argument("--all", action="store_true", help="include non-claimed entries")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of TSV")
    args = ap.parse_args()

    rows = []
    for report in iter_reports(args.input):
        try:
            for row in parse_report(report):
                if args.all or row["status"].lower() == "claimed":
                    rows.append(row)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: {report}: {exc}", file=sys.stderr)

    rows.sort(key=lambda r: (r["username"].lower(), r["site"].lower()))

    if args.json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0

    print("username\tsite\tstatus\turl\tmetadata\tsource")
    for row in rows:
        metadata = "; ".join(f"{k}={v}" for k, v in row["metadata"].items())
        fields = [
            row["username"],
            row["site"],
            row["status"],
            row["url"],
            metadata,
            row["source"],
        ]
        print("\t".join(str(v).replace("\t", " ").replace("\n", " ") for v in fields))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
