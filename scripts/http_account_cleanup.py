#!/usr/bin/env python3
"""HTTP account cleanup adapters.

Currently implements CCM end-to-end:
  - GET the official delete-account URL
  - follow redirect to login
  - submit the login form while preserving hidden/CSRF fields and cookies
  - GET the delete-account URL again
  - submit the deletion confirmation form

Passwords are read with getpass and are never written to disk.
"""
from __future__ import annotations

import argparse
import getpass
import http.cookiejar
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from dataclasses import dataclass, field
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) account-cleanup/1.0"


@dataclass
class Form:
    action: str
    method: str = "get"
    inputs: list[dict[str, str]] = field(default_factory=list)
    buttons: list[dict[str, str]] = field(default_factory=list)


class FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[Form] = []
        self.current: Form | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.current = Form(
                action=a.get("action", ""),
                method=a.get("method", "get").lower(),
            )
            self.forms.append(self.current)
        elif self.current and tag == "input":
            self.current.inputs.append(a)
        elif self.current and tag == "button":
            self.current.buttons.append(a)

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


class Browser:
    def __init__(self) -> None:
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def request(self, url: str, *, data: dict[str, str] | None = None, method: str | None = None):
        encoded = None if data is None else urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(
            url,
            data=encoded,
            method=method,
            headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"},
        )
        with self.opener.open(req, timeout=20) as r:
            body = r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")
            return r.status, r.geturl(), body

    def get(self, url: str):
        return self.request(url)

    def submit(self, base_url: str, form: Form, values: dict[str, str]):
        target = urllib.parse.urljoin(base_url, form.action or base_url)
        data: dict[str, str] = {}
        for inp in form.inputs:
            name = inp.get("name")
            if not name:
                continue
            typ = inp.get("type", "text").lower()
            if typ in {"submit", "button", "image", "file"}:
                continue
            if typ in {"checkbox", "radio"} and "checked" not in inp:
                continue
            data[name] = inp.get("value", "")
        data.update(values)

        if form.method == "post":
            return self.request(target, data=data, method="POST")

        q = urllib.parse.urlencode(data)
        sep = "&" if urllib.parse.urlparse(target).query else "?"
        return self.get(target + (sep + q if q else ""))


def parse_forms(html: str) -> list[Form]:
    p = FormParser()
    p.feed(html)
    return p.forms


def choose_login_form(forms: list[Form]) -> Form:
    for form in forms:
        if any(i.get("type", "").lower() == "password" for i in form.inputs):
            return form
    raise RuntimeError("login form not found")


def login_field_names(form: Form) -> tuple[str, str]:
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
            and re.search(r"(user|login|email|name)", i.get("name", ""), re.I)
        ),
        None,
    )
    if not user:
        user = next(
            (i.get("name") for i in form.inputs if i.get("name") and i.get("type", "text").lower() in {"text", "email"}),
            None,
        )
    if not user or not password:
        raise RuntimeError("could not identify username/password fields")
    return user, password


def choose_delete_form(forms: list[Form]) -> Form:
    keywords = re.compile(r"(delete|remove|cancel|close|unsubscribe|supprim)", re.I)
    ranked: list[tuple[int, Form]] = []
    for form in forms:
        hay = " ".join(
            [form.action]
            + [i.get("name", "") + " " + i.get("value", "") for i in form.inputs]
            + [b.get("name", "") + " " + b.get("value", "") for b in form.buttons]
        )
        score = 0
        if keywords.search(hay):
            score += 10
        if form.method == "post":
            score += 2
        ranked.append((score, form))
    if not ranked or max(ranked, key=lambda x: x[0])[0] == 0:
        raise RuntimeError("deletion confirmation form not found")
    return max(ranked, key=lambda x: x[0])[1]


def confirmation_values(form: Form) -> dict[str, str]:
    values: dict[str, str] = {}
    keywords = re.compile(r"(delete|remove|cancel|close|unsubscribe|confirm|supprim|yes|oui)", re.I)
    for inp in form.inputs:
        name = inp.get("name")
        if not name:
            continue
        typ = inp.get("type", "").lower()
        if typ in {"checkbox", "radio"} and keywords.search(name + " " + inp.get("value", "")):
            values[name] = inp.get("value", "1") or "1"
        elif typ == "submit" and keywords.search(name + " " + inp.get("value", "")):
            values[name] = inp.get("value", "")
    for button in form.buttons:
        name = button.get("name")
        if name and keywords.search(name + " " + button.get("value", "")):
            values[name] = button.get("value", "")
    return values


def ccm(username: str, yes: bool) -> int:
    delete_url = "https://auth.ccm.net/user/delete_account"
    b = Browser()
    password: str | None = None

    status, url, html = b.get(delete_url)
    print(f"GET {delete_url} -> {status} {url}")

    if urllib.parse.urlparse(url).path.rstrip("/") != "/user/delete_account":
        login = choose_login_form(parse_forms(html))
        user_field, password_field = login_field_names(login)
        password = getpass.getpass("CCM password: ")
        status, url, html = b.submit(
            url,
            login,
            {user_field: username, password_field: password},
        )
        print(f"LOGIN -> {status} {url}")

        # Always revisit the official deletion endpoint after login.
        status, url, html = b.get(delete_url)
        print(f"GET delete page -> {status} {url}")

    if urllib.parse.urlparse(url).path.rstrip("/") != "/user/delete_account":
        print("ERROR: authentication failed or CCM redirected away from delete_account", file=sys.stderr)
        return 2

    form = choose_delete_form(parse_forms(html))
    target = urllib.parse.urljoin(url, form.action or url)
    print(f"Deletion form: {form.method.upper()} {target}")

    if not yes:
        print("Dry-run only. Re-run with --yes to submit the deletion confirmation.")
        return 0

    values = confirmation_values(form)

    # CCM asks for the account password again on the deletion form.
    password_fields = [
        i.get("name")
        for i in form.inputs
        if i.get("type", "").lower() == "password" and i.get("name")
    ]
    if password_fields:
        if password is None:
            password = getpass.getpass("CCM password for deletion: ")
        for field_name in password_fields:
            values[field_name] = password

    status, final_url, body = b.submit(url, form, values)
    debug_path = Path("/tmp/ccm-delete-response.html")
    debug_path.write_text(body, encoding="utf-8")
    print(f"DELETE REQUEST -> {status} {final_url}")
    print(f"Saved final response: {debug_path}")

    lower = body.casefold()
    if any(x in lower for x in ("account deleted", "account has been deleted", "compte supprim", "désinscrit")):
        print("CCM reports that the account was deleted.")
        return 0

    print("Deletion request submitted. Re-run the Maigret/HTTP check to verify disappearance.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="site", required=True)

    p = sub.add_parser("ccm", help="delete a CCM account through its official HTTP flow")
    p.add_argument("--username", required=True)
    p.add_argument("--yes", action="store_true", help="submit the final deletion form")

    args = ap.parse_args()
    if args.site == "ccm":
        return ccm(args.username, args.yes)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
