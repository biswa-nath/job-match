import importlib

import config
from browser.base import JobBoardBrowser


def get_browser(source: str) -> JobBoardBrowser:
    if source not in config.SUPPORTED_SOURCES:
        raise ValueError(
            f"Unknown source '{source}'. Supported: {config.SUPPORTED_SOURCES}"
        )
    mod = importlib.import_module(f"browser.{source}")
    return mod.Browser()
