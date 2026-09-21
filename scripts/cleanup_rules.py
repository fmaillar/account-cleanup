#!/usr/bin/env python3
"""Shared rule engine for Maigret cleanup classification."""
from __future__ import annotations

import csv
import fnmatch
from dataclasses import dataclass
from pathlib import Path

ACTIONS = {"review", "mine", "cleanup", "requested", "deleted", "keep", "false-positive"}

@dataclass(frozen=True)
class Rule:
    username: str
    site: str
    action: str
    reason: str = ""


def load_lines(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def load_rules(path: Path | None) -> list[Rule]:
    if not path or not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        rows = csv.DictReader(f, delimiter="\t")
        required = {"username", "site", "action"}
        if not rows.fieldnames or not required.issubset(rows.fieldnames):
            raise ValueError(f"{path}: expected TSV columns username, site, action[, reason]")
        rules = []
        for n, row in enumerate(rows, start=2):
            username = (row.get("username") or "*").strip()
            site = (row.get("site") or "*").strip()
            action = (row.get("action") or "").strip().casefold()
            reason = (row.get("reason") or "").strip()
            if not action:
                continue
            if action not in ACTIONS:
                raise ValueError(f"{path}:{n}: invalid action {action!r}")
            rules.append(Rule(username, site, action, reason))
        return rules


def _match(pattern: str, value: str) -> bool:
    return fnmatch.fnmatchcase(value.casefold(), pattern.casefold())


def matching_rule(rules: list[Rule], username: str, site: str) -> Rule | None:
    candidates: list[tuple[int, int, Rule]] = []
    for idx, rule in enumerate(rules):
        if _match(rule.username, username) and _match(rule.site, site):
            specificity = int(rule.username != "*") + int(rule.site != "*")
            candidates.append((specificity, idx, rule))
    return max(candidates, default=(0, -1, None), key=lambda x: (x[0], x[1]))[2]


def classify_row(
    row: dict[str, str],
    *,
    rules: list[Rule],
    keep_sites: list[str],
    ignore_sites: list[str],
) -> tuple[str, str]:
    query = row.get("query_username", "").strip()
    detected = row.get("detected_username", "").strip()
    site = row.get("site", "").strip()
    metadata = row.get("metadata", "")

    rule = matching_rule(rules, query, site)
    if rule:
        return rule.action, rule.reason or "explicit local rule"

    site_cf = site.casefold()
    if any(token.casefold() in site_cf for token in ignore_sites):
        return "false-positive", "site configured as non-actionable/ignored"

    if detected and query.casefold() != detected.casefold():
        return "false-positive", "detected username differs from scanned username"

    if any(token.casefold() in site_cf for token in keep_sites):
        return "keep", "site configured to keep"

    md = metadata.casefold().replace(" ", "")
    if "status=closed" in md or "account_status=closed" in md:
        return "deleted", "source metadata reports account status=closed"

    return "review", "manual ownership check required"
