import hashlib
from pathlib import Path

import psycopg2
import psycopg2.extras
from alembic import command
from alembic.config import Config

import config


def get_connection():
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in your .env file.")
    return psycopg2.connect(config.DATABASE_URL)


def init_db() -> None:
    """Apply pending Alembic migrations; also creates the schema on a fresh database."""
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    command.upgrade(cfg, "head")


def _signature(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def get_or_create_resume(conn, text: str) -> int:
    """Return the id of the resume row, inserting if new."""
    sig = _signature(text)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM resume WHERE signature = %s", (sig,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO resume (signature, text) VALUES (%s, %s) RETURNING id",
            (sig, text),
        )
        resume_id = cur.fetchone()[0]
    conn.commit()
    return resume_id


def get_or_create_job(conn, job_link: str) -> int:
    """Return the id of the job row, inserting if new."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM jobs WHERE job_link = %s", (job_link,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO jobs (job_link) VALUES (%s) RETURNING id",
            (job_link,),
        )
        job_id = cur.fetchone()[0]
    conn.commit()
    return job_id


def get_match(conn, resume_id: int, job_id: int) -> dict | None:
    """Return existing match dict or None if not yet matched."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM job_matches WHERE resume_id = %s AND job_id = %s",
            (resume_id, job_id),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def save_match(
    conn,
    resume_id: int,
    job_id: int,
    score: int,
    recommendation: str,
    additional_notes: str = "",
) -> int:
    """Insert a new job_match row and return its id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO job_matches (resume_id, job_id, score, recommendation, additional_notes)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (resume_id, job_id, score, recommendation, additional_notes),
        )
        match_id = cur.fetchone()[0]
    conn.commit()
    return match_id


def delete_jobs_by_source(conn, source: str) -> tuple[int, int]:
    """Delete all jobs (and their job_matches) whose job_link belongs to source.
    Returns (matches_deleted, jobs_deleted)."""
    pattern = f"%{source}.com%"
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM job_matches
            WHERE job_id IN (SELECT id FROM jobs WHERE job_link ILIKE %s)
            """,
            (pattern,),
        )
        matches_deleted = cur.rowcount
        cur.execute("DELETE FROM jobs WHERE job_link ILIKE %s", (pattern,))
        jobs_deleted = cur.rowcount
    conn.commit()
    return matches_deleted, jobs_deleted


def deactivate_jobs_by_links(conn, links: list[str]) -> tuple[int, int]:
    """Mark the jobs for the given links, and their job_matches, inactive
    (one transaction). Rows already inactive are left as they are.
    Returns (jobs_deactivated, matches_deactivated)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs SET is_active = 'no', deactivated_on = NOW()
            WHERE job_link = ANY(%s) AND is_active = 'yes'
            """,
            (links,),
        )
        jobs_deactivated = cur.rowcount
        cur.execute(
            """
            UPDATE job_matches SET is_active = 'no'
            WHERE is_active = 'yes'
              AND job_id IN (SELECT id FROM jobs WHERE job_link = ANY(%s))
            """,
            (links,),
        )
        matches_deactivated = cur.rowcount
    conn.commit()
    return jobs_deactivated, matches_deactivated


def is_job_active(conn, job_id: int) -> bool:
    """Return False if the job has been marked inactive (closed posting)."""
    with conn.cursor() as cur:
        cur.execute("SELECT is_active FROM jobs WHERE id = %s", (job_id,))
        row = cur.fetchone()
    return row is None or row[0] == "yes"


def mark_added_to_sheet(conn, match_id: int) -> None:
    """Set added_to_sheet = true for a job_match row."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE job_matches SET added_to_sheet = TRUE WHERE id = %s",
            (match_id,),
        )
    conn.commit()
