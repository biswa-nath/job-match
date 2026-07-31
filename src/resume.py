"""PDF text extraction and PII redaction via Presidio."""

from __future__ import annotations

from rich.console import Console

console = Console(stderr=True)

# Entities to redact. LOCATION and DATE_TIME are intentionally excluded —
# location context (e.g. "San Francisco") is useful to the LLM.
REDACT_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"]

# Product/brand names that spaCy's NER mistakenly tags as PERSON.
REDACT_ALLOW_LIST = ["Claude"]

# Words that spaCy appends to PERSON spans but are not part of a name.
_NON_NAME_WORDS = frozenset(
    {
        "engineering",
        "engineer",
        "leader",
        "manager",
        "director",
        "head",
        "chief",
        "senior",
        "junior",
        "principal",
        "staff",
        "architect",
        "developer",
        "product",
        "technology",
        "technical",
        "software",
        "hardware",
        "data",
        "science",
        "scientist",
        "analyst",
        "consultant",
        "vp",
        "svp",
        "evp",
        "cto",
        "ceo",
        "coo",
        "cpo",
    }
)


def extract_pdf(path: str) -> str:
    """Extract and return plain text from all pages of a PDF."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError(
            "pdfplumber is required for PDF extraction.\nInstall it: uv add pdfplumber"
        )

    texts: list[str] = []
    failed = 0
    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
        for i, page in enumerate(pdf.pages, 1):
            try:
                text = page.extract_text() or ""
                texts.append(text)
            except Exception as e:
                console.print(
                    f"[yellow]⚠ PDF page {i}/{total} failed to extract: {e}[/]"
                )
                failed += 1

    if failed:
        console.print(f"[yellow]⚠ {failed}/{total} PDF pages could not be extracted[/]")

    return "\n\n".join(texts)


def redact(text: str, entities: list[str] | None = None) -> str:
    """Redact PII from text using Presidio. Returns redacted text."""
    try:
        from presidio_anonymizer import AnonymizerEngine
        from presidio_anonymizer.entities import OperatorConfig
    except ImportError:
        raise ImportError(
            "presidio-analyzer and presidio-anonymizer are required for PII redaction.\n"
            "Install them: uv add presidio-analyzer presidio-anonymizer spacy\n"
            "Then run: python -m spacy download en_core_web_lg"
        )

    if entities is None:
        entities = REDACT_ENTITIES

    analyzer = _get_analyzer()
    anonymizer = AnonymizerEngine()

    results = analyzer.analyze(
        text=text, entities=entities, language="en", allow_list=REDACT_ALLOW_LIST
    )
    results = _trim_person_spans(text, results)

    operators = {
        entity: OperatorConfig("replace", {"new_value": f"__REDACTED_{entity}__"})
        for entity in entities
    }

    return anonymizer.anonymize(
        text=text, analyzer_results=results, operators=operators
    ).text


def _trim_person_spans(text: str, results: list) -> list:
    """Trim trailing non-name tokens (e.g. job title words) from PERSON spans."""
    from presidio_analyzer import RecognizerResult

    trimmed = []
    for r in results:
        if r.entity_type == "PERSON":
            span = text[r.start : r.end]
            words = span.split()
            while (
                len(words) > 1 and words[-1].lower().strip(".,;:|") in _NON_NAME_WORDS
            ):
                words.pop()
            new_end = r.start + len(" ".join(words))
            if new_end != r.end:
                r = RecognizerResult(r.entity_type, r.start, new_end, r.score)
        trimmed.append(r)
    return trimmed


_analyzer_instance = None


def _get_analyzer():
    """Lazy singleton — spaCy model loads once per process."""
    global _analyzer_instance
    if _analyzer_instance is None:
        from presidio_analyzer import AnalyzerEngine

        _analyzer_instance = AnalyzerEngine()
    return _analyzer_instance
