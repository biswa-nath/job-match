import re
import time

from playwright.sync_api import Page, TimeoutError
from rich.console import Console

from browser.base import JobBoardBrowser

console = Console()


class LinkedInBrowser(JobBoardBrowser):
    name = "linkedin"
    login_url = "https://www.linkedin.com/login"
    saved_jobs_url = "https://www.linkedin.com/jobs-tracker/?stage=saved"

    @property
    def _login_excluded_patterns(self) -> list[str]:
        return ["linkedin.com/login", "linkedin.com/checkpoint"]

    @staticmethod
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

    @staticmethod
    def _clean_position(raw: str, company: str) -> str:
        """Strip company name and trailing metadata from the raw anchor innerText."""
        if company and company in raw:
            raw = raw[: raw.index(company)].strip()
        return raw

    def get_saved_jobs(self, page: Page) -> list[dict]:
        """
        Navigate to the saved jobs listing and collect all jobs with
        url, company, location, and office_type extracted from the listing cards.
        """
        page.goto(self.saved_jobs_url, wait_until="domcontentloaded")
        jobs: list[dict] = []
        seen: set[str] = set()

        while True:
            try:
                page.wait_for_selector(
                    "a[href*='/jobs/view/']", state="attached", timeout=15_000
                )
            except TimeoutError:
                break

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
                company, location, office_type = self._parse_job_meta(
                    card.get("subtitle", "")
                )
                position = self._clean_position(card.get("position", ""), company)
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

        console.print(f"[cyan]Found {len(jobs)} saved LinkedIn job(s).[/cyan]")
        return jobs

    def extract_job_details(self, page: Page, job: dict) -> dict:
        """
        Navigate to the job page and add description to the job dict.
        position/company/location/office_type already extracted from
        the listing page.
        """
        url = job["url"]
        page.goto(url, wait_until="load")
        page.wait_for_timeout(3000)

        about_selector = (
            'div[data-sdui-component="com.linkedin.sdui.generated'
            '.jobseeker.dsl.impl.aboutTheJob"]'
        )
        el = page.query_selector(about_selector)
        description = el.inner_text().strip() if el else ""

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


Browser = LinkedInBrowser
