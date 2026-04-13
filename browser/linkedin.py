import re
import time

from playwright.sync_api import Playwright, BrowserContext, Page
from rich.console import Console

from browser.session import save_cookies, load_cookies, is_session_valid
import config

console = Console()

SAVED_JOBS_URL = "https://www.linkedin.com/jobs-tracker/?stage=saved"


def login(playwright: Playwright) -> None:
    """
    Ensure a valid LinkedIn session exists. Uses a headed browser so the
    user can log in manually if needed. Saves cookies and closes the browser.
    """
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    session_loaded = load_cookies(context, config.SESSION_FILE)

    if session_loaded:
        console.print("[cyan]Loaded saved session — checking validity...[/cyan]")
        try:
            if is_session_valid(page):
                console.print("[green]Session is valid.[/green]")
                browser.close()
                return
        except Exception:
            pass
        console.print("[yellow]Session expired. Starting fresh login.[/yellow]")
        context.clear_cookies()

    console.print("[bold]Please log in to LinkedIn in the browser window.[/bold]")
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    page.wait_for_url(
        lambda url: (
            "linkedin.com/login" not in url and "linkedin.com/checkpoint" not in url
        ),
        timeout=120_000,
    )
    console.print("[green]Login detected. Saving session.[/green]")
    save_cookies(context, config.SESSION_FILE)
    browser.close()


def create_scraping_browser(playwright: Playwright) -> tuple[BrowserContext, Page]:
    """
    Launch a headless browser with the saved session for scraping.
    Call login() first to ensure the session is valid.
    """
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    load_cookies(context, config.SESSION_FILE)
    return context, page


def _parse_job_meta(subtitle: str) -> tuple[str, str, str]:
    """
    Parse 'Company · Location (Office)' subtitle from the saved jobs listing.

    Examples:
      'GoDaddy · Gurugram (On-site)'   → ('GoDaddy', 'Gurugram', 'On-site')
      'Wayfair · Bengaluru (Hybrid)'   → ('Wayfair', 'Bengaluru', 'Hybrid')
      'Alteryx · Bengaluru'            → ('Alteryx', 'Bengaluru', 'On-site')
      'GitLab · Greater Delhi Area (Remote)' → ('GitLab', 'Greater Delhi Area', 'Remote')
    """
    parts = subtitle.split("·", 1)
    company = parts[0].strip()
    if len(parts) == 1:
        return company, "", "On-site"

    rest = parts[1].strip()
    match = re.search(r"\(([^)]+)\)\s*$", rest)
    if match:
        office_type = match.group(1).strip()
        location = rest[: match.start()].strip()
    else:
        location = rest
        office_type = "On-site"

    return company, location, office_type


def _clean_position(raw: str, company: str) -> str:
    """Strip company name and trailing metadata from the raw anchor innerText."""
    if company and company in raw:
        raw = raw[: raw.index(company)].strip()
    return raw


def get_saved_jobs(page: Page) -> list[dict]:
    """
    Navigate to the saved jobs listing and collect all jobs with
    url, company, location, and office_type extracted from the listing cards.
    """
    page.goto(SAVED_JOBS_URL, wait_until="domcontentloaded")
    jobs: list[dict] = []
    seen: set[str] = set()

    while True:
        page.wait_for_selector(
            "a[href*='/jobs/view/']", state="attached", timeout=15_000
        )

        # Extract link + subtitle text from each card in one JS call
        cards = page.evaluate("""() => {
            const seen = new Set();
            const result = [];
            document.querySelectorAll('a[href*="/jobs/view/"]').forEach(a => {
                const m = a.href.match(/\\/jobs\\/view\\/(\\d+)\\//);
                if (!m || seen.has(m[1])) return;
                seen.add(m[1]);

                const card = a.closest('li') || a.closest('[data-job-id]') || a.parentElement;
                let subtitle = '';
                if (card) {
                    // Find a leaf element whose text contains the '·' separator
                    for (const el of card.querySelectorAll('*')) {
                        if (el.children.length === 0 && el.innerText && el.innerText.includes('·')) {
                            subtitle = el.innerText.trim();
                            break;
                        }
                    }
                }
                result.push({ href: a.href, position: a.innerText.trim(), subtitle });
            });
            return result;
        }""")

        for card in cards:
            href = card["href"]
            match = re.search(r"/jobs/view/(\d+)/", href)
            if not match or match.group(1) in seen:
                continue
            seen.add(match.group(1))
            url = f"https://www.linkedin.com/jobs/view/{match.group(1)}/"
            company, location, office_type = _parse_job_meta(card.get("subtitle", ""))
            position = _clean_position(card.get("position", ""), company)
            jobs.append(
                {
                    "url": url,
                    "position": position,
                    "company": company,
                    "location": location,
                    "office_type": office_type,
                }
            )

        next_btn = page.get_by_role("button", name="Next")
        if next_btn.count() > 0 and next_btn.is_enabled():
            next_btn.click()
            time.sleep(2)
        else:
            break

    console.print(f"[cyan]Found {len(jobs)} saved job(s).[/cyan]")
    return jobs


def extract_job_details(page: Page, job: dict) -> dict:
    """
    Navigate to the job page and add description to the job dict.
    position/company/location/office_type already extracted from
    the listing page.
    """
    url = job["url"]
    page.goto(url, wait_until="load")
    page.wait_for_timeout(3000)

    # Description from sdui container
    about_selector = (
        'div[data-sdui-component="com.linkedin.sdui.generated'
        '.jobseeker.dsl.impl.aboutTheJob"]'
    )
    el = page.query_selector(about_selector)
    description = el.inner_text().strip() if el else ""

    # Fallback: content after the "About the job" h2
    if not description:
        description = page.evaluate("""() => {
            const h2s = [...document.querySelectorAll('h2')];
            const heading = h2s.find(h => h.innerText.trim() === 'About the job');
            if (!heading) return '';
            const section = heading.closest('section');
            if (section) return section.innerText.trim();
            const next = heading.parentElement?.nextElementSibling;
            return next ? next.innerText.trim() : '';
        }""")

    return {**job, "description": description}
