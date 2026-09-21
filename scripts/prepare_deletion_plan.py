#!/usr/bin/env python3
"""Build a per-profile deletion/contact plan from classified Maigret results."""
from __future__ import annotations

import argparse
import csv
import shlex
import urllib.parse
from pathlib import Path


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def expand(url: str, username: str) -> str:
    return url.replace("{username}", urllib.parse.quote(username, safe=""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--classified", type=Path, default=Path("results/extracts/maigret-classified.tsv"))
    ap.add_argument("--registry", type=Path, default=Path("config/site-channels.tsv"))
    ap.add_argument("-o", "--output", type=Path, default=Path("results/deletion-plan.tsv"))
    args = ap.parse_args()

    rows = read_tsv(args.classified)
    reg = {r["site"]: r for r in read_tsv(args.registry)}
    out = []

    for row in rows:
        meta = reg.get(row["site"], {})
        username = row["query_username"]
        site = row["site"]
        classification = row["classification"]
        profile = row["url"]
        mode = meta.get("mode", "UNCONFIGURED")
        delete_url = expand(meta.get("delete_url", ""), username)
        contact_url = expand(meta.get("contact_url", ""), username)

        if classification in {"keep", "false-positive", "deleted"}:
            action = "skip"
            command = ""
        elif site == "Ccm" and classification in {"cleanup", "requested"}:
            action = "ccm-http-or-contact"
            command = (
                "python3 scripts/http_account_cleanup.py ccm --username "
                + shlex.quote(username) + " --yes"
            )
        elif mode in {"no_account_result", "closed_service", "no_direct_delete"}:
            action = mode
            command = ""
        elif delete_url:
            action = "self-service-delete"
            command = "GET " + delete_url
        elif contact_url:
            action = "contact-form"
            command = "GET " + contact_url
        else:
            action = "manual-discovery"
            command = ""

        out.append({
            "classification": classification,
            "username": username,
            "site": site,
            "profile_url": profile,
            "mode": mode,
            "recommended_action": action,
            "delete_url": delete_url,
            "contact_url": contact_url,
            "command_or_probe": command,
            "notes": meta.get("notes", ""),
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "classification", "username", "site", "profile_url", "mode",
        "recommended_action", "delete_url", "contact_url", "command_or_probe", "notes"
    ]
    with args.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(out)

    print(f"Wrote {len(out)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
