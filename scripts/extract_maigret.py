#!/usr/bin/env python3
"""Extract Maigret claimed profiles into a compact TSV or JSON document.

When config/usernames.txt exists, only reports for those requested usernames are
kept. This prevents usernames discovered in profile metadata from being mixed
with the usernames that were actually scanned.
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
        if value and prefix:
            out[prefix] = ", ".join(map(str, value))
    elif value not in (None, "") and prefix:
        out[prefix] = str(value)
    return out


def iter_reports(root: Path):
    if root.is_file():
        yield root
        return
    yield from sorted(root.rglob("report_*_simple.json"))


def requested_username(path: Path) -> str:
    name = path.name
    prefix = "report_"
    suffix = "_simple.json"
    if name.startswith(prefix) and name.endswith(suffix):
        return name[len(prefix):-len(suffix)]
    return ""


def load_usernames(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    return {
        line.strip().casefold()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def parse_report(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return

    query_username = requested_username(path)

    for site, item in data.items():
        if not isinstance(item, dict):
            continue

        status = item.get("status")
        status_dict = status if isinstance(status, dict) else {}
        ids = first(status_dict.get("ids"), item.get("ids"), {})
        metadata = flatten_metadata(ids)

        detected_username = first(
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
            "query_username": query_username,
            "detected_username": str(detected_username),
            "site": str(site),
            "status": status_name(item),
            "url": str(url),
            "metadata": metadata,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="Maigret result directory or simple JSON report")
    ap.add_argument("--all", action="store_true", help="include non-claimed entries")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of TSV")
    ap.add_argument(
        "--usernames-file",
        type=Path,
        default=Path("config/usernames.txt"),
        help="allowlist of scanned usernames; filtering is disabled if the file does not exist",
    )
    args = ap.parse_args()

    allowed = load_usernames(args.usernames_file)
    rows = []

    for report in iter_reports(args.input):
        query = requested_username(report)
        if allowed and query.casefold() not in allowed:
            continue

        try:
            for row in parse_report(report):
                if args.all or row["status"].lower() == "claimed":
                    rows.append(row)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: {report}: {exc}", file=sys.stderr)

    rows.sort(key=lambda r: (r["query_username"].casefold(), r["site"].casefold()))

    if args.json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0

    print("query_username\tdetected_username\tsite\tstatus\turl\tmetadata\tsource")
    for row in rows:
        metadata = "; ".join(f"{k}={v}" for k, v in row["metadata"].items())
        fields = [
            row["query_username"],
            row["detected_username"],
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
