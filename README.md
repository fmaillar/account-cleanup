# account-cleanup

Small local toolkit to inventory old accounts/usernames and turn OSINT results into a deletion checklist.

The repository intentionally contains **no personal email address, username list, or scan result**. Keep those local: the repository is public.

## Tools

The workflow supports:

- **Holehe** — checks whether an email appears to be registered on supported services.
- **Blackbird** — complementary account/email enumeration.
- **Maigret** — username enumeration across many sites.
- **Sherlock** — optional second opinion for username enumeration.

None of these tools proves ownership. A "found"/"claimed" result must be verified before requesting deletion.

## Local setup

Create private local configuration files:

```bash
cp config/emails.txt.example config/emails.txt
cp config/usernames.txt.example config/usernames.txt
cp config/keep-sites.txt.example config/keep-sites.txt
```

Edit them locally. They are ignored by Git.

Suggested isolated installations:

```bash
pipx install holehe
pipx install maigret
pipx install sherlock-project
```

Blackbird is commonly run from its own clone/virtualenv; set `BLACKBIRD` to the executable/script path if it is not on `PATH`.

## Scan

Run tools independently:

```bash
scripts/run_holehe.sh
scripts/run_blackbird.sh
scripts/run_maigret.sh
scripts/run_sherlock.sh
```

Results are written below `results/`.

For Maigret:

```bash
scripts/run_maigret.sh
scripts/extract_all.sh
python3 scripts/build_cleanup_report.py results/maigret
```

The Maigret extractor and HTML report automatically use `config/usernames.txt` as an allowlist when that file exists. This is important because profile metadata can contain other usernames; those secondary identifiers are shown separately as **Detected username**, but they no longer create unrelated cleanup entries.

The last command creates:

```text
results/cleanup-report.html
```

Open it locally in a browser. It contains profile links, HTTP verification status, extracted metadata, and a per-row cleanup state stored in browser localStorage.

## Recommended workflow

1. Enumerate with Holehe/Blackbird using your email addresses.
2. Enumerate remembered usernames with Maigret.
3. Use Sherlock only as a cross-check when useful.
4. Review Maigret's claimed profiles with `extract_maigret.py`.
5. Generate the cleanup HTML report.
6. Mark obvious false positives and sites/accounts you intentionally keep.
7. Recover access or use the site's deletion/privacy procedure.
8. Re-scan after the service's deletion grace period.

## Safety / limitations

- HTTP 200 does **not** prove that a profile belongs to you.
- Some sites return HTTP 200 for nonexistent users.
- Account deletion endpoints are site-specific and may require authentication, CSRF tokens, email confirmation, CAPTCHA, or a waiting period.
- This repository therefore does not issue generic destructive POST requests.
- Do not commit raw reports: they can contain personal data.
