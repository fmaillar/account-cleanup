#!/usr/bin/env python3
"""Process every explicitly-confirmed cleanup row.

Priority:
1. dedicated site adapter;
2. authenticated self-service deletion URL;
3. contact/privacy form only for sites without a self-service deletion flow.

The runner never acts on review/keep/false-positive rows.
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
    ap.add_argument(
        "--allow-contact-fallback",
        action="store_true",
        help="allow generic contact/privacy forms only when no self-service deletion URL exists",
    )
    args = ap.parse_args()

    rows = read_tsv(args.queue)
    registry = {r["site"]: r for r in read_tsv(args.registry)}
    summary = []

    for row in rows:
        site = row["site"]
        username = row["query_username"]
        profile = row["url"]
        meta = registry.get(site, {})
        mode = meta.get("mode", "")
        contact = meta.get("contact_url", "")
        delete_url = meta.get("delete_url", "").replace("{username}", username)

        print(f"\n=== {site} / {username} ===")

        if site == "Ccm":
            cmd = [
                sys.executable, "scripts/http_account_cleanup.py", "ccm",
                "--username", username,
            ]
            if args.yes:
                cmd.append("--yes")
            rc = subprocess.run(cmd, check=False).returncode
            summary.append((site, username, "dedicated-adapter", str(rc)))
            continue

        if mode == "self_service" and delete_url:
            cmd = [
                sys.executable, "scripts/self_service_delete.py",
                "--site", site,
                "--username", username,
                "--delete-url", delete_url,
            ]
            if args.yes:
                cmd.append("--yes")
            rc = subprocess.run(cmd, check=False).returncode
            summary.append((site, username, "self-service", str(rc)))
            continue

        if mode == "shared_account":
            print("SKIP: deletion would affect a shared parent account; dedicated adapter/manual confirmation required.")
            if delete_url:
                print(f"Parent-account URL: {delete_url}")
            summary.append((site, username, "shared-account-skip", "not-submitted"))
            continue

        if args.allow_contact_fallback and contact:
            cmd = [
                sys.executable, "scripts/contact_privacy_request.py",
                "--site", site,
                "--username", username,
                "--profile-url", profile,
                "--from-email", args.from_email,
                "--name", args.name,
            ]
            if args.yes:
                cmd.append("--yes")
            rc = subprocess.run(cmd, check=False).returncode
            summary.append((site, username, "contact-fallback", str(rc)))
            continue

        if contact:
            print("CONTACT AVAILABLE but not used automatically; pass --allow-contact-fallback if desired.")
            print(f"Contact URL: {contact}")
            summary.append((site, username, "contact-available", "not-submitted"))
        else:
            print("No automatable deletion channel configured.")
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
