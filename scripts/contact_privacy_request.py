#!/usr/bin/env python3
"""Submit privacy/account-erasure requests through official web contact forms.

The registry supplies the official contact URL. This script GETs that page,
preserves hidden/CSRF fields, finds the most likely support/contact form, fills
common identity/message fields, and POSTs only with --yes.

It deliberately refuses forms that appear to require CAPTCHA/reCAPTCHA.
"""
from __future__ import annotations

import argparse
import csv
import html
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) account-cleanup/1.0"


@dataclass
class Form:
    action: str
    method: str = "get"
    inputs: list[dict[str, str]] = field(default_factory=list)
    textareas: list[dict[str, str]] = field(default_factory=list)
    buttons: list[dict[str, str]] = field(default_factory=list)


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[Form] = []
        self.current: Form | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.current = Form(a.get("action", ""), a.get("method", "get").lower())
            self.forms.append(self.current)
        elif self.current and tag == "input":
            self.current.inputs.append(a)
        elif self.current and tag == "textarea":
            self.current.textareas.append(a)
        elif self.current and tag == "button":
            self.current.buttons.append(a)

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


def load_registry(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return {r["site"]: r for r in csv.DictReader(f, delimiter="\t")}


def fetch(url: str):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"},
    )
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    with opener.open(req, timeout=20) as r:
        body = r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")
        return opener, r.status, r.geturl(), body


def parse_forms(body: str) -> list[Form]:
    p = Parser()
    p.feed(body)
    return p.forms


def attr_blob(a: dict[str, str]) -> str:
    return " ".join(
        str(a.get(k, "")) for k in ("name", "id", "placeholder", "type", "value")
    ).casefold()


def score_form(form: Form) -> int:
    blob = " ".join(
        [form.action]
        + [attr_blob(x) for x in form.inputs]
        + [attr_blob(x) for x in form.textareas]
        + [attr_blob(x) for x in form.buttons]
    )
    score = 0
    for token, points in (
        ("email", 5),
        ("subject", 4),
        ("message", 6),
        ("contact", 4),
        ("request", 3),
        ("privacy", 5),
        ("name", 2),
    ):
        if token in blob:
            score += points
    if form.textareas:
        score += 6
    if form.method == "post":
        score += 4
    return score


def pick_form(forms: list[Form]) -> Form:
    if not forms:
        raise RuntimeError("no HTML form found")
    scored = sorted(((score_form(f), f) for f in forms), key=lambda x: x[0], reverse=True)
    if scored[0][0] < 6:
        raise RuntimeError("no plausible contact/privacy form found")
    return scored[0][1]


def captcha_present(body: str, form: Form) -> bool:
    blob = body.casefold() + " " + " ".join(attr_blob(x) for x in form.inputs)
    return any(x in blob for x in ("g-recaptcha", "hcaptcha", "recaptcha", "cf-turnstile"))


def field_kind(attrs: dict[str, str]) -> str | None:
    blob = attr_blob(attrs)
    typ = attrs.get("type", "").casefold()
    if typ == "email" or re.search(r"(^|[^a-z])e[-_ ]?mail([^a-z]|$)", blob):
        return "email"
    if "subject" in blob or "objet" in blob:
        return "subject"
    if re.search(r"(^|[^a-z])(full[-_ ]?name|name|nom)([^a-z]|$)", blob):
        return "name"
    if any(x in blob for x in ("message", "description", "details", "request", "comment", "body")):
        return "message"
    return None


def build_payload(form: Form, *, name: str, email: str, subject: str, message: str):
    data: dict[str, str] = {}
    mapped: dict[str, str] = {}

    for inp in form.inputs:
        key = inp.get("name")
        if not key:
            continue
        typ = inp.get("type", "text").casefold()
        if typ in {"submit", "button", "image", "file"}:
            continue
        if typ in {"checkbox", "radio"} and "checked" not in inp:
            continue
        data[key] = inp.get("value", "")
        kind = field_kind(inp)
        if kind:
            mapped.setdefault(kind, key)

    for ta in form.textareas:
        key = ta.get("name")
        if not key:
            continue
        kind = field_kind(ta) or "message"
        mapped.setdefault(kind, key)
        data.setdefault(key, "")

    values = {"name": name, "email": email, "subject": subject, "message": message}
    for kind, value in values.items():
        key = mapped.get(kind)
        if key:
            data[key] = value

    return data, mapped


def submit(opener, base_url: str, form: Form, data: dict[str, str]):
    target = urllib.parse.urljoin(base_url, form.action or base_url)
    encoded = urllib.parse.urlencode(data).encode()
    method = form.method.upper()
    if method == "GET":
        q = urllib.parse.urlencode(data)
        target += ("&" if urllib.parse.urlparse(target).query else "?") + q
        encoded = None
    req = urllib.request.Request(
        target,
        data=encoded,
        method=method,
        headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"},
    )
    with opener.open(req, timeout=20) as r:
        body = r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")
        return r.status, r.geturl(), body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--username", required=True)
    ap.add_argument("--profile-url", required=True)
    ap.add_argument("--from-email", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--registry", type=Path, default=Path("config/site-channels.tsv"))
    ap.add_argument("--yes", action="store_true", help="actually submit the form")
    args = ap.parse_args()

    registry = load_registry(args.registry)
    meta = registry.get(args.site)
    if not meta:
        raise SystemExit(f"site not present in registry: {args.site}")

    contact = meta.get("contact_url", "").replace(
        "{username}", urllib.parse.quote(args.username, safe="")
    )
    if not contact:
        raise SystemExit(f"{args.site}: no web contact URL configured")

    subject = f"Account/profile erasure request: {args.username}"
    message = f"""Hello,

I am requesting deletion/erasure of my old account and public profile on your service.

Username: {args.username}
Public profile: {args.profile_url}

Please delete the account/profile and erase the associated personal data to the
extent applicable. Please confirm when the public profile is no longer
accessible.

This request concerns my own account and personal data.

Regards,
{args.name}
"""

    opener, status, final_url, body = fetch(contact)
    print(f"GET {contact} -> {status} {final_url}")

    outdir = Path("results/contact-requests")
    outdir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{args.site}-{args.username}")
    (outdir / f"{stem}-page.html").write_text(body, encoding="utf-8")

    forms = parse_forms(body)
    form = pick_form(forms)
    if captcha_present(body, form):
        raise SystemExit(
            f"{args.site}: contact form contains CAPTCHA/anti-bot challenge; "
            "saved page for manual completion"
        )

    data, mapped = build_payload(
        form,
        name=args.name,
        email=args.from_email,
        subject=subject,
        message=message,
    )

    required = {"email", "message"}
    missing = sorted(required - set(mapped))
    if missing:
        raise SystemExit(
            f"{args.site}: could not identify required field(s): {', '.join(missing)}"
        )

    preview = outdir / f"{stem}-request.txt"
    preview.write_text(
        f"site={args.site}\ncontact={contact}\nform_action={form.action}\n"
        f"method={form.method}\nfields={mapped}\n\n{subject}\n\n{message}",
        encoding="utf-8",
    )
    print(f"Prepared: {preview}")

    if not args.yes:
        print("Dry-run only; re-run with --yes to submit.")
        return 0

    status, final_url, response = submit(opener, final_url, form, data)
    response_path = outdir / f"{stem}-response.html"
    response_path.write_text(response, encoding="utf-8")
    print(f"SUBMIT -> {status} {final_url}")
    print(f"Saved response: {response_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
