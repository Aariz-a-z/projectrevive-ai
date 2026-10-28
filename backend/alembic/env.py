"""Alembic environment.

The database URL comes from the application's own settings rather than from
alembic.ini. Two copies of a connection string drift, and the one that drifts
is always the one that runs against production.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importing the models is what populates this; it is the source of truth that
# autogenerate compares the live database against.
target_metadata = Base.metadata

def _resolve_url() -> str:
    """A URL supplied by the caller wins over the application settings.

    Programmatic callers -- the startup check, and the tests that migrate a
    throwaway database -- set the URL on the Config they pass in. Overwriting
    it here unconditionally would silently redirect those migrations at
    whatever DATABASE_URL happens to be in the environment.
    """
    supplied = config.get_main_option("sqlalchemy.url", None)
    if supplied:
        return supplied
    return get_settings().database_url


DATABASE_URL = _resolve_url()
config.set_main_option("sqlalchemy.url", DATABASE_URL)


# Shared options. `render_as_batch` matters on SQLite, which cannot ALTER a
# column: Alembic has to copy the table, and batch mode is what generates
# that. `compare_type` makes autogenerate notice a changed column type, which
# it ignores by default.
COMMON = dict(
    target_metadata=target_metadata,
    compare_type=True,
    compare_server_default=True,
)


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=DATABASE_URL.startswith("sqlite"),
        **COMMON,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            render_as_batch=connection.dialect.name == "sqlite",
            **COMMON,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
