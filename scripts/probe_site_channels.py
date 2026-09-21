#!/usr/bin/env python3
"""Probe official deletion/contact channels for every site in Maigret results.

GET-only by default. It never submits a destructive request.
"""
from __future__ import annotations

import argparse
import csv
import html.parser
import http.cookiejar
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) account-cleanup/1.0"


class FormCounter(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms = 0

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            self.forms += 1


@dataclass
class Probe:
    status: str
    final_url: str
    forms: int
    error: str = ""


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def expand(url: str, username: str) -> str:
    return url.replace("{username}", urllib.parse.quote(username, safe=""))


def probe(url: str, timeout: float) -> Probe:
    if not url:
        return Probe("-", "", 0)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    try:
        with opener.open(req, timeout=timeout) as r:
            body = r.read(2_000_000).decode(
                r.headers.get_content_charset() or "utf-8", "replace"
            )
            p = FormCounter()
            p.feed(body)
            return Probe(str(r.status), r.geturl(), p.forms)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(2_000_000).decode("utf-8", "replace")
            p = FormCounter()
            p.feed(body)
            forms = p.forms
        except Exception:
            forms = 0
        return Probe(str(exc.code), exc.geturl(), forms, str(exc))
    except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as exc:
        return Probe("ERR", url, 0, str(exc))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--classified",
        type=Path,
        default=Path("results/extracts/maigret-classified.tsv"),
    )
    ap.add_argument(
        "--registry",
        type=Path,
        default=Path("config/site-channels.tsv"),
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("results/site-channels.tsv"),
    )
    ap.add_argument("--timeout", type=float, default=12.0)
    args = ap.parse_args()

    rows = read_tsv(args.classified)
    registry = {r["site"]: r for r in read_tsv(args.registry)}

    # One representative username per discovered site is enough to expand
    # username-templated endpoints such as Launchpad.
    sites: dict[str, str] = {}
    for row in rows:
        sites.setdefault(row["site"], row["query_username"])

    out = []
    for site in sorted(sites, key=str.casefold):
        username = sites[site]
        meta = registry.get(site)
        if not meta:
            out.append({
                "site": site,
                "mode": "UNCONFIGURED",
                "delete_url": "",
                "delete_status": "-",
                "delete_final": "",
                "delete_forms": "0",
                "contact_url": "",
                "contact_status": "-",
                "contact_final": "",
                "contact_forms": "0",
                "notes": "No registry entry",
            })
            continue

        delete_url = expand(meta.get("delete_url", ""), username)
        contact_url = expand(meta.get("contact_url", ""), username)
        dp = probe(delete_url, args.timeout)
        cp = probe(contact_url, args.timeout)

        out.append({
            "site": site,
            "mode": meta.get("mode", ""),
            "delete_url": delete_url,
            "delete_status": dp.status,
            "delete_final": dp.final_url,
            "delete_forms": str(dp.forms),
            "contact_url": contact_url,
            "contact_status": cp.status,
            "contact_final": cp.final_url,
            "contact_forms": str(cp.forms),
            "notes": meta.get("notes", ""),
        })
        print(
            f"{site}: delete={dp.status} forms={dp.forms} "
            f"contact={cp.status} forms={cp.forms}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "site", "mode",
        "delete_url", "delete_status", "delete_final", "delete_forms",
        "contact_url", "contact_status", "contact_final", "contact_forms",
        "notes",
    ]
    with args.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(out)

    missing = [r["site"] for r in out if r["mode"] == "UNCONFIGURED"]
    if missing:
        print("UNCONFIGURED:", ", ".join(missing))
        return 1

    print(f"Wrote {len(out)} site probes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
