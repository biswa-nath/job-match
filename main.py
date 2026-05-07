import sys

import click
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.table import Table

import config
from browser import get_browser
from browser.base import JobBoardBrowser
from db.database import (
    get_connection,
    init_db,
    get_or_create_resume,
    get_or_create_job,
    get_match,
    save_match,
    mark_added_to_sheet,
)
from matcher.llm_matcher import match_job
from sheets.google_sheets import append_job_row

console = Console()


def _parse_sources(source: str) -> list[str]:
    source = source.strip().lower()
    if source == "all":
        return config.SUPPORTED_SOURCES
    return [
        s.strip().lower()
        for s in source.split(":")
        if s.strip().lower() in config.SUPPORTED_SOURCES
    ]


def _maybe_add_to_sheet(
    job: dict,
    match_id: int,
    score: int,
    recommendation: str,
    threshold: int,
    dry_run: bool,
    conn,
) -> bool:
    """
    Append to Google Sheet if score >= threshold and not already added.
    Returns True if added (or would have been added in dry-run).
    """
    if score < threshold:
        return False
    if dry_run:
        console.print(
            f"[yellow](dry-run) Would add to sheet:[/yellow] "
            f"{job.get('position')} @ {job.get('company')} — {score}%"
        )
        return False
    try:
        append_job_row(job, score, recommendation)
    except Exception as e:
        console.print(f"[red]Google Sheets error:[/red] {e}")
        raise
    try:
        mark_added_to_sheet(conn, match_id)
    except Exception as e:
        console.print(f"[red]Database error (sheet row was written):[/red] {e}")
    return True


def _run_source(
    browser: JobBoardBrowser,
    resume_id: int,
    resume_text: str,
    conn,
    threshold: int,
    dry_run: bool,
) -> list[dict]:
    """Run the scrape+match pipeline for one job board. Returns results."""
    results = []

    with sync_playwright() as pw:
        browser.login(pw)
        context, page = browser.create_scraping_browser(pw)

        saved_jobs = browser.get_saved_jobs(page)
        if not saved_jobs:
            console.print(f"[yellow]No saved jobs found on {browser.name}.[/yellow]")
            context.browser.close()
            return results

        for job_stub in saved_jobs:
            console.print(f"\n[cyan]Processing:[/cyan] {job_stub['url']}")
            job_id = get_or_create_job(conn, job_stub["url"])

            existing = get_match(conn, resume_id, job_id)
            if existing:
                score = existing["score"]
                recommendation = existing["recommendation"]
                console.print(f"[dim]Cached match — score: {score}%[/dim]")

                added = False
                if not existing["added_to_sheet"]:
                    try:
                        added = _maybe_add_to_sheet(
                            job_stub,
                            existing["id"],
                            score,
                            recommendation,
                            threshold,
                            dry_run,
                            conn,
                        )
                    except Exception:
                        break

                results.append(
                    {
                        **job_stub,
                        "score": score,
                        "recommendation": recommendation,
                        "cached": True,
                        "added": added or existing["added_to_sheet"],
                        "source": browser.name,
                    }
                )
                continue

            try:
                job = browser.extract_job_details(page, job_stub)
            except Exception as e:
                console.print(f"[red]Failed to extract details:[/red] {e}")
                continue

            try:
                match = match_job(resume_text, job)
            except Exception as e:
                console.print(f"[red]LLM error:[/red] {e}")
                continue

            score = match["score"]
            recommendation = match["recommendation"]
            match_id = save_match(conn, resume_id, job_id, score, recommendation)
            try:
                added = _maybe_add_to_sheet(
                    job, match_id, score, recommendation, threshold, dry_run, conn
                )
            except Exception:
                break
            results.append(
                {
                    **job,
                    "score": score,
                    "recommendation": recommendation,
                    "cached": False,
                    "added": added,
                    "source": browser.name,
                }
            )

        context.browser.close()

    return results


@click.command()
@click.option(
    "--resume",
    default=config.DEFAULT_RESUME,
    show_default=True,
    help="Path to resume file (plain text or Markdown).",
)
@click.option(
    "--threshold",
    default=config.DEFAULT_THRESHOLD,
    show_default=True,
    type=int,
    help="Minimum match score (%) to add job to Google Sheet.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Score jobs but do not write to Google Sheet.",
)
@click.option(
    "--source",
    default="linkedin",
    show_default=True,
    help=(
        "Job board(s) to scrape. Options: linkedin, indeed, all, "
        "or colon-separated list (e.g. linkedin:indeed)."
    ),
)
def main(resume: str, threshold: int, dry_run: bool, source: str) -> None:
    """
    Scan saved jobs from LinkedIn or Indeed, score against resume,
    and add high matches to Google Sheet.
    """

    sources = _parse_sources(source)
    for s in sources:
        if s not in config.SUPPORTED_SOURCES:
            console.print(
                f"[red]Unknown source '{s}'.[/red] "
                f"Supported: {', '.join(config.SUPPORTED_SOURCES)}"
            )
            sys.exit(1)

    try:
        with open(resume) as f:
            resume_text = f.read().strip()
    except FileNotFoundError:
        console.print(f"[red]Resume file not found:[/red] {resume}")
        sys.exit(1)

    if not resume_text or resume_text.startswith("<!--"):
        console.print(
            "[red]Resume file appears empty or is still a placeholder.[/red]\n"
            f"Please fill in {resume} with your actual resume content."
        )
        sys.exit(1)

    if dry_run:
        console.print(
            "[yellow]Dry-run mode: no rows will be written to Google Sheet.[/yellow]"
        )

    conn = get_connection()
    init_db(conn)
    resume_id = get_or_create_resume(conn, resume_text)
    console.print(f"[dim]Resume id: {resume_id}[/dim]")

    all_results = []
    for source_name in sources:
        console.print(f"\n[bold]--- Scraping {source_name} ---[/bold]")
        browser = get_browser(source_name)
        all_results.extend(
            _run_source(browser, resume_id, resume_text, conn, threshold, dry_run)
        )

    conn.close()

    console.print("\n")
    table = Table(title="Job Match Summary", show_lines=True)
    table.add_column("Position", style="bold")
    table.add_column("Company")
    table.add_column("Source")
    table.add_column("Score", justify="right")
    table.add_column("Cached", justify="center")
    table.add_column("In Sheet", justify="center")

    for r in sorted(all_results, key=lambda x: x["score"], reverse=True):
        score_str = (
            f"[green]{r['score']}%[/green]"
            if r["score"] >= threshold
            else f"{r['score']}%"
        )
        cached_str = "[dim]Yes[/dim]" if r.get("cached") else "No"
        in_sheet_str = "[green]Yes[/green]" if r.get("added") else "[yellow]No[/yellow]"
        table.add_row(
            r.get("position", ""),
            r.get("company", ""),
            r.get("source", ""),
            score_str,
            cached_str,
            in_sheet_str,
        )

    console.print(table)


if __name__ == "__main__":
    main()
