---
name: known-bugs
description: Confirmed latent bugs in the job-match codebase — patterns the reviewer should flag if they appear in new code
metadata:
  type: feedback
---

These are confirmed latent bugs in the existing codebase. Document them so the reviewer can flag the same pattern if it appears in new code.

**Why:** The project has no automated tests, so bugs survive until a review catches them. Knowing the recurring anti-patterns prevents them from spreading.

**How to apply:** When reviewing new code, check each pattern below. If a new feature repeats the same mistake, flag it at the appropriate severity. If a PR fixes one of these, remove or update the entry.

---

1. **Sheet/DB state divergence → duplicate sheet rows** (`main.py:61-70`)

   If `append_job_row()` succeeds but `mark_added_to_sheet()` then raises, `added_to_sheet` stays `FALSE`. On the next run the row is re-appended. Pattern to flag: any "write to external system → mark in DB" sequence where the mark step is not atomic with the write. Fix direction: idempotency key on the external write, or accept the duplicate and deduplicate on read.

2. **Missing UNIQUE constraints on deduplication columns** (`db/database.py`)

   `resume.signature` and `jobs.job_link` have indexes but no `UNIQUE` constraints. `get_or_create_*` uses SELECT-then-INSERT without atomicity — concurrent Lambda invocations can create duplicate rows. Pattern to flag: any new `get_or_create_*` function that doesn't use `INSERT ... ON CONFLICT DO NOTHING RETURNING id` (or equivalent). See [[architecture-conventions]] for caching context.

3. **Bare `json.loads` on externally-sourced strings** (`matcher/llm_matcher.py:54`)

   `json.loads(json_match.group())` has no `try/except`. A regex match that grabs non-JSON curly braces raises `json.JSONDecodeError` which surfaces as a generic "LLM error". Pattern to flag: any `json.loads()` call on LLM output, scraped text, or API responses without a `try/except json.JSONDecodeError`.

4. **`break` on sheet error silently skips remaining jobs** (`main.py:137-142`, `173`)

   Non-`RefreshError` sheet exceptions hit `except Exception: break`, abandoning the remaining job loop. Pattern to flag: new per-item processing loops that `break` on an error that is not truly unrecoverable for the remaining items. The established convention is `continue` for per-item errors, `break` only for unrecoverable auth failures.

5. **Google Sheets API range column count mismatch** (`sheets/google_sheets.py:70`)

   API range `A:I` covers 9 columns but the `row` list has 10 elements — the last column (LLM recommendation) may be silently dropped. Pattern to flag: any new `append_values` call where the range column span (`A:X`) does not match `len(row)`.
