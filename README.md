# account-cleanup

Local toolkit to inventory old online accounts/usernames and turn OSINT results into a deterministic cleanup queue.

The repository intentionally contains **no personal email address, username list, account rules, or scan result**. Keep those local: this repository is public.

## Supported tools

- **Holehe** — email registration checks.
- **Blackbird** — complementary email/account enumeration.
- **Maigret** — username enumeration across many sites.
- **Sherlock** — optional username cross-check.

A positive result never proves ownership by itself.

## Local setup

Create the private configuration files:

```bash
cp config/emails.txt.example config/emails.txt
cp config/usernames.txt.example config/usernames.txt
cp config/keep-sites.txt.example config/keep-sites.txt
cp config/ignore-sites.txt.example config/ignore-sites.txt
cp config/account-rules.tsv.example config/account-rules.tsv
```

All five real files are ignored by Git.

Suggested installations:

```bash
pipx install holehe
pipx install maigret
pipx install sherlock-project
```

Blackbird can be run from its own clone/venv; set `BLACKBIRD=/path/to/blackbird.py` when needed.

## One-command campaign

```bash
scripts/run_campaign.sh
```

This runs the tools available on the machine, then extracts and classifies results. Sherlock is optional:

```bash
RUN_SHERLOCK=1 scripts/run_campaign.sh
```

To process already existing results without re-scanning:

```bash
scripts/process_results.sh
```

## Deterministic classification

The central private file is:

```text
config/account-rules.tsv
```

Format:

```text
username<TAB>site<TAB>action<TAB>reason
```

Actions:

- `review` — ownership still needs checking.
- `mine` — confirmed mine, decision still pending.
- `cleanup` — confirmed account/profile to remove.
- `requested` — deletion request already sent.
- `deleted` — account is closed/deleted.
- `keep` — intentional current account.
- `false-positive` — wrong person, mirror, search result, or detector error.

Rules may use shell-style `*` wildcards. The most specific matching rule wins, so exact `username + site` rules override broad site rules.

Manage rules without editing TSV manually:

```bash
python3 scripts/account_rule.py set old_username "Example Forum" cleanup "confirmed old account"
python3 scripts/account_rule.py set current_username GitHub keep "current account"
python3 scripts/account_rule.py list
python3 scripts/account_rule.py delete old_username "Example Forum"
```

Classification precedence is:

1. explicit `account-rules.tsv` rule;
2. ignored/non-actionable site;
3. detected username mismatch;
4. broad keep-site fallback;
5. source metadata saying `status=closed`;
6. manual review.

This avoids the previous error where a global `GitHub`/ `GitLab` keep rule could incorrectly preserve another person's account with the same username.

## Outputs

```text
results/extracts/holehe-positive.tsv
results/extracts/blackbird-positive.tsv
results/extracts/maigret-claimed.tsv
results/extracts/maigret-classified.tsv
results/extracts/maigret-cleanup.tsv
results/extracts/maigret-mine.tsv
results/extracts/maigret-review.tsv
results/extracts/maigret-requested.tsv
results/extracts/maigret-deleted.tsv
results/extracts/maigret-keep.tsv
results/extracts/maigret-false-positive.tsv
results/cleanup-report.html
```

The HTML dashboard shows actionable entries by default and can reveal the full classified set.

## Recommended workflow

1. Put only remembered/credible usernames in `config/usernames.txt`.
2. Run the campaign.
3. Inspect `maigret-review.tsv`.
4. Confirm ownership using profile metadata or HTTP/browser access.
5. Record the decision with `account_rule.py`.
6. Re-run `scripts/process_results.sh`.
7. Work only from `maigret-cleanup.tsv` and `maigret-requested.tsv`.
8. Re-scan after deletion grace periods.

## Tests

The rule engine uses only the Python standard library:

```bash
python3 -m unittest discover -s tests -v
```

## Safety / limitations

- HTTP 200 does not prove that an account exists or belongs to you.
- Some sites return HTTP 200 for nonexistent users.
- Account deletion endpoints are site-specific and may require login, CSRF tokens, email confirmation, CAPTCHA, or a grace period.
- The toolkit does not send generic destructive POST requests.
- Raw reports can contain personal data; do not commit `results/`.

## HTTP deletion adapters

The repository now includes a real HTTP deletion adapter for CCM:

```bash
python3 scripts/http_account_cleanup.py ccm --username old_username
```

The first run is a dry-run: it follows the official delete-account URL, discovers the login form, authenticates with an interactive password prompt, revisits the deletion page, and prints the final form it would submit.

To actually submit the deletion confirmation:

```bash
python3 scripts/http_account_cleanup.py ccm --username old_username --yes
```

The password is read with `getpass`, kept only in memory, and never written to disk. The adapter preserves cookies and hidden/CSRF fields from the site's forms.

Additional sites should be implemented as explicit adapters instead of generic destructive requests, because deletion flows differ in authentication, CSRF handling, confirmation fields, CAPTCHA, and grace periods.
