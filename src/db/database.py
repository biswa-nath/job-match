import hashlib

import psycopg2
import psycopg2.extras

import config


def get_connection():
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in your .env file.")
    return psycopg2.connect(config.DATABASE_URL)


def init_db(conn) -> None:
    """Create tables if they don't already exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS resume (
                id          SERIAL PRIMARY KEY,
                signature   TEXT NOT NULL,
                added_on    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                text        TEXT NOT NULL
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_resume_signature ON resume (signature)"
        )

        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          SERIAL PRIMARY KEY,
                job_link    TEXT NOT NULL,
                added_on    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_job_link ON jobs (job_link)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS job_matches (
                id               SERIAL PRIMARY KEY,
                resume_id        INTEGER NOT NULL REFERENCES resume (id),
                job_id           INTEGER NOT NULL REFERENCES jobs (id),
                score            INTEGER NOT NULL,
                recommendation   TEXT NOT NULL,
                additional_notes TEXT NOT NULL DEFAULT '',
                added_to_sheet   BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)
        # Migration: add added_to_sheet if table already exists without it
        cur.execute("""
            ALTER TABLE job_matches
            ADD COLUMN IF NOT EXISTS added_to_sheet BOOLEAN NOT NULL DEFAULT FALSE
        """)
    conn.commit()


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


def mark_added_to_sheet(conn, match_id: int) -> None:
    """Set added_to_sheet = true for a job_match row."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE job_matches SET added_to_sheet = TRUE WHERE id = %s",
            (match_id,),
        )
    conn.commit()
