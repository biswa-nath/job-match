"""Baseline schema (resume, jobs, job_matches)

Idempotent so databases created by the old init_db() are adopted as-is.

Revision ID: 0001
Revises:
Create Date: 2026-11-21
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS resume (
            id          SERIAL PRIMARY KEY,
            signature   TEXT NOT NULL,
            added_on    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            text        TEXT NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_resume_signature ON resume (signature)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id          SERIAL PRIMARY KEY,
            job_link    TEXT NOT NULL,
            added_on    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_job_link ON jobs (job_link)")
    op.execute("""
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
    op.execute("""
        ALTER TABLE job_matches
        ADD COLUMN IF NOT EXISTS added_to_sheet BOOLEAN NOT NULL DEFAULT FALSE
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS job_matches")
    op.execute("DROP TABLE IF EXISTS jobs")
    op.execute("DROP TABLE IF EXISTS resume")
