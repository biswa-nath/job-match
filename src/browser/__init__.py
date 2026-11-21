import importlib
from urllib.parse import urlparse

import config
from browser.base import JobBoardBrowser


def source_for_url(url: str) -> str | None:
    """Return the supported source whose domain is url's host, else None."""
    host = (urlparse(url).hostname or "").lower()
    return next(
        (
            s
            for s in config.SUPPORTED_SOURCES
            if host == f"{s}.com" or host.endswith(f".{s}.com")
        ),
        None,
    )


def get_browser(source: str) -> JobBoardBrowser:
    if source not in config.SUPPORTED_SOURCES:
        raise ValueError(
            f"Unknown source '{source}'. Supported: {config.SUPPORTED_SOURCES}"
        )
    mod = importlib.import_module(f"browser.{source}")
    return mod.Browser()
