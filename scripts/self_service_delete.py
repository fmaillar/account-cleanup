#!/usr/bin/env python3
"""Generic authenticated HTML self-service account deletion.

This handles ordinary server-rendered flows:
GET delete URL -> detect login form -> authenticate -> GET delete URL again ->
detect deletion/deactivation form -> preserve hidden/CSRF fields -> optionally
submit with --yes.

It refuses ambiguous forms and JS/CAPTCHA-only flows instead of posting blindly.
"""
from __future__ import annotations

import argparse
import getpass
import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) account-cleanup/1.0"
DELETE_RE = re.compile(r"(delete|deactivat|close|remove|terminate|cancel|supprim|désactiv)", re.I)
LOGIN_RE = re.compile(r"(user|login|email|mail|name|identifier)", re.I)
SUCCESS_RE = re.compile(
    r"(account.{0,40}(deleted|deactivated|closed|removed)|"
    r"(deleted|deactivated|closed|removed).{0,40}account|"
    r"compte.{0,40}(supprim|désactiv|fermé))",
    re.I | re.S,
)
CAPTCHA_RE = re.compile(r"(g-recaptcha|hcaptcha|recaptcha|cf-turnstile|captcha)", re.I)
AUTH_RE = re.compile(r"(login|log[-_ ]?in|sign[-_ ]?in|openid|oauth|auth)", re.I)


@dataclass
class Form:
    action: str
    method: str = "get"
    attrs: dict[str, str] = field(default_factory=dict)
    inputs: list[dict[str, str]] = field(default_factory=list)
    buttons: list[dict[str, str]] = field(default_factory=list)
    textareas: list[dict[str, str]] = field(default_factory=list)
    text: str = ""


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[Form] = []
        self.current: Form | None = None
        self.in_button = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.current = Form(a.get("action", ""), a.get("method", "get").lower(), a)
            self.forms.append(self.current)
        elif self.current and tag == "input":
            self.current.inputs.append(a)
        elif self.current and tag == "textarea":
            self.current.textareas.append(a)
        elif self.current and tag == "button":
            self.current.buttons.append(a)
            self.in_button = True

    def handle_endtag(self, tag):
        if tag == "button":
            self.in_button = False
        elif tag == "form":
            self.current = None

    def handle_data(self, data):
        if self.current:
            self.current.text += " " + data
            if self.in_button and self.current.buttons:
                self.current.buttons[-1]["_text"] = (
                    self.current.buttons[-1].get("_text", "") + " " + data
                ).strip()


class Browser:
    def __init__(self) -> None:
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def request(self, url: str, *, data: dict[str, str] | None = None, method: str | None = None):
        body = None if data is None else urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"},
        )
        try:
            with self.opener.open(req, timeout=25) as r:
                text = r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")
                return r.status, r.geturl(), text
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            return exc.code, exc.geturl(), text

    def get(self, url: str):
        return self.request(url)


def parse_forms(body: str) -> list[Form]:
    p = Parser()
    p.feed(body)
    return p.forms


def form_blob(form: Form) -> str:
    fields = [form.action, form.text]
    for a in form.inputs + form.buttons + form.textareas:
        fields.extend(str(a.get(k, "")) for k in ("name", "id", "value", "placeholder", "_text"))
    return " ".join(fields)


def is_login_form(form: Form) -> bool:
    return any(i.get("type", "").lower() == "password" for i in form.inputs) and not DELETE_RE.search(form_blob(form))


def deletion_score(form: Form) -> int:
    blob = form_blob(form)

    # Never classify authentication/OpenID/OAuth forms as deletion forms,
    # even if the surrounding page text mentions "deactivate" or "delete".
    auth_blob = " ".join([
        form.action,
        form.attrs.get("id", ""),
        form.attrs.get("name", ""),
        form.attrs.get("class", ""),
    ])
    if AUTH_RE.search(auth_blob):
        return -100

    if any(i.get("type", "").lower() == "password" for i in form.inputs) and not any(
        DELETE_RE.search(
            " ".join(str(x.get(k, "")) for k in ("name", "id", "value", "placeholder"))
        )
        for x in form.inputs + form.buttons
    ):
        return -100

    score = 0
    # Strong evidence must come from controls/action, not arbitrary surrounding text.
    if DELETE_RE.search(form.action):
        score += 12
    for b in form.buttons:
        if DELETE_RE.search(" ".join(str(v) for v in b.values())):
            score += 10
    for i in form.inputs:
        if i.get("type", "").lower() == "submit" and DELETE_RE.search(
            i.get("value", "") + " " + i.get("name", "") + " " + i.get("id", "")
        ):
            score += 10
    if form.method == "post" and score:
        score += 3
    return score


def pick_delete_form(forms: list[Form]) -> Form | None:
    ranked = sorted(((deletion_score(f), f) for f in forms), key=lambda x: x[0], reverse=True)
    if not ranked or ranked[0][0] < 12:
        return None
    return ranked[0][1]


def pick_login_form(forms: list[Form]) -> Form | None:
    return next((f for f in forms if is_login_form(f)), None)


def input_names(form: Form) -> tuple[str | None, str | None]:
    password = next(
        (i.get("name") for i in form.inputs if i.get("type", "").lower() == "password" and i.get("name")),
        None,
    )
    user = next(
        (
            i.get("name")
            for i in form.inputs
            if i.get("name")
            and i.get("type", "text").lower() in {"text", "email"}
            and LOGIN_RE.search(i.get("name", "") + " " + i.get("id", ""))
        ),
        None,
    )
    if not user:
        user = next(
            (i.get("name") for i in form.inputs if i.get("name") and i.get("type", "text").lower() in {"text", "email"}),
            None,
        )
    return user, password


def build_payload(form: Form) -> dict[str, str]:
    data: dict[str, str] = {}
    for i in form.inputs:
        name = i.get("name")
        if not name:
            continue
        typ = i.get("type", "text").lower()
        if typ in {"file", "image", "button"}:
            continue
        if typ in {"checkbox", "radio"}:
            if "checked" in i or "required" in i:
                data[name] = i.get("value", "1") or "1"
            continue
        if typ == "submit":
            if DELETE_RE.search(i.get("value", "") + " " + name):
                data[name] = i.get("value", "")
            continue
        data[name] = i.get("value", "")

    for b in form.buttons:
        name = b.get("name")
        if name and DELETE_RE.search(
            b.get("value", "") + " " + b.get("_text", "") + " " + name
        ):
            data[name] = b.get("value", "") or b.get("_text", "")
    return data



def add_login_submit(form: Form, data: dict[str, str]) -> None:
    """Include the first named login submit control when the server expects it."""
    for i in form.inputs:
        if i.get("type", "").lower() == "submit" and i.get("name"):
            data.setdefault(i["name"], i.get("value", ""))
            return
    for b in form.buttons:
        if b.get("name"):
            data.setdefault(b["name"], b.get("value", "") or b.get("_text", ""))
            return

def submit(browser: Browser, base: str, form: Form, data: dict[str, str]):
    target = urllib.parse.urljoin(base, form.action or base)
    if form.method == "post":
        return browser.request(target, data=data, method="POST")
    q = urllib.parse.urlencode(data)
    return browser.get(target + (("&" if urllib.parse.urlparse(target).query else "?") + q if q else ""))


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--username", required=True)
    ap.add_argument("--delete-url", required=True)
    ap.add_argument("--login", help="login identifier; defaults to username")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    b = Browser()
    outdir = Path("results/self-service")
    outdir.mkdir(parents=True, exist_ok=True)
    stem = safe_name(f"{args.site}-{args.username}")

    status, url, body = b.get(args.delete_url)
    (outdir / f"{stem}-initial.html").write_text(body, encoding="utf-8")
    print(f"GET {args.delete_url} -> {status} {url}")

    if CAPTCHA_RE.search(body):
        print("BLOCKED: CAPTCHA/anti-bot challenge detected; no POST attempted.")
        return 4

    forms = parse_forms(body)

    parsed_url = urllib.parse.urlparse(url)
    auth_redirect = (
        AUTH_RE.search(parsed_url.path or "") is not None
        or AUTH_RE.search(parsed_url.netloc or "") is not None
    )

    delete_form = None if auth_redirect else pick_delete_form(forms)
    password: str | None = None

    if delete_form is None:
        login_form = pick_login_form(forms)
        if login_form is None:
            if auth_redirect:
                print("BLOCKED: redirected to an authentication/OpenID/OAuth flow that is not a simple HTML username/password form.")
                return 6
            print("BLOCKED: no server-rendered login or deletion form found (likely JS/OAuth/manual flow).")
            return 3

        user_field, pass_field = input_names(login_form)
        if not pass_field:
            print("BLOCKED: could not identify login password field.")
            return 3

        login_value = args.login or input(f"Login identifier [{args.username}]: ").strip() or args.username
        password = getpass.getpass(f"{args.site} password: ")
        values = build_payload(login_form)
        add_login_submit(login_form, values)
        if user_field:
            values[user_field] = login_value
        values[pass_field] = password

        status, url, body = submit(b, url, login_form, values)
        (outdir / f"{stem}-after-login.html").write_text(body, encoding="utf-8")
        print(f"LOGIN -> {status} {url}")
        if "/login" in urllib.parse.urlparse(url).path.casefold() and pick_login_form(parse_forms(body)):
            print("BLOCKED: login was not accepted; credentials or an extra authentication step are required.")
            return 5

        status, url, body = b.get(args.delete_url)
        (outdir / f"{stem}-delete-page.html").write_text(body, encoding="utf-8")
        print(f"GET delete page -> {status} {url}")

        if CAPTCHA_RE.search(body):
            print("BLOCKED: CAPTCHA/anti-bot challenge detected after login.")
            return 4

        delete_form = pick_delete_form(parse_forms(body))
        if delete_form is None:
            print("BLOCKED: authenticated page has no unambiguous server-rendered deletion form.")
            return 3

    score = deletion_score(delete_form)
    target = urllib.parse.urljoin(url, delete_form.action or url)
    print(f"Deletion form score={score}: {delete_form.method.upper()} {target}")

    values = build_payload(delete_form)
    for i in delete_form.inputs:
        if i.get("type", "").lower() == "password" and i.get("name"):
            if password is None:
                password = getpass.getpass(f"{args.site} password for deletion: ")
            values[i["name"]] = password

    if not args.yes:
        print("DRY-RUN: deletion form identified; add --yes to submit.")
        return 0

    status, final_url, response = submit(b, url, delete_form, values)
    (outdir / f"{stem}-response.html").write_text(response, encoding="utf-8")
    print(f"DELETE REQUEST -> {status} {final_url}")

    if SUCCESS_RE.search(response):
        print("SUCCESS: site response explicitly indicates account deletion/deactivation/closure.")
        return 0

    if final_url != target and not DELETE_RE.search(final_url):
        print("SUBMITTED: redirected away from deletion endpoint; verify account/profile disappearance.")
        return 0

    print("SUBMITTED: no explicit success text detected; verify account/profile disappearance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
