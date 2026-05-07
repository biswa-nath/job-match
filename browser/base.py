import json
from abc import ABC, abstractmethod

from playwright.sync_api import Playwright, BrowserContext, Page
from rich.console import Console

from browser.session import save_cookies, load_cookies
import config

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

    def _make_scraping_context(self, playwright: Playwright) -> tuple:
        """Create a headless browser + context for scraping. Override to customise."""
        browser = playwright.chromium.launch(headless=True)
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
            except Exception:
                pass
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
        js_cond = " && ".join(
            f"!window.location.href.includes({json.dumps(p)})"
            for p in self._login_excluded_patterns
        )
        page.wait_for_function(f"() => {js_cond}", timeout=120_000)
        console.print(f"[green]{self.name} login detected. Saving session.[/green]")
        save_cookies(context, self.session_file)
        browser.close()

    def create_scraping_browser(
        self, playwright: Playwright
    ) -> tuple[BrowserContext, Page]:
        """Headless browser with saved session cookies loaded."""
        _browser, context = self._make_scraping_context(playwright)
        page = context.new_page()
        load_cookies(context, self.session_file)
        return context, page

    @abstractmethod
    def get_saved_jobs(self, page: Page) -> list[dict]:
        """Return list of job stubs: {url, position, company, location, office_type}."""

    @abstractmethod
    def extract_job_details(self, page: Page, job: dict) -> dict:
        """Return job dict enriched with 'description' key."""
