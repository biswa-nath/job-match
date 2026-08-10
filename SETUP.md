# Setup Guide

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- PostgreSQL database
- A Google account with access to the target Google Sheet
- An API key for your LLM provider
- System Chrome installed (required for Indeed and Naukri — Playwright's Chromium is blocked by their bot detection)

## 1. Install dependencies

```bash
uv sync
uv run playwright install chromium
```

## 2. Configure environment

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

### Required variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql://user:pass@host/db?sslmode=require`) |
| `SHEET_ID` | Google Sheet identifier (from the sheet URL) |
| `LLM_MODEL` | LiteLLM model string (e.g. `anthropic/claude-sonnet-4-6`, `gpt-4o`, `gemini/gemini-2.0-flash`) |

### API keys (set the one(s) matching your `LLM_MODEL`)

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Required for Claude models |
| `GEMINI_API_KEY` | Required for Gemini models |
| `OPENAI_API_KEY` | Required for OpenAI models |

### Optional variables

| Variable | Default | Description |
|---|---|---|
| `DESKTOP_NOTIFY` | `0` | Set to `1` to enable desktop notifications via `notify-send` (requires `libnotify-bin`) |
| `LAMBDA_MODE` | `0` | Set to `1` to skip headed browser login and send session-expiry alerts via SNS |
| `SNS_TOPIC_ARN` | — | SNS topic ARN for Lambda alert notifications |
| `AWS_REGION` | `us-east-1` | AWS region for SNS |
| `SESSION_DIR` | `data` | Directory for session cookie files (set to a persistent path like `/mnt/efs` for Lambda) |
| `SECRETS_DIR` | `secrets` | Directory for Google OAuth2 credentials |
| `RESUME_PATH` | — | Path to resume PDF for Lambda deployments (local runs use `--resume` flag instead) |

## 3. Set up Google Sheets OAuth2

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services** → **Library**
2. Enable the **Google Sheets API**
3. Go to **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
4. Application type: **Desktop app**
5. Download the JSON file and save it as `secrets/credentials.json`
6. On first run, a browser window will open for Google account authorisation — approve it
7. The token is cached in `data/token.json` for subsequent runs

### Refreshing an expired token

```bash
rm data/token.json
uv run python -c "from sheets.google_sheets import get_sheets_service; get_sheets_service()"
```

## 4. Run

Pass your resume as a PDF via `--resume`:

```bash
# Recommended: dry-run first to verify everything works
uv run job-matcher --resume my_cv.pdf --dry-run

# Full run (LinkedIn only, default)
uv run job-matcher --resume my_cv.pdf

# Scrape multiple sources
uv run job-matcher --resume my_cv.pdf --source linkedin:indeed
uv run job-matcher --resume my_cv.pdf --source all

# Custom threshold (default is 60)
uv run job-matcher --resume my_cv.pdf --threshold 50
```

On first run for each job board, a browser window will open for manual login. Credentials are never stored — only the session cookies are saved (one file per source):

| Source | Session file |
|---|---|
| LinkedIn | `data/linkedin_session.json` |
| Indeed | `data/indeed_session.json` |
| Naukri | `data/naukri_session.json` |

## Files not committed to git

| File | Purpose |
|---|---|
| `.env` | API keys and configuration |
| `data/*_session.json` | Per-source browser session cookies |
| `data/token.json` | Google OAuth2 token cache |
| `secrets/credentials.json` | Google OAuth2 client credentials |
| `*.pdf` | Resume PDF |
| `.venv/` | Python virtual environment |
