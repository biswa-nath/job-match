"""Delete all jobs and job_matches for a given source."""

import sys

sys.path.insert(0, "src")

import click
from rich.console import Console

import config
from db.database import get_connection, delete_jobs_by_source

console = Console()


@click.command()
@click.argument("source", type=click.Choice([*config.SUPPORTED_SOURCES, "all"]))
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt.")
def main(source: str, yes: bool) -> None:
    """Delete all jobs and job_matches for SOURCE (linkedin, indeed, naukri, or all)."""
    sources = config.SUPPORTED_SOURCES if source == "all" else [source]

    conn = get_connection()
    for src in sources:
        if not yes and not click.confirm(f"Delete all {src} jobs and matches?"):
            console.print(f"[yellow]Skipped {src}.[/yellow]")
            continue
        matches_deleted, jobs_deleted = delete_jobs_by_source(conn, src)
        console.print(
            f"[green]{src}:[/green] deleted {jobs_deleted} jobs, {matches_deleted} matches"
        )
    conn.close()


if __name__ == "__main__":
    main()
