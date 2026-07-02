---
name: security-patterns
description: Enforced security conventions in the job-match codebase — SQL parameterization, gitignore coverage, credential handling
metadata:
  type: feedback
---

Key security patterns enforced in this codebase:

1. **SQL queries**: always use parameterized psycopg2 statements — never f-strings in SQL. Any f-string SQL is Critical.

2. **Session/credential files are gitignored**: `*_session.json`, `credentials.json`, `token.json`, `resume.txt` must NEVER be committed. The gitignore patterns must cover ALL locations where these files can exist (not just one directory). PR #3 introduced a regression here by switching from unpathed patterns (covering all directories) to `data/`-pathed patterns — leaving root-level files exposed.

3. **No secrets in logs**: credentials, API keys, and tokens must not appear in console output or tracebacks. The `DATABASE_URL` connection string is passed to psycopg2 directly — it must not be logged.

4. **Lazy boto3 import in notifications.py**: boto3 is NOT in pyproject.toml dependencies — it's lazy-imported inside `notify()` so local runs without boto3 installed aren't broken. Don't add boto3 as a hard dependency.

5. **Lambda env vars for secrets**: `ANTHROPIC_API_KEY` and `database_url` are passed as Lambda environment variables marked `sensitive = true` in Terraform. This is the accepted pattern for this project (not Secrets Manager).

**Why:** Personal/sensitive data (resume, OAuth tokens, session cookies) flowing into git would be a serious privacy incident. SQL injection would compromise the PostgreSQL match cache.

**How to apply:** Always verify gitignore patterns cover both legacy root-level paths AND new `data/` paths when reviewing path-related changes.
