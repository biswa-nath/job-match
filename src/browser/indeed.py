import re
import time

from playwright.sync_api import Page, TimeoutError
from rich.console import Console

import config
from browser.base import JobBoardBrowser

console = Console()

# Injected into every page to hide Playwright's automation fingerprint
_STEALTH_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)


class IndeedBrowser(JobBoardBrowser):
    name = "indeed"
    login_url = "https://www.indeed.com/account/login"
    saved_jobs_url = "https://myjobs.indeed.com/saved"

    @property
    def _login_excluded_patterns(self) -> list[str]:
        return ["indeed.com/account/login", "secure.indeed.com/auth"]

    def _make_headed_context(self, playwright):
        # Use system Chrome (not Playwright's Chromium) so Cloudflare sees a real
        # browser fingerprint (canvas, plugins, etc.) during the login CAPTCHA
        browser = playwright.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context()
        context.add_init_script(_STEALTH_SCRIPT)
        return browser, context

    def _make_scraping_context(self, playwright):
        # Lambda has no system Chrome — fall back to Playwright Chromium.
        # Valid session cookies make Cloudflare much less aggressive during scraping.
        kwargs = {} if config.LAMBDA_MODE else {"channel": "chrome"}
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                *self._container_args(),
            ],
            **kwargs,
        )
        context = browser.new_context()
        context.add_init_script(_STEALTH_SCRIPT)
        return browser, context

    def get_saved_jobs(self, page: Page) -> list[dict]:
        """
        Navigate to the Indeed saved jobs listing and collect all jobs with
        url, position, company, location, and office_type.
        """
        page.goto(self.saved_jobs_url, wait_until="domcontentloaded")
        jobs: list[dict] = []
        seen: set[str] = set()

        while True:
            try:
                page.wait_for_selector(
                    "ul.atw-Updates-list", state="attached", timeout=15_000
                )
            except TimeoutError:
                break

            cards = page.evaluate("""() => {
                const results = [];
                const seen = new Set();

                document.querySelectorAll(
                    'ul.atw-Updates-list a.atw-JobInfo-jobTitle'
                ).forEach(a => {
                    const href = a.href;
                    if (a.getAttribute('aria-disabled') === 'true') return;
                    if (!href || seen.has(href)) return;
                    seen.add(href);

                    const position = a.innerText
                        .replace(/job description opens in a new window/i, '')
                        .trim();

                    const li = a.closest('li') || a.parentElement;
                    let company = '';
                    let location = '';
                    if (li) {
                        const spans = li.querySelectorAll(
                            'div.atw-JobInfo-companyLocation span'
                        );
                        if (spans[0]) company = spans[0].innerText.trim();
                        if (spans[1]) location = spans[1].innerText.trim();
                    }

                    results.push({ href, position, company, location });
                });

                return results;
            }""")

            for card in cards:
                href = card.get("href", "")
                if not href:
                    continue
                # Normalise to canonical viewjob URL and use jk as dedup key
                jk_match = re.search(r"[?&]jk=([^&]+)", href)
                jk = jk_match.group(1) if jk_match else href
                if jk in seen:
                    continue
                seen.add(jk)
                url = (
                    f"https://www.indeed.com/viewjob?jk={jk}"
                    if jk_match
                    else (
                        f"https://www.indeed.com{href}"
                        if href.startswith("/")
                        else href
                    )
                )
                jobs.append(
                    {
                        "url": url,
                        "position": card.get("position", ""),
                        "company": card.get("company", ""),
                        "location": card.get("location", ""),
                        "office_type": "",
                    }
                )

            next_btn = page.get_by_role(
                "link", name=re.compile(r"^Next$", re.IGNORECASE)
            )
            if next_btn.count() == 0:
                next_btn = page.get_by_role(
                    "button", name=re.compile(r"^Next$", re.IGNORECASE)
                )
            if next_btn.count() > 0 and next_btn.first.is_enabled():
                next_btn.first.click()
                time.sleep(2)
            else:
                break

        console.print(f"[cyan]Found {len(jobs)} saved Indeed job(s).[/cyan]")
        return jobs

    def extract_job_details(self, page: Page, job: dict) -> dict:
        """
        Navigate to the Indeed job page and add description to the job dict.
        position/company/location/office_type already populated from get_saved_jobs.
        """
        url = job["url"]
        page.goto(url, wait_until="load")
        page.wait_for_timeout(3000)

        el = page.query_selector("#jobDescriptionText")
        description = el.inner_text().strip() if el else ""

        if not description:
            el = page.query_selector('[data-testid="jobsearch-jobDescriptionText"]')
            description = el.inner_text().strip() if el else ""

        if not description:
            description = page.evaluate("""() => {
                const byId = document.querySelector('[id*="jobDescription"]');
                if (byId && byId.innerText.trim().length > 50) {
                    return byId.innerText.trim();
                }
                const byCls = document.querySelector('[class*="jobDescription"]');
                if (byCls && byCls.innerText.trim().length > 50) {
                    return byCls.innerText.trim();
                }
                return '';
            }""")

        return {**job, "description": description}


Browser = IndeedBrowser
