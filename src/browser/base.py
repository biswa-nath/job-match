import json
import re
from abc import ABC, abstractmethod
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Playwright, BrowserContext, Page
from rich.console import Console

from browser.session import save_cookies, load_cookies
import config
from notifications import notify

console = Console()


class JobBoardBrowser(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Source identifier matching a key in config.SESSION_FILES."""

    @property
    @abstractmethod
    def login_url(self) -> str:
        """URL to open for manual login."""

    @property
    @abstractmethod
    def saved_jobs_url(self) -> str:
        """URL of the saved jobs listing page."""

    @property
    def _login_excluded_patterns(self) -> list[str]:
        """URL substrings that indicate login is not yet complete. Override per source."""
        return [self.login_url]

    @property
    def session_file(self) -> str:
        return config.SESSION_FILES[self.name]

    def _login_success(self, url: str) -> bool:
        return not any(p in url for p in self._login_excluded_patterns)

    def _is_session_valid(self, page: Page) -> bool:
        """Navigate to saved_jobs_url and confirm no redirect to login."""
        page.goto(self.saved_jobs_url, wait_until="domcontentloaded", timeout=15_000)
        return self._login_success(page.url)

    def _make_headed_context(self, playwright: Playwright) -> tuple:
        """Create a headed browser + context for login. Override to customise launch args."""
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        return browser, context

    @staticmethod
    def _container_args() -> list[str]:
        """Extra Chromium flags required when running inside Lambda / containers."""
        if not config.LAMBDA_MODE:
            return []
        return [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-zygote",
        ]

    def _make_scraping_context(self, playwright: Playwright) -> tuple:
        """Create a headless browser + context for scraping. Override to customise."""
        browser = playwright.chromium.launch(headless=True, args=self._container_args())
        context = browser.new_context()
        return browser, context

    def login(self, playwright: Playwright) -> None:
        """Headed browser: validate or refresh session, save cookies, close."""
        browser, context = self._make_headed_context(playwright)
        page = context.new_page()

        if load_cookies(context, self.session_file):
            console.print(
                f"[cyan]Loaded saved {self.name} session — checking validity...[/cyan]"
            )
            try:
                if self._is_session_valid(page):
                    console.print(f"[green]{self.name} session is valid.[/green]")
                    browser.close()
                    return
            except Exception as e:
                console.print(f"[red]Error checking {self.name} session:[/red] {e}")

            console.print(
                f"[yellow]{self.name} session expired. Starting fresh login.[/yellow]"
            )
            context.clear_cookies()

        console.print(
            f"[bold]Please log in to {self.name} in the browser window.[/bold]"
        )
        page.goto(self.login_url, wait_until="domcontentloaded")
        # wait_for_function polls via JS — more reliable than wait_for_url for
        # OAuth/SPA flows where Playwright navigation events may not fire
        login_exclude = self._login_excluded_patterns or self.login_url
        js_cond = " && ".join(
            f"!window.location.href.includes({json.dumps(p)})" for p in login_exclude
        )

        page.wait_for_function(f"() => {js_cond}", timeout=120_000)
        console.print(f"[green]{self.name} login detected. Saving session.[/green]")
        save_cookies(context, self.session_file)
        browser.close()

    def check_session_headless(self, playwright: Playwright) -> bool:
        """
        Check session validity without a headed browser.
        Used in headless-only / Lambda mode instead of login().
        """
        console.print(f"[dim]Checking {self.name} session validity[/dim]")
        _browser, context = self._make_scraping_context(playwright)
        page = context.new_page()
        try:
            load_cookies(context, self.session_file)
            return self._is_session_valid(page)
        except Exception:
            return False
        finally:
            context.browser.close()

    def create_scraping_browser(
        self, playwright: Playwright
    ) -> tuple[BrowserContext, Page]:
        """Headless browser with saved session cookies loaded."""
        _browser, context = self._make_scraping_context(playwright)
        page = context.new_page()
        load_cookies(context, self.session_file)
        return context, page

    def open_session(
        self, playwright: Playwright, headless_only: bool
    ) -> tuple[BrowserContext, Page] | None:
        """
        Ensure a valid login (interactive unless headless_only) and return a
        scraping browser. Returns None, after alerting, if headless_only and the
        saved session is invalid.
        """
        if headless_only:
            if not self.check_session_headless(playwright):
                notify(
                    f"{self.name} session is invalid or expired. "
                    f"Run `uv run job-matcher --source {self.name}` locally to "
                    f"log in and refresh {self.session_file}."
                )
                return None
        else:
            self.login(playwright)
        return self.create_scraping_browser(playwright)

    # Lower-case phrases that mark a posting as closed. Subclasses may extend.
    closed_phrases: tuple[str, ...] = (
        "no longer accepting applications",
        "this job has expired",
        "this job is no longer available",
    )

    # Closed banners sit at the top of the posting (or are the whole page, as on
    # Indeed's expired page). Only this many leading characters of the main
    # content are searched, so "closed" badges on related jobs further down an
    # open posting are not mistaken for the posting's own status.
    closed_scan_chars: int = 1500

    @staticmethod
    def _job_key(url: str) -> str | None:
        """Identifier that must survive redirects: Indeed's `jk`, else the last
        run of 6+ digits in the path (LinkedIn / Naukri job ids)."""
        parsed = urlparse(url)
        jk = parse_qs(parsed.query).get("jk")
        if jk:
            return jk[0]
        ids = re.findall(r"\d{6,}", parsed.path)
        return ids[-1] if ids else None

    def _landed_on_job(self, requested: str, final: str) -> bool:
        key = self._job_key(requested)
        if key:
            return key in final
        return urlparse(requested).path.rstrip("/") == urlparse(final).path.rstrip("/")

    def closed_reason(self, page: Page, url: str) -> str | None:
        """
        Open a job page and return why it is closed (HTTP status, or the matched
        phrase with surrounding text), or None if it still looks open. Raises if
        the page cannot be loaded or is not the requested job (login wall,
        redirect, bot block) — callers must treat that as "unknown", never as
        closed.
        """
        response = page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        if not self._landed_on_job(url, page.url):
            raise RuntimeError(f"redirected away from the job page to {page.url}")
        if response and response.status in (404, 410):
            return f"HTTP {response.status}"
        container = page.locator("main")
        if container.count() == 0:
            container = page.locator("body")
        text = " ".join(container.first.inner_text().split())[: self.closed_scan_chars]
        lowered = text.lower()
        for phrase in self.closed_phrases:
            at = lowered.find(phrase)
            if at != -1:
                start, end = max(0, at - 40), at + len(phrase) + 40
                return f'"{phrase}" — …{text[start:end]}…'
        return None

    @abstractmethod
    def get_saved_jobs(self, page: Page) -> list[dict]:
        """Return list of job stubs: {url, position, company, location, office_type}."""

    @abstractmethod
    def extract_job_details(self, page: Page, job: dict) -> dict:
        """Return job dict enriched with 'description' key."""
