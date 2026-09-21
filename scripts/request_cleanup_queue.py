#!/usr/bin/env python3
"""Process every explicitly-confirmed cleanup row in one pass.

For CCM, uses the dedicated authenticated HTTP adapter.
For other sites, attempts the official web contact form from site-channels.tsv.
Self-service delete URLs are still included in the summary because many require
site-specific authentication/2FA and cannot be safely guessed.
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path


def read_tsv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", type=Path, default=Path("results/extracts/maigret-cleanup.tsv"))
    ap.add_argument("--from-email", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--registry", type=Path, default=Path("config/site-channels.tsv"))
    args = ap.parse_args()

    rows = read_tsv(args.queue)
    registry = {r["site"]: r for r in read_tsv(args.registry)}
    summary = []

    for row in rows:
        site = row["site"]
        username = row["query_username"]
        profile = row["url"]
        meta = registry.get(site, {})
        contact = meta.get("contact_url", "")
        delete_url = meta.get("delete_url", "")

        print(f"\n=== {site} / {username} ===")

        if site == "Ccm":
            cmd = [
                sys.executable,
                "scripts/http_account_cleanup.py",
                "ccm",
                "--username",
                username,
            ]
            if args.yes:
                cmd.append("--yes")
            rc = subprocess.run(cmd, check=False).returncode
            summary.append((site, username, "ccm-adapter", str(rc)))
            continue

        if contact:
            cmd = [
                sys.executable,
                "scripts/contact_privacy_request.py",
                "--site",
                site,
                "--username",
                username,
                "--profile-url",
                profile,
                "--from-email",
                args.from_email,
                "--name",
                args.name,
            ]
            if args.yes:
                cmd.append("--yes")
            rc = subprocess.run(cmd, check=False).returncode
            summary.append((site, username, "contact-form", str(rc)))
        elif delete_url:
            print(f"Self-service deletion URL: {delete_url}")
            summary.append((site, username, "self-service", "not-submitted"))
        else:
            print("No configured deletion/contact channel.")
            summary.append((site, username, "unconfigured", "not-submitted"))

    out = Path("results/cleanup-request-summary.tsv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["site", "username", "method", "result"])
        w.writerows(summary)

    print(f"\nWrote summary to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
