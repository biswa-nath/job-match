# Setup Guide

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A database (preferrably PostgreSQL)
- A Google account with access to the target Google Sheet
- An API key for your LLM provider

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

`.env` variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql://...?sslmode=require`) |
| `SHEET_ID` | Google sheet identifier |
| `LLM_MODEL` | LiteLLM model string |
| `ANTHROPIC_API_KEY` | Required if using a Claude model |
| `GEMINI_API_KEY` | Required if using a Gemini model |
| `OPENAI_API_KEY` | Required if using an OpenAI model |

## 3. Add your resume

Edit `resume.txt` (or whichever file `DEFAULT_RESUME` points to in `config.py`) and paste your full resume in plain text. 
**Caveat:** Remove name, contact details and any other sensitive information as all of it will go to LLM.

## 4. Set up Google Sheets OAuth2

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services** → **Library**
2. Enable the **Google Sheets API**
3. Go to **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
4. Application type: **Desktop app**
5. Download the JSON file and save as `credentials.json` in the project root
6. On first run, a browser window will open for Google account authorisation - approve it
7. The token is cached in `token.json` for subsequent runs

## 5. Run

```bash
# Recommended: dry-run first to verify everything works
uv run job-matcher --dry-run

# Full run
uv run job-matcher

# Custom threshold
uv run job-matcher --threshold 60
```

On first run, a browser will open for LinkedIn login. Log in manually - credentials are never stored, only the session cookies are saved to `session.json`.

## Files not committed to git

| File | Purpose |
|---|---|
| `.env` | API keys and configuration |
| `session.json` | LinkedIn session cookies |
| `credentials.json` | Google OAuth2 client credentials |
| `token.json` | Google OAuth2 token cache |
| `resume.txt` | Your resume |
| `.venv/` | Python virtual environment |
