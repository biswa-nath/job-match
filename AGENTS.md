# AGENTS.md

> Structured agent context for this repository. Designed to work with any agentic
> coding system (Claude Code, Cursor, Codex, Aider, etc.). Keep this file in sync
> with CLAUDE.md when making architectural changes.

---

## 1. Project Identity

| Field        | Value |
|--------------|-------|
| Name         | job-matcher |
| Language     | Python 3.11+ |
| Package mgr  | uv |
| Entry point  | `src/main.py` → `main:main` (CLI) |
| Config layer | `src/config.py` reads `.env` via python-dotenv |
| Tests        | None — no test suite exists |
| Linter       | ruff (pre-commit hook, also runnable manually) |

---

## 2. Quick Commands

```bash
# Environment setup
uv sync
uv run playwright install chromium
uv run pre-commit install          # dev only

# Run the tool
uv run job-matcher --resume <path>.pdf                   # LinkedIn (default)
uv run job-matcher --resume <path>.pdf --source indeed
uv run job-matcher --resume <path>.pdf --source linkedin:indeed
uv run job-matcher --resume <path>.pdf --source all
uv run job-matcher --resume <path>.pdf --dry-run         # score only, no sheet write
uv run job-matcher --resume <path>.pdf --threshold 75    # override score cutoff

# Lint / format
uv run ruff check --fix .
uv run ruff format .
```

---

## 3. Repository Layout

```
src/
  main.py              # CLI entry point (click command)
  config.py            # All env-var loading; imported by every module
  resume.py            # PDF extraction (pdfplumber) + PII redaction (Presidio/spaCy)
  notifications.py     # Desktop/SNS notification helper
  lambda_handler.py    # AWS Lambda entry point (wraps main pipeline)

  browser/
    base.py            # Abstract base class JobBoardBrowser
    __init__.py        # get_browser(source) factory
    linkedin.py        # LinkedInBrowser
    indeed.py          # IndeedBrowser
    naukri.py          # NaukriBrowser
    session.py         # Cookie save/load helpers

  db/
    database.py        # PostgreSQL helpers (psycopg2)
    __init__.py

  matcher/
    llm_matcher.py     # LiteLLM call + JSON parsing
    __init__.py

  sheets/
    google_sheets.py   # Google Sheets append + deduplication
    __init__.py

infra/                 # Terraform (AWS Lambda + EFS + EventBridge + SNS)
docker/                # Dockerfile for Lambda image
clean_jobs.py          # Utility: delete all DB rows for a given source
diagnose_redaction.py  # Utility: preview PII redaction on a resume
```

---

## 4. Data Flow (per job)

```
PDF file
  └─► resume.py: extract_pdf() → raw text
        └─► resume.py: redact()  → PII-stripped text
              └─► db: get_or_create_resume(text)  [key = SHA-256 of redacted text]
                    │
                    ▼
              browser/<source>.py
                get_saved_jobs(page)   → list of job stubs {url, position, company, location, office_type}
                    │
                    ▼
              db: get_or_create_job(url)
                    │
                    ├─► [cache hit] db: get_match(resume_id, job_id) → skip LLM
                    │
                    └─► [cache miss]
                          browser.extract_job_details(page, stub) → adds "description"
                            └─► matcher/llm_matcher.py: match_job(resume_text, job)
                                  └─► LiteLLM → {"score": int, "recommendation": str}
                                        └─► db: save_match(...)
                                              └─► [score >= threshold] sheets: append_job_row(...)
                                                    └─► db: mark_added_to_sheet(match_id)
```

---

## 5. Key Invariants — Read Before Editing

- **`config.py` is the single source of truth** for all configuration. Never hard-code
  paths, URLs, or model names in other modules; always read from `config.*`.

- **Resume text is always redacted before storage or LLM calls.** `resume.py:redact()`
  strips name, email, phone, and SSN via Presidio + spaCy. The raw text must never be
  persisted or sent to an external service.

- **Caching is keyed on `(resume_id, job_id)`** in `job_matches`. `resume_id` is
  derived from the SHA-256 of the *redacted* text. Changing the redaction logic
  creates new resume rows and invalidates the cache for all jobs.

- **`init_db()` is idempotent.** It uses `CREATE TABLE IF NOT EXISTS` and
  `ALTER TABLE … ADD COLUMN IF NOT EXISTS`. Schema migrations belong here, not in
  separate migration files.

- **Per-source isolation in the main loop.** A crash in one board's `_run_source()`
  call must not stop other boards. The outer `except Exception` in `main.py` achieves
  this. Preserve it when adding new boards.

- **Sheet writes and DB writes are separated.** `_maybe_add_to_sheet()` calls
  `append_job_row` first, then `mark_added_to_sheet`. A Sheets failure raises
  (stopping further processing). A DB failure after a successful sheet write logs and
  notifies but does not raise (the row is already written; re-raising would be a lie).

- **`added_to_sheet` prevents duplicate sheet rows.** If it is already `True`, skip
  the sheet write even when re-processing a cached match.

---

## 6. Environment Variables

All read by `config.py`. Provide in `.env` at the project root.

| Variable        | Required | Default                         | Purpose |
|-----------------|----------|---------------------------------|---------|
| `DATABASE_URL`  | Yes      | —                               | psycopg2 DSN |
| `SHEET_ID`      | Yes      | —                               | Google Sheets spreadsheet ID |
| `LLM_MODEL`     | No       | `anthropic/claude-sonnet-4-6`   | LiteLLM model string |
| `LLM_API_KEY`   | No       | —                               | Provider API key (or set `ANTHROPIC_API_KEY` etc.) |
| `LAMBDA_MODE`   | No       | `0`                             | `1` = headless-only + SNS alerts |
| `SNS_TOPIC_ARN` | Lambda   | —                               | SNS ARN for expiry/error alerts |
| `AWS_REGION`    | No       | `us-east-1`                     | AWS region for SNS |
| `SESSION_DIR`   | No       | `data`                          | Directory for cookie / token files |
| `SECRETS_DIR`   | No       | `secrets`                       | Directory for `credentials.json` |
| `RESUME_PATH`   | Lambda   | —                               | Absolute path to resume PDF (EFS mount) |
| `DESKTOP_NOTIFY`| No       | `0`                             | `1` = `notify-send` desktop alerts |

---

## 7. Database Schema

```sql
-- Deduplicated by SHA-256 of redacted text
CREATE TABLE resume (
    id        SERIAL PRIMARY KEY,
    signature TEXT NOT NULL,          -- SHA-256 hex
    added_on  TIMESTAMPTZ DEFAULT NOW(),
    text      TEXT NOT NULL
);

-- One row per unique job URL
CREATE TABLE jobs (
    id       SERIAL PRIMARY KEY,
    job_link TEXT NOT NULL,
    added_on TIMESTAMPTZ DEFAULT NOW()
);

-- One row per (resume, job) pair
CREATE TABLE job_matches (
    id               SERIAL PRIMARY KEY,
    resume_id        INTEGER NOT NULL REFERENCES resume(id),
    job_id           INTEGER NOT NULL REFERENCES jobs(id),
    score            INTEGER NOT NULL,           -- 0–100
    recommendation   TEXT NOT NULL,
    additional_notes TEXT NOT NULL DEFAULT '',
    added_to_sheet   BOOLEAN NOT NULL DEFAULT FALSE
);
```

---

## 8. Browser Abstraction

`JobBoardBrowser` (in `src/browser/base.py`) is the abstract base class.

**Required overrides for a new board:**

| Member                | Kind     | Description |
|-----------------------|----------|-------------|
| `name`                | property | Source identifier (must match key in `config.SESSION_FILES`) |
| `login_url`           | property | URL opened for manual login |
| `saved_jobs_url`      | property | URL of the saved-jobs listing |
| `get_saved_jobs(page)`| method   | Returns `list[dict]` with keys: `url`, `position`, `company`, `location`, `office_type` |
| `extract_job_details(page, job)` | method | Returns `job` dict enriched with a `description` key |

**Optional overrides:**

| Member                    | When to override |
|---------------------------|-----------------|
| `_login_excluded_patterns`| Login URL alone is insufficient to detect incomplete login |
| `_make_headed_context()`  | Need non-default launch args for the login browser (e.g. `channel="chrome"` for bot detection) |
| `_make_scraping_context()`| Need non-default launch args for the scraping browser |

The module must export `Browser = <YourClass>` for `browser/__init__.py:get_browser()` to find it.

---

## 9. Adding a New Job Board (Checklist)

1. Add the source name string to `config.SUPPORTED_SOURCES`.
2. Add `"<name>": os.path.join(_SESSION_DIR, "<name>_session.json")` to `config.SESSION_FILES`.
3. Create `src/browser/<name>.py` implementing the contract above.
4. Export `Browser = <YourClass>` at the bottom of the new module.
5. Document board-specific CSS selectors and bot-detection workarounds in this file
   under a new `## <Name>-specific notes` section (see §11 below).

---

## 10. LLM Matcher Contract

`src/matcher/llm_matcher.py:match_job(resume_text, job)` sends one chat completion
request via LiteLLM and returns:

```python
{"score": int,           # 0–100
 "recommendation": str}  # one or two sentences
```

The model is set by `config.LLM_MODEL` (LiteLLM model string). To switch provider,
change `LLM_MODEL` in `.env` — no code change needed. The prompt asks for raw JSON;
a regex fallback strips markdown fences if the model wraps the output.

---

## 11. Board-Specific Notes

### LinkedIn

- Session file: `data/linkedin_session.json`
- Standard Playwright Chromium (no system Chrome needed).
- Saved jobs page: `https://www.linkedin.com/my-items/saved-jobs/`

### Indeed

- Session file: `data/indeed_session.json`
- Requires `channel="chrome"` (system Chrome) for Cloudflare bypass.
- `--disable-blink-features=AutomationControlled` flag + `navigator.webdriver = undefined`
  init script applied in `_make_scraping_context()`.
- Saved jobs URL: `https://myjobs.indeed.com/saved`
- Job cards: `ul.atw-Updates-list`; title/link: `a.atw-JobInfo-jobTitle`;
  company/location: two `<span>` inside `div.atw-JobInfo-companyLocation`.

### Naukri

- Session file: `data/naukri_session.json`
- Requires `channel="chrome"` (system Chrome) for Akamai bypass.
- Saved jobs URL: `https://www.naukri.com/mnjuser/savedjobs`
- Job cards: `article.one-theme-job-tuple`; link: `a.tupleLink[href]`;
  job ID: `div.tuple[data-jobid]`.
- Title: `.title` element, prefer `title` attribute for untruncated text.
- Company: `.org`; location: `.location-container .loc` (`title` attribute for multi-city).
- Job description on detail page: `[class*="dang-inner-html"]` (CSS-modules class).
- Page lazy-loads on scroll; scraper loops until card count stabilises.
- Login page: `https://www.naukri.com/nlogin/login`

---

## 12. Files Not Committed to Git

The `.gitignore` uses unpathed patterns, so these are excluded whether at the project
root or inside `data/` or `secrets/`:

| Pattern              | Purpose |
|----------------------|---------|
| `*_session.json`     | Browser session cookies per job board |
| `credentials.json`   | Google OAuth2 client secrets |
| `token.json`         | Google OAuth2 cached token |
| `*.pdf`              | Resume files |
| `.env`               | Environment variables |
| `infra/terraform.tfvars` | Terraform secrets (API keys, ARNs) |

**Never commit these.** The gitignore is the safety net; do not rely on it as the only
protection — verify before staging any `git add .`.

---

## 13. Troubleshooting

### Google Sheets: `invalid_grant: Bad Request`

Token is expired or revoked. Re-authenticate:

```bash
rm data/token.json
uv run python -c "from sheets.google_sheets import get_sheets_service; get_sheets_service()"
```

Complete the browser OAuth flow. If the error persists, regenerate `credentials.json`
from Google Cloud Console.

### Lambda session expiry

When `LAMBDA_MODE=1`, `check_session_headless()` validates the cookie file without
opening a browser. If it returns `False`, an SNS alert is sent. Fix: run the tool
locally for the affected source, then upload the refreshed `*_session.json` to EFS.

### Bot detection / 403

- Indeed/Naukri: ensure `channel="chrome"` is set in `_make_headed_context()` and
  `_make_scraping_context()`. Playwright's bundled Chromium gets blocked.
- If system Chrome is not installed at the default path, set `executable_path` in
  the launch call.

---

## 14. Agent Constraints

When an agent works in this repository it must respect the following:

- **Do not commit `.env`, `*_session.json`, `credentials.json`, `token.json`, or `*.pdf`.**
- **Do not log or print raw resume text** (before `redact()` is applied) in any new code.
- **Preserve the per-source isolation pattern** in `main.py`: a failure in one source
  must not prevent other sources from running.
- **No new test framework** — there are no tests by design; do not add pytest or similar
  unless explicitly requested.
- **No new abstraction layers** unless the task clearly requires it. Three similar lines
  is better than a premature helper.
- **Lint before finishing.** Run `uv run ruff check --fix .` and `uv run ruff format .`
  after any code change.
- **`config.py` is the only place** where environment variables are read. Other modules
  import `config`; they do not call `os.getenv` directly.
