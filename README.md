# Job Match Assistant

A CLI tool to automatically scan your LinkedIn saved jobs. It scores each one against your resume using an LLM, and adds high-match jobs to a Google Sheet - to help you save time.

## How it works

1. Opens a browser for LinkedIn login (credentials not saved)
2. Scrapes all saved jobs from LinkedIn (https://www.linkedin.com/jobs-tracker/?stage=saved)
3. For each job, extracts the job description and scores it against your resume via LLM
4. Jobs scoring above the threshold are appended to a Google Sheet
5. Match results are cached in database - so subsequent runs skip the LLM call for already-matched jobs

## Features

- **Session persistence** — LinkedIn cookies are saved locally in session.json; login only required when session expires
- **Provider-agnostic LLM** — uses LiteLLM, switch between Claude, Gemini, OpenAI, or any other via single env var
- **Caching and cost-saving** — resume, job and job matches stored in db; no redundant LLM calls for multiple runs
- **Threshold flexibility** — lower the threshold on a later run to catch previously-skipped jobs
- **Dry-run mode** — score jobs without writing to Google Sheet

## Usage

```bash
uv run job-matcher                   # full run with defaults
uv run job-matcher --dry-run         # score jobs, skip sheet writes
uv run job-matcher --threshold 60    # lower match threshold
uv run job-matcher --resume my_cv.txt
```

## Tech stack

- [Playwright](https://playwright.dev/python/) — browser automation
- [LiteLLM](https://docs.litellm.ai/) — LLM provider abstraction
- [Google Sheets API](https://developers.google.com/sheets/api) — OAuth2
- [Rich](https://rich.readthedocs.io/) — terminal output
- [uv](https://docs.astral.sh/uv/) — package management
