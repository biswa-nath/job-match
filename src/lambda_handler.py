"""
AWS Lambda entry point. Invoked by EventBridge on a daily schedule.
"""

import config
from main import main
from notifications import notify


def handler(event: dict, context) -> dict:
    """
    EventBridge event payload (all fields optional):
        {"source": "all"}              — scrape all job boards (default)
        {"source": "linkedin"}         — scrape LinkedIn only
        {"source": "indeed"}           — scrape Indeed only
        {"resume": "/mnt/efs/cv.pdf"}  — override RESUME_PATH env var

    RESUME_PATH env var (or event["resume"]) must point to a PDF on EFS.
    """
    source = event.get("source", "all")
    resume = event.get("resume", config.RESUME_PATH)

    if not resume:
        notify(
            "job-matcher Lambda: RESUME_PATH is not set and no resume in event payload."
        )
        return {
            "statusCode": 500,
            "source": source,
            "error": "RESUME_PATH not configured",
        }

    try:
        main(
            ["--source", source, "--resume", resume, "--headless-only"],
            standalone_mode=False,
        )
        return {"statusCode": 200, "source": source}
    except SystemExit as e:
        return {"statusCode": 500, "source": source, "error": str(e)}
    except Exception as e:
        notify(f"job-matcher Lambda crashed unexpectedly: {type(e).__name__}: {e}")
        raise
