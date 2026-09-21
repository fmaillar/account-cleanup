#!/usr/bin/env python3
"""Build a local HTML dashboard from the classified Maigret TSV."""
from __future__ import annotations

import argparse
import csv
import html
import urllib.parse
from pathlib import Path

ACTIONABLE = {"review", "mine", "cleanup", "requested"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=Path("results/extracts/maigret-classified.tsv"),
    )
    ap.add_argument("-o", "--output", type=Path, default=Path("results/cleanup-report.html"))
    args = ap.parse_args()

    with args.input.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    rows.sort(key=lambda r: (
        r.get("classification", "") not in ACTIONABLE,
        r.get("query_username", "").casefold(),
        r.get("site", "").casefold(),
    ))

    body = []
    for row in rows:
        action = row.get("classification", "review")
        hidden = "" if action in ACTIONABLE else " hidden"
        profile = row.get("url", "")
        search_q = urllib.parse.quote_plus(f'{row.get("site", "")} delete account remove account privacy')
        search_url = f"https://www.google.com/search?q={search_q}"
        body.append(f"""<tr data-action="{html.escape(action)}"{hidden}>
<td>{html.escape(row.get('query_username',''))}</td>
<td>{html.escape(row.get('detected_username',''))}</td>
<td>{html.escape(row.get('site',''))}</td>
<td><b>{html.escape(action)}</b><br><small>{html.escape(row.get('reason',''))}</small></td>
<td>{html.escape(row.get('metadata',''))}</td>
<td><a href="{html.escape(profile, quote=True)}">profile</a></td>
<td><a href="{html.escape(search_url, quote=True)}">deletion help</a></td>
</tr>""")

    counts = {}
    for row in rows:
        action = row.get("classification", "review")
        counts[action] = counts.get(action, 0) + 1
    summary = " · ".join(f"{html.escape(k)}={v}" for k, v in sorted(counts.items()))

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Account cleanup</title>
<style>
body{{font-family:sans-serif;margin:2rem}} table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #bbb;padding:.45rem;vertical-align:top}} th{{position:sticky;top:0;background:Canvas}}
.controls{{margin:1rem 0}} small{{opacity:.8}} td:nth-child(5){{max-width:45rem;overflow-wrap:anywhere}}
</style></head><body>
<h1>Account cleanup</h1><p>{summary}</p>
<div class="controls"><button onclick="showActionable()">actionable only</button> <button onclick="showAll()">show all</button></div>
<table><thead><tr><th>Scanned username</th><th>Detected username</th><th>Site</th><th>Classification</th><th>Metadata</th><th>Profile</th><th>Deletion</th></tr></thead>
<tbody>{''.join(body)}</tbody></table>
<script>
const actionable=new Set(['review','mine','cleanup','requested']);
function showActionable(){{for(const r of document.querySelectorAll('tbody tr'))r.hidden=!actionable.has(r.dataset.action)}}
function showAll(){{for(const r of document.querySelectorAll('tbody tr'))r.hidden=false}}
</script></body></html>"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(doc, encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
