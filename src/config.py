import os

from dotenv import load_dotenv

load_dotenv()

SHEET_ID = os.getenv("SHEET_ID", "")
SHEET_TAB = "Sheet1"
DEFAULT_THRESHOLD = 60
# LiteLLM model string — change via LLM_MODEL env var to switch provider/model
# e.g. "claude/claude-sonnet-4-6", "gpt-4o", "ollama/llama3"
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-6")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Lambda / headless deployment
# Set LAMBDA_MODE=1 to skip headed browser login and use SNS for expiry alerts.
LAMBDA_MODE = os.getenv("LAMBDA_MODE", "").lower() in ("1", "true")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Set SESSION_DIR to a persistent path (e.g. /mnt/efs) for Lambda deployments.
# Defaults to "data" so local runs resolve files from the data/ directory.
_SESSION_DIR = os.getenv("SESSION_DIR", "data")
DEFAULT_RESUME = os.path.join(_SESSION_DIR, "resume.txt")

SUPPORTED_SOURCES = ["linkedin", "indeed"]
SESSION_FILES = {
    "linkedin": os.path.join(_SESSION_DIR, "linkedin_session.json"),
    "indeed": os.path.join(_SESSION_DIR, "indeed_session.json"),
}
GOOGLE_CREDS_FILE = os.path.join(_SESSION_DIR, "credentials.json")
GOOGLE_TOKEN_FILE = os.path.join(_SESSION_DIR, "token.json")
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
