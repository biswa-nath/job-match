from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

from db.database import get_connection

_LOCK = 7_302_018  # arbitrary app-specific advisory-lock key

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

if context.is_offline_mode():
    raise RuntimeError("Offline (--sql) migrations are not supported.")

# Reuse the psycopg2 connection helper so DATABASE_URL (any psycopg2 DSN form)
# stays configured in one place.
engine = create_engine(
    "postgresql+psycopg2://", creator=get_connection, poolclass=pool.NullPool
)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        # Serialise concurrent runs (e.g. a local run during a scheduled Lambda):
        # the second waits here, then finds the schema already at head. The
        # timeout stops a start-up hanging behind a long transaction that holds
        # a table lock; both settings end with the transaction.
        connection.execute(text("SET LOCAL lock_timeout = '30s'"))
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _LOCK})
        context.run_migrations()
