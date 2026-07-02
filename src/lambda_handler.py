"""
AWS Lambda entry point. Invoked by EventBridge on a daily schedule.
"""

from main import main
from notifications import notify


def handler(event: dict, context) -> dict:
    """
    EventBridge event payload (all fields optional):
        {"source": "all"}        — scrape all job boards (default)
        {"source": "linkedin"}   — scrape LinkedIn only
        {"source": "indeed"}     — scrape Indeed only
    """
    source = event.get("source", "all")

    try:
        main(["--source", source, "--headless-only"], standalone_mode=False)
        return {"statusCode": 200, "source": source}
    except SystemExit as e:
        return {"statusCode": 500, "source": source, "error": str(e)}
    except Exception as e:
        notify(f"job-matcher Lambda crashed unexpectedly: {type(e).__name__}: {e}")
        raise
