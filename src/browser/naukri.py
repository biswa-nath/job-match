import time

from playwright.sync_api import Page, TimeoutError
from rich.console import Console

import config
from browser.base import JobBoardBrowser

console = Console()

_STEALTH_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)


class NaukriBrowser(JobBoardBrowser):
    name = "naukri"
    login_url = "https://www.naukri.com/nlogin/login"
    saved_jobs_url = "https://www.naukri.com/mnjuser/savedjobs"

    @property
    def _login_excluded_patterns(self) -> list[str]:
        return ["naukri.com/nlogin/login"]

    def _make_headed_context(self, playwright):
        browser = playwright.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context()
        context.add_init_script(_STEALTH_SCRIPT)
        return browser, context

    def _make_scraping_context(self, playwright):
        # Akamai WAF detects "HeadlessChrome" in the User-Agent and blocks the request.
        # We launch with system Chrome and override the UA to remove the "Headless" marker.
        # Lambda has no system Chrome, so fall back to Playwright Chromium there.
        kwargs = {} if config.LAMBDA_MODE else {"channel": "chrome"}
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                *self._container_args(),
            ],
            **kwargs,
        )
        # Strip "HeadlessChrome" → "Chrome" from the default UA so Akamai sees a
        # normal browser fingerprint.
        probe = browser.new_page()
        ua = probe.evaluate("navigator.userAgent").replace("HeadlessChrome", "Chrome")
        probe.close()
        context = browser.new_context(user_agent=ua)
        context.add_init_script(_STEALTH_SCRIPT)
        return browser, context

    def get_saved_jobs(self, page: Page) -> list[dict]:
        page.goto(self.saved_jobs_url, wait_until="domcontentloaded")

        try:
            page.wait_for_selector(
                "article.one-theme-job-tuple", state="attached", timeout=15_000
            )
        except TimeoutError:
            console.print("[yellow]No saved Naukri job cards found.[/yellow]")
            return []

        # Naukri may lazy-load additional cards — scroll to trigger them.
        prev_count = 0
        while True:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            count = page.locator("article.one-theme-job-tuple").count()
            if count == prev_count:
                break
            prev_count = count

        jobs: list[dict] = []
        seen: set[str] = set()

        cards = page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('article.one-theme-job-tuple').forEach(card => {
                const link = card.querySelector('a.tupleLink');
                const tuple = card.querySelector('.tuple');
                const titleEl = card.querySelector('.title');
                const orgEl = card.querySelector('.org');
                const locEl = card.querySelector('.location-container .loc');

                const jobId = tuple ? tuple.dataset.jobid : '';
                const href = link ? link.href : '';
                const title = titleEl ? (titleEl.title || titleEl.innerText.trim()) : '';
                const company = orgEl ? orgEl.innerText.trim() : '';
                // title attribute holds the full untruncated location
                const location = locEl ? (locEl.title || locEl.innerText.trim()) : '';

                if (jobId && href) {
                    results.push({ href, jobId, title, company, location });
                }
            });
            return results;
        }""")

        for card in cards:
            job_id = card.get("jobId", "")
            if not job_id or job_id in seen:
                continue
            seen.add(job_id)
            jobs.append(
                {
                    "url": card["href"],
                    "position": card.get("title", ""),
                    "company": card.get("company", ""),
                    "location": card.get("location", ""),
                    "office_type": "",
                }
            )

        console.print(f"[cyan]Found {len(jobs)} saved Naukri job(s).[/cyan]")
        return jobs

    def extract_job_details(self, page: Page, job: dict) -> dict:
        page.goto(job["url"], wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        description = page.evaluate("""() => {
            const el = document.querySelector('[class*="dang-inner-html"]');
            return el ? el.innerText.trim() : '';
        }""")

        return {**job, "description": description}


Browser = NaukriBrowser
