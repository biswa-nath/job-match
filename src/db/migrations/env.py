from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from db.database import get_connection

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
        context.run_migrations()
