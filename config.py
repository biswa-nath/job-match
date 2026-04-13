import os
from dotenv import load_dotenv

load_dotenv()

SHEET_ID = os.getenv("SHEET_ID", "")
SHEET_TAB = "Sheet1"
DEFAULT_RESUME = "resume.txt"
DEFAULT_THRESHOLD = 70
# LiteLLM model string — change via LLM_MODEL env var to switch provider/model
# e.g. "claude/claude-sonnet-4-6", "gpt-4o", "ollama/llama3"
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-6")
DATABASE_URL = os.getenv("DATABASE_URL", "")
SESSION_FILE = "session.json"
GOOGLE_CREDS_FILE = "credentials.json"
GOOGLE_TOKEN_FILE = "token.json"
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
