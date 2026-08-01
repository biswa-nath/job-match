"""
AWS Lambda entry point. Invoked by EventBridge on a daily schedule.
"""

import os

import config
from main import main
from notifications import notify

# Permitted root for resume PDFs on EFS. All resume paths must resolve within here.
_RESUME_ROOT = os.path.realpath(config._SESSION_DIR)


def _validate_resume_path(path: str) -> bool:
    """Return True only if the resolved path stays inside _RESUME_ROOT."""
    return os.path.realpath(path).startswith(_RESUME_ROOT + os.sep)


def handler(event: dict, context) -> dict:
    """
    EventBridge event payload (all fields optional):
        {"source": "all"}              — scrape all job boards (default)
        {"source": "linkedin"}         — scrape LinkedIn only
        {"source": "indeed"}           — scrape Indeed only
        {"resume": "/mnt/efs/cv.pdf"}  — override RESUME_PATH env var

    RESUME_PATH env var (or event["resume"]) must point to a PDF inside SESSION_DIR.
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

    if not _validate_resume_path(resume):
        notify(
            f"job-matcher Lambda: resume path outside permitted directory — rejected: {resume}"
        )
        return {
            "statusCode": 400,
            "source": source,
            "error": "Invalid resume path",
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
