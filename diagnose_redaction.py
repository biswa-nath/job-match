"""Diagnostic: show every entity Presidio detects on the resume PDF."""

import sys

sys.path.insert(0, "src")
from resume import REDACT_ALLOW_LIST, REDACT_ENTITIES, _get_analyzer, extract_pdf

pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
if not pdf_path:
    print("Usage: uv run python diagnose_redaction.py <path-to-resume.pdf>")
    sys.exit(1)

text = extract_pdf(pdf_path)
analyzer = _get_analyzer()

print("=== RAW DETECTIONS (no allow_list) ===")
raw = analyzer.analyze(text=text, entities=REDACT_ENTITIES, language="en")
for r in sorted(raw, key=lambda x: x.start):
    span = text[r.start : r.end]
    # Show 40 chars of context before the span
    ctx_start = max(0, r.start - 40)
    ctx = repr(text[ctx_start : r.end + 20])
    print(
        f"  {r.entity_type:20s} score={r.score:.2f}  span={span!r:30s}  context={ctx}"
    )

print()
print("=== AFTER ALLOW_LIST ===")
filtered = analyzer.analyze(
    text=text, entities=REDACT_ENTITIES, language="en", allow_list=REDACT_ALLOW_LIST
)
for r in sorted(filtered, key=lambda x: x.start):
    span = text[r.start : r.end]
    ctx_start = max(0, r.start - 40)
    ctx = repr(text[ctx_start : r.end + 20])
    print(
        f"  {r.entity_type:20s} score={r.score:.2f}  span={span!r:30s}  context={ctx}"
    )
