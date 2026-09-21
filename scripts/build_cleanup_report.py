#!/usr/bin/env python3
"""Build a local HTML deletion checklist from Maigret simple JSON reports."""

from __future__ import annotations

import argparse
import html
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

USER_AGENT = "Mozilla/5.0 (account-cleanup; local profile verification)"


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
    return ""


def flatten(value: Any, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).startswith("_"):
                continue
            name = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten(child, name))
    elif isinstance(value, list):
        if value and prefix:
            out[prefix] = ", ".join(map(str, value))
    elif value not in (None, "") and prefix:
        out[prefix] = str(value)
    return out


def iter_reports(root: Path):
    if root.is_file():
        yield root
    else:
        yield from sorted(root.rglob("report_*_simple.json"))


def load_rows(root: Path):
    rows = []
    for path in iter_reports(root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: {path}: {exc}")
            continue
        if not isinstance(data, dict):
            continue
        for site, item in data.items():
            if not isinstance(item, dict) or status_name(item).lower() != "claimed":
                continue
            st = item.get("status")
            st = st if isinstance(st, dict) else {}
            metadata = flatten(first(st.get("ids"), item.get("ids"), {}))
            username = str(first(st.get("username"), item.get("username"), metadata.get("username")))
            url = str(first(st.get("url"), item.get("url_user"), item.get("url")))
            if not url:
                continue
            rows.append(
                {
                    "site": str(site),
                    "username": username,
                    "url": url,
                    "metadata": metadata,
                    "source": str(path),
                }
            )
    return rows


def load_keep(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    return [
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def verify(url: str, timeout: float) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return str(r.status), r.geturl()
    except urllib.error.HTTPError as exc:
        return str(exc.code), exc.geturl()
    except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as exc:
        return "ERR", f"{url} ({exc})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="Maigret result directory or simple JSON report")
    ap.add_argument("-o", "--output", type=Path, default=Path("results/cleanup-report.html"))
    ap.add_argument("--keep-sites", type=Path, default=Path("config/keep-sites.txt"))
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--no-http", action="store_true", help="do not verify profile URLs")
    args = ap.parse_args()

    rows = load_rows(args.input)
    keep = load_keep(args.keep_sites)

    # De-duplicate exact Maigret hits.
    unique = {}
    for row in rows:
        unique[(row["site"], row["username"], row["url"])] = row
    rows = list(unique.values())

    for row in rows:
        row["keep"] = any(token in row["site"].lower() for token in keep)
        row["http"] = "-"
        row["final_url"] = row["url"]

    if not args.no_http:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {pool.submit(verify, row["url"], args.timeout): row for row in rows}
            for future in as_completed(futures):
                row = futures[future]
                row["http"], row["final_url"] = future.result()

    rows.sort(key=lambda r: (r["keep"], r["username"].lower(), r["site"].lower()))
    args.output.parent.mkdir(parents=True, exist_ok=True)

    body = []
    for i, row in enumerate(rows):
        meta = "<br>".join(
            f"<b>{html.escape(k)}</b>: {html.escape(v)}"
            for k, v in row["metadata"].items()
        )
        search_q = urllib.parse.quote_plus(
            f'{row["site"]} delete account remove account privacy'
        )
        search_url = f"https://www.google.com/search?q={search_q}"
        cls = "keep" if row["keep"] else ""
        default_state = "keep" if row["keep"] else "todo"
        body.append(
            f"""<tr class="{cls}" data-key="{html.escape(row["site"] + "|" + row["username"] + "|" + row["url"])}">
<td>{html.escape(row["username"])}</td>
<td>{html.escape(row["site"])}</td>
<td>{html.escape(row["http"])}</td>
<td>{meta}</td>
<td><a href="{html.escape(row["final_url"], quote=True)}">profile</a></td>
<td><a href="{html.escape(search_url, quote=True)}">find deletion</a></td>
<td>
<select class="state" data-default="{default_state}">
<option value="todo">to verify</option>
<option value="mine">mine</option>
<option value="requested">deletion requested</option>
<option value="deleted">deleted</option>
<option value="keep">keep</option>
<option value="false-positive">false positive</option>
</select>
</td>
</tr>"""
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Account cleanup</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #bbb; padding: .45rem; vertical-align: top; }}
th {{ position: sticky; top: 0; background: Canvas; }}
tr.keep {{ opacity: .65; }}
a {{ white-space: nowrap; }}
.controls {{ margin: 1rem 0; }}
</style>
</head>
<body>
<h1>Account cleanup</h1>
<p>{len(rows)} claimed Maigret profile(s). HTTP status only checks reachability; it does not prove ownership.</p>
<div class="controls">
<button id="show-open">show unfinished only</button>
<button id="show-all">show all</button>
</div>
<table>
<thead><tr>
<th>Username</th><th>Site</th><th>HTTP</th><th>Metadata</th>
<th>Profile</th><th>Deletion help</th><th>State</th>
</tr></thead>
<tbody>
{''.join(body)}
</tbody>
</table>
<script>
const doneStates = new Set(["deleted", "keep", "false-positive"]);
for (const row of document.querySelectorAll("tbody tr")) {{
  const select = row.querySelector(".state");
  const key = "account-cleanup:" + row.dataset.key;
  select.value = localStorage.getItem(key) || select.dataset.default || "todo";
  select.addEventListener("change", () => localStorage.setItem(key, select.value));
}}
document.getElementById("show-open").onclick = () => {{
  for (const row of document.querySelectorAll("tbody tr")) {{
    row.hidden = doneStates.has(row.querySelector(".state").value);
  }}
}};
document.getElementById("show-all").onclick = () => {{
  for (const row of document.querySelectorAll("tbody tr")) row.hidden = false;
}};
</script>
</body>
</html>
"""
    args.output.write_text(document, encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
