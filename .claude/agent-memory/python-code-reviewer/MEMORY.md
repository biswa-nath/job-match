# Memory Index

- [User Role](user_role.md) — Biswanath: solo developer, Python, building personal job-matching CLI tool with Lambda deployment
- [Codebase Security Patterns](feedback_security_patterns.md) — Enforced security conventions: no f-string SQL, parameterized psycopg2, session files gitignored, PII redaction before DB/LLM
- [Architecture Conventions](feedback_architecture.md) — Key architectural rules: resume pipeline (extract_pdf→redact), config.py central import, browser OOP pattern, (resume_id, job_id) cache key
- [Known Latent Bugs](feedback_known_bugs.md) — Five confirmed bug patterns to flag in new code: sheet/DB divergence, missing UNIQUE constraints, bare json.loads, break-on-error, Sheets range mismatch
