# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies and Playwright browser
uv sync
uv run playwright install chromium
uv run pre-commit install # Dev environment

# Run the tool
uv run job-matcher                        # LinkedIn only (default)
uv run job-matcher --source indeed        # Indeed only
uv run job-matcher --source linkedin:indeed  # both sources
uv run job-matcher --source all           # all supported sources
uv run job-matcher --dry-run             # score jobs without writing to Google Sheet
uv run job-matcher --threshold 60        # override match threshold
uv run job-matcher --resume my_cv.txt

# Lint and format
uv run ruff check --fix .
uv run ruff format .
```

There are no automated tests. Pre-commit hooks run ruff on commit.

## Architecture

The entry point is `main.py` (`job-matcher` CLI command via `main:main`). All configuration is loaded from `.env` via `config.py`, which is imported by every module.

**Data flow for each job:**
1. `browser/` — OOD browser layer. `JobBoardBrowser` (in `base.py`) is the abstract base class; it implements the shared `login()` and `create_scraping_browser()` methods and defines the `_make_headed_context()` / `_make_scraping_context()` hooks that subclasses override to customise browser launch options. `LinkedInBrowser` and `IndeedBrowser` extend it, each implementing `get_saved_jobs()` and `extract_job_details()`. `browser/__init__.py` exports `get_browser(source)` which instantiates the right class. `config.SUPPORTED_SOURCES` lists valid source names; `config.SESSION_FILES` maps each to its cookie file.
2. `db/database.py` — PostgreSQL via psycopg2. `init_db()` is idempotent (CREATE IF NOT EXISTS + ALTER ADD COLUMN IF NOT EXISTS for migrations). The cache key is `(resume_id, job_id)` in `job_matches`. Resumes are deduplicated by SHA-256 of their text.
3. `matcher/llm_matcher.py` — calls LiteLLM with the resume text and job dict, expects a `{"score": int, "recommendation": str}` JSON response. `config.LLM_MODEL` controls the provider (default: `anthropic/claude-sonnet-4-6`).
4. `sheets/google_sheets.py` — appends a row to the configured Google Sheet tab (`Sheet1` by default). OAuth2 credentials in `credentials.json`; token cached in `token.json`.

**Multi-source loop in `main.py`:** `_parse_sources()` expands `--source` (e.g. `all`, `linkedin:indeed`) into a list. `_run_source()` runs the full scrape+match pipeline for one browser instance and returns results tagged with `source`. Results from all sources are merged into a single summary table.

**Caching logic in `main.py`:** if `get_match()` returns an existing row, the LLM call is skipped entirely. The sheet write is also skipped if `added_to_sheet` is already true. `_maybe_add_to_sheet()` handles the threshold check, dry-run mode, and error isolation between the Sheets and DB writes.

## Adding a new job board

1. Add the source name to `config.SUPPORTED_SOURCES` and its session file to `config.SESSION_FILES`.
2. Create `browser/<name>.py` with a class extending `JobBoardBrowser` — implement `name`, `login_url`, `saved_jobs_url`, `get_saved_jobs()`, and `extract_job_details()`. Override `_login_excluded_patterns`, `_make_headed_context()`, or `_make_scraping_context()` as needed.
3. Export `Browser = <YourClass>` at the bottom of the module.

## Indeed-specific notes

- Saved jobs URL: `https://myjobs.indeed.com/saved`. Job cards are in `ul.atw-Updates-list`; title/link from `a.atw-JobInfo-jobTitle`; company and location from the two `<span>` elements inside `div.atw-JobInfo-companyLocation`.
- Both the login and scraping browsers use `channel="chrome"` (system Chrome) to pass Cloudflare's bot detection. The `--disable-blink-features=AutomationControlled` flag and a `navigator.webdriver = undefined` init script are also applied.
- On first run a headed Chrome window opens for manual login; session cookies are saved to `indeed_session.json`.

## Troubleshooting

### Google Sheets: `invalid_grant: Bad Request`

The cached OAuth2 token has expired or been revoked. Delete it and trigger the OAuth flow directly from your terminal:

```bash
rm data/token.json
uv run python -c "from sheets.google_sheets import get_sheets_service; get_sheets_service()"
```

A browser window will open — complete the Google authorization there. Once `token.json` is written, `job-matcher` will work again.

If the error persists after re-auth, the OAuth2 client credentials themselves may have been revoked — regenerate `credentials.json` from the Google Cloud Console.

## Key files not committed to git

All of these are excluded by `.gitignore` using unpathed patterns, so they are protected whether they sit at the project root or inside `data/`:

| File | Purpose |
|------|---------|
| `*_session.json` | LinkedIn / Indeed browser cookies |
| `credentials.json` | Google OAuth2 client secrets |
| `token.json` | Google OAuth2 cached token |
| `resume.txt` | Resume content |
| `.env` | Environment variables (DB URL, API keys, etc.) |
| `infra/terraform.tfvars` | Terraform variable values (API keys, ARNs) |
