"""PDF text extraction and PII redaction via Presidio."""

from __future__ import annotations

from rich.console import Console

console = Console(stderr=True)

# Entities to redact. LOCATION and DATE_TIME are intentionally excluded —
# location context (e.g. "San Francisco") is useful to the LLM.
REDACT_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"]

# Strings that Presidio must NOT flag as entities.
# Includes AI product names and common resume action verbs: both are capitalised
# when they start a bullet point after a line break, causing spaCy's NER to tag
# them as proper nouns / person names.
REDACT_ALLOW_LIST = [
    # AI product names
    "Claude",
    "Gemini",
    "Copilot",
    "Grok",
    "Nova",
    # Resume action verbs — capitalised at the start of bullet lines
    "Architected",
    "Built",
    "Championed",
    "Collaborated",
    "Created",
    "Delivered",
    "Deployed",
    "Designed",
    "Developed",
    "Directed",
    "Drove",
    "Established",
    "Founded",
    "Grew",
    "Implemented",
    "Improved",
    "Increased",
    "Integrated",
    "Launched",
    "Led",
    "Managed",
    "Mentored",
    "Migrated",
    "Optimized",
    "Partnered",
    "Reduced",
    "Scaled",
    "Spearheaded",
]

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

    try:
        from pdfminer.pdfpage import PDFPasswordIncorrect
    except ImportError:
        PDFPasswordIncorrect = None  # type: ignore[assignment,misc]

    texts: list[str] = []
    failed = 0
    try:
        pdf_file = pdfplumber.open(path)
    except Exception as e:
        if PDFPasswordIncorrect and isinstance(e, PDFPasswordIncorrect):
            raise ValueError(
                "PDF is password-protected. Remove the password and try again."
            ) from e
        raise

    with pdf_file:
        total = len(pdf_file.pages)
        for i, page in enumerate(pdf_file.pages, 1):
            try:
                text = page.extract_text() or ""
                texts.append(text)
            except Exception as e:
                console.print(
                    f"[yellow]Warning: PDF page {i}/{total} failed to extract: {e}[/]"
                )
                failed += 1

    if failed:
        console.print(
            f"[yellow]Warning: {failed}/{total} PDF pages could not be extracted[/]"
        )

    return "\n\n".join(texts)


def redact(text: str, entities: list[str] | None = None) -> str:
    """Redact PII from text using Presidio. Returns redacted text."""
    try:
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
    anonymizer = _get_anonymizer()

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
    """Trim leading/trailing non-name tokens from PERSON spans.

    Works in original text coordinates to avoid whitespace-normalisation bugs:
    PDF text often contains multi-space gaps from column detection, so
    split()+join() would compute a shorter span length and under-redact.

    Trailing trim: "John Smith senior engineer" → "John Smith"
    Leading trim:  "Manager John Smith" → "John Smith"
    """
    from presidio_analyzer import RecognizerResult

    trimmed = []
    for r in results:
        if r.entity_type == "PERSON":
            span_start = r.start
            span_end = r.end

            # Trim trailing non-name words
            while True:
                current = text[span_start:span_end].rstrip()
                if not current:
                    break
                parts = current.rsplit(None, 1)
                if len(parts) <= 1:
                    break
                remaining, last_word = parts
                if last_word.lower().strip(".,;:|") in _NON_NAME_WORDS:
                    span_end = span_start + len(remaining.rstrip())
                else:
                    break

            # Trim leading non-name words
            while True:
                current = text[span_start:span_end]
                lstripped = current.lstrip()
                parts = lstripped.split(None, 1)
                if len(parts) <= 1:
                    break
                first_word, _ = parts
                if first_word.lower().strip(".,;:|") in _NON_NAME_WORDS:
                    span_start += len(current) - len(lstripped) + len(first_word)
                    while span_start < span_end and text[span_start].isspace():
                        span_start += 1
                else:
                    break

            if span_start >= span_end:
                continue  # trimmed to nothing — drop the entity
            if span_start != r.start or span_end != r.end:
                r = RecognizerResult(r.entity_type, span_start, span_end, r.score)
        trimmed.append(r)
    return trimmed


_analyzer_instance = None
_anonymizer_instance = None


def _get_analyzer():
    """Lazy singleton — spaCy model loads once per process."""
    global _analyzer_instance
    if _analyzer_instance is None:
        from presidio_analyzer import AnalyzerEngine

        _analyzer_instance = AnalyzerEngine()
    return _analyzer_instance


def _get_anonymizer():
    """Lazy singleton — reuse across calls in the same process."""
    global _anonymizer_instance
    if _anonymizer_instance is None:
        from presidio_anonymizer import AnonymizerEngine

        _anonymizer_instance = AnonymizerEngine()
    return _anonymizer_instance
