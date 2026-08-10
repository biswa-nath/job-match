# Job Match Assistant

A CLI tool to automatically scan your saved jobs across LinkedIn, Indeed, and Naukri. It scores each one against your resume using an LLM, and adds high-match jobs to a Google Sheet — to help you save time.

## How it works

1. Reads and extracts text from your resume PDF, then redacts PII (name, email, phone, SSN) before anything leaves your machine
2. Opens a browser for job board login (credentials are never saved — only session cookies)
3. Scrapes all saved jobs from the selected source(s)
4. For each job, extracts the full job description and scores it against your redacted resume via LLM
5. Jobs scoring above the threshold are appended to a Google Sheet
6. Match results are cached in a PostgreSQL database — subsequent runs skip the LLM call for already-matched jobs

## Features

- **Multi-source** — scrape LinkedIn, Indeed, and Naukri in a single run
- **PDF resume + PII redaction** — extracts text from your PDF and strips name, email, phone, and SSN using Presidio before sending to the LLM
- **Session persistence** — each job board's cookies are saved to their own session file; login only required when a session expires
- **Provider-agnostic LLM** — uses LiteLLM; switch between Claude, Gemini, OpenAI, or any other provider via a single env var
- **Caching and cost-saving** — resumes, jobs, and match scores stored in DB; no redundant LLM calls across runs
- **Threshold flexibility** — lower the threshold on a later run to catch previously-skipped jobs
- **Dry-run mode** — score jobs without writing to Google Sheet
- **Sheet deduplication** — duplicate rows removed automatically after each run
- **Desktop notifications** — optional `notify-send` alerts for local / cron deployments
- **Headless / Lambda mode** — runs without a browser UI; sends SNS alerts when sessions expire

## Usage

```bash
uv run job-matcher --resume my_cv.pdf                        # LinkedIn only (default)
uv run job-matcher --resume my_cv.pdf --source indeed        # Indeed only
uv run job-matcher --resume my_cv.pdf --source naukri        # Naukri only
uv run job-matcher --resume my_cv.pdf --source linkedin:indeed  # multiple sources
uv run job-matcher --resume my_cv.pdf --source all           # all supported sources

uv run job-matcher --resume my_cv.pdf --dry-run              # score jobs, skip sheet writes
uv run job-matcher --resume my_cv.pdf --threshold 50         # override match threshold (default: 60)
uv run job-matcher --resume my_cv.pdf --headless-only        # skip browser login (Lambda / cron)
```

## Tech stack

- [Playwright](https://playwright.dev/python/) — browser automation (system Chrome for bot-detection bypass on Indeed / Naukri)
- [pdfplumber](https://github.com/jsvine/pdfplumber) — PDF text extraction
- [Presidio](https://microsoft.github.io/presidio/) + [spaCy](https://spacy.io/) — PII detection and redaction
- [LiteLLM](https://docs.litellm.ai/) — LLM provider abstraction
- [Google Sheets API](https://developers.google.com/sheets/api) — OAuth2
- [PostgreSQL](https://www.postgresql.org/) — job and match caching via psycopg2
- [Rich](https://rich.readthedocs.io/) — terminal output
- [uv](https://docs.astral.sh/uv/) — package management

## Deployment

The tool supports local runs and AWS Lambda deployments. Set `LAMBDA_MODE=1` to skip headed browser login and receive session-expiry alerts via SNS. Terraform infrastructure for Lambda + EFS + EventBridge is in `infra/`.

See [SETUP.md](SETUP.md) for full configuration instructions.
