import json
import os


def save_cookies(context, path: str) -> None:
    """Serialize browser context cookies to a JSON file."""
    cookies = context.cookies()
    with open(path, "w") as f:
        json.dump(cookies, f, indent=2)


def load_cookies(context, path: str) -> bool:
    """Restore cookies from file into browser context. Returns True if loaded."""
    if not os.path.exists(path):
        return False
    with open(path) as f:
        cookies = json.load(f)
    context.add_cookies(cookies)
    return True


def is_session_valid(page) -> bool:
    """Check if the current LinkedIn session is still active."""
    page.goto(
        "https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000
    )
    return "feed" in page.url and "login" not in page.url
