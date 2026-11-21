import sys

import click
from google.auth.exceptions import RefreshError
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.table import Table

import config
from browser import get_browser, source_for_url
from db.database import deactivate_jobs_by_links, get_connection, init_db
from sheets.google_sheets import (
    delete_pending_rows_by_links,
    get_pending_links,
    still_pending_links,
)

console = Console()


def _check_source(
    source: str, links: list[str], headless_only: bool
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Check each link on one board. Returns (closed, unchecked) as (link, detail)."""
    closed: list[tuple[str, str]] = []
    unchecked: list[tuple[str, str]] = []
    browser = get_browser(source)
    with sync_playwright() as pw:
        session = browser.open_session(pw, headless_only)
        if session is None:
            return closed, [(link, "no valid session") for link in links]
        context, page = session
        try:
            for i, link in enumerate(links, start=1):
                console.print(f"[dim]({i}/{len(links)}) {link}[/dim]")
                try:
                    reason = browser.closed_reason(page, link)
                except Exception as e:
                    unchecked.append((link, str(e).splitlines()[0]))
                    continue
                if reason:
                    closed.append((link, reason))
        finally:
            context.browser.close()
    return closed, unchecked


def _cleanup(headless_only: bool) -> None:
    links = get_pending_links()
    if not links:
        console.print("[yellow]No 'Pending' rows with links in the sheet.[/yellow]")
        return

    by_source: dict[str, list[str]] = {}
    for link in links:
        source = source_for_url(link)
        if source is None:
            console.print(f"[yellow]Skipping unsupported link:[/yellow] {link}")
            continue
        by_source.setdefault(source, []).append(link)

    closed: list[tuple[str, str]] = []
    unchecked: list[tuple[str, str]] = []
    for source in config.SUPPORTED_SOURCES:
        if source not in by_source:
            continue
        console.print(
            f"\n[bold]--- Checking {len(by_source[source])} {source} link(s) ---[/bold]"
        )
        try:
            source_closed, source_unchecked = _check_source(
                source, by_source[source], headless_only
            )
        except Exception as e:
            # Isolate failures per source, as in main.py.
            console.print(f"[red]{source} check failed:[/red] {e}")
            unchecked.extend(
                (link, f"{source} check failed") for link in by_source[source]
            )
            continue
        closed.extend(source_closed)
        unchecked.extend(source_unchecked)

    if unchecked:
        console.print("\n[yellow]Could not check (left untouched):[/yellow]")
        for link, detail in unchecked:
            console.print(f"  {link} [dim]({detail})[/dim]")

    if not closed:
        console.print("\n[green]No closed postings found.[/green]")
        return

    table = Table(title="No longer accepting applications", show_lines=True)
    table.add_column("Link", overflow="fold")
    table.add_column("Reason")
    for link, reason in closed:
        table.add_row(link, reason)
    console.print("\n")
    console.print(table)

    if not click.confirm(
        f"Delete the sheet rows and mark the database entries inactive "
        f"for these {len(closed)} link(s)?"
    ):
        console.print("[yellow]Nothing deleted.[/yellow]")
        return

    # Re-read the sheet: act only on links still 'Pending' (and nowhere marked
    # otherwise), so a row updated while we were checking is left alone in both
    # the sheet and the database.
    closed_links = still_pending_links([link for link, _ in closed])
    skipped = len(closed) - len(closed_links)
    if skipped:
        console.print(
            f"[yellow]{skipped} link(s) changed status in the sheet since "
            f"the check and were left untouched.[/yellow]"
        )
    if not closed_links:
        console.print("[yellow]Nothing to delete.[/yellow]")
        return

    # DB first: if the sheet step fails, the rows are still 'Pending' and a
    # re-run finds them again (marking inactive is then a harmless no-op).
    init_db()
    conn = get_connection()
    try:
        jobs, matches = deactivate_jobs_by_links(conn, closed_links)
    finally:
        conn.close()
    console.print(
        f"[green]Database:[/green] marked {jobs} job(s) and {matches} match(es) inactive."
    )

    rows = delete_pending_rows_by_links(closed_links)
    console.print(f"[green]Sheet:[/green] deleted {rows} row(s).")


@click.command("cleanup")
@click.option(
    "--headless-only",
    is_flag=True,
    default=False,
    help="Skip browser login; skip a board if its saved session is invalid.",
)
def cleanup(headless_only: bool) -> None:
    """
    Find 'Pending' sheet rows whose job posting is closed, list them, and — after
    confirmation — delete the rows and mark their database entries inactive.
    """
    try:
        _cleanup(headless_only or config.LAMBDA_MODE)
    except RefreshError as e:
        console.print(f"[red]Google Sheets authentication failed:[/red] {e}")
        sys.exit(1)
