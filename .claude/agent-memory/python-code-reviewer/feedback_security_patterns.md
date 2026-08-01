---
name: security-patterns
description: Enforced security conventions in the job-match codebase — SQL parameterization, gitignore, PII redaction, credential handling
metadata:
  type: feedback
---

Key security patterns enforced in this codebase:

1. **SQL queries**: always use parameterized psycopg2 statements — never f-strings in SQL. Any f-string SQL is Critical.

2. **Session/credential files are gitignored**: `*_session.json`, `credentials.json`, `token.json`, resume PDFs must NEVER be committed. The gitignore patterns must cover ALL locations where these files can exist (not just one directory). PR #3 introduced a regression here by switching from unpathed patterns (covering all directories) to `data/`-pathed patterns — leaving root-level files exposed.

3. **No secrets in logs**: credentials, API keys, and tokens must not appear in console output or tracebacks. The `DATABASE_URL` connection string is passed to psycopg2 directly — it must not be logged.

4. **Lazy boto3 import in notifications.py**: boto3 is NOT in pyproject.toml dependencies — it's lazy-imported inside `notify()` so local runs without boto3 installed aren't broken. Don't add boto3 as a hard dependency.

5. **Lambda env vars for secrets**: `ANTHROPIC_API_KEY` and `database_url` are passed as Lambda environment variables marked `sensitive = true` in Terraform. This is the accepted pattern for this project (not Secrets Manager).

6. **PII redaction before any DB write or LLM call**: `raw_text` (the direct PDF extract) is ephemeral — it must never reach `get_or_create_resume()`, `match_job()`, or any log output. `resume_text = redact(raw_text)` in `main()` is the trust boundary. Any code that bypasses this is Critical.

7. **Lambda event paths are untrusted**: `event.get("resume", config.RESUME_PATH)` in `lambda_handler.py` is only `.pdf` extension-checked, not directory-scoped. Any new code that routes a Lambda event field to a file path must validate the resolved path sits within `config._SESSION_DIR` (or equivalent) to prevent path traversal.

**Why:** Personal/sensitive data (resume PII, OAuth tokens, session cookies) flowing into storage or logs would be a serious privacy incident. SQL injection would compromise the PostgreSQL match cache. Path traversal via untrusted Lambda events could read arbitrary EFS files.

**How to apply:** Verify gitignore patterns cover both root-level and `data/`-pathed files when reviewing path changes. Flag any call that stores or forwards `raw_text` before `redact()`. Flag Lambda event fields used as file paths without directory validation.
