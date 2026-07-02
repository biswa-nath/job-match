---
name: architecture-conventions
description: Core architectural rules for the job-match codebase — config, browser OOP, caching, error isolation
metadata:
  type: feedback
---

**Config**: All configuration goes through `src/config.py` (imported as `import config`). Never hardcode paths, model names, thresholds, or URLs elsewhere. Session file paths now constructed as `os.path.join(_SESSION_DIR, filename)` where `_SESSION_DIR = os.getenv("SESSION_DIR", "data")`.

**Browser OOP pattern**: `JobBoardBrowser` (in `src/browser/base.py`) is the ABC. Subclasses must implement `name`, `login_url`, `saved_jobs_url`, `get_saved_jobs()`, `extract_job_details()`. New boards: add to `config.SUPPORTED_SOURCES` and `config.SESSION_FILES`, create `src/browser/<name>.py`, export `Browser = <Class>`. 

**Lambda mode**: `config.LAMBDA_MODE = os.getenv("LAMBDA_MODE", "").lower() in ("1", "true")`. In Lambda mode: no headed browser, no OAuth flow (raises `RefreshError` instead), SNS alerts for session expiry. `--headless-only` CLI flag implies the same behaviour. `effective_headless_only = headless_only or config.LAMBDA_MODE`.

**Error isolation pattern**: `_maybe_add_to_sheet()` is the model — sheets errors and DB errors are isolated from each other. Outer try/except catches the whole call; inner try/except catches just the `mark_added_to_sheet` DB write. The `_add_to_sheet` closure in `_run_source()` adds a `sheets_auth_failed` flag to short-circuit subsequent calls after a `RefreshError`.

**Caching**: Cache key is `(resume_id, job_id)`. `get_match()` returns existing row → skip LLM. `added_to_sheet` flag → skip sheet write. Both checks must be respected in any new flow.

**Data directory**: Sensitive runtime files live in `data/` locally and `/mnt/efs` in Lambda. `DEFAULT_RESUME = os.path.join(_SESSION_DIR, "resume.txt")` — this changed in PR #3 (was `"resume.txt"` at root). Existing users must move their resume to `data/resume.txt`.

**Playwright cleanup**: Use `context.browser.close()` (not `browser.close()` directly when browser ref is discarded). The `with sync_playwright()` context manager is the ultimate safety net — all browsers are closed when it exits.

**`_parse_sources()` behavior**: Silently filters unknown sources from colon-separated input (post PR #3). Only raises sys.exit(1) if ALL sources are unknown. Single unknown source `--source fakeboard` exits; `--source linkedin:fakeboard` silently processes only linkedin.
