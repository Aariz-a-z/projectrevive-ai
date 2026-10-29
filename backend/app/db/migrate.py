"""Applying and verifying schema migrations.

`create_all` is gone from the application path. It produces whatever the
models currently say and silently diverges from what migrations would have
built, so a database created by one and then migrated by the other ends up in
a state no migration describes. It is kept only for tests, where the database
is thrown away after every run.

Startup behaviour depends on `auto_migrate`:

- **True** (the default, suits development and a single-instance deployment):
  bring the database to head automatically.
- **False**: verify it is already at head and refuse to start otherwise. That
  is the right setting wherever several instances start at once, since
  concurrent migrations race, and where applying schema changes should be a
  deliberate deploy step rather than a side effect of a process restarting.

Either way the process never serves requests against a schema it did not
expect, which is the failure this module exists to prevent.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

from app.config import Settings

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


class SchemaOutOfDate(RuntimeError):
    """The database is not at the revision this code expects."""


def alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)
    return config


@lru_cache(maxsize=1)
def head_revision() -> str | None:
    """The newest revision on disk.

    Cached: resolving it parses alembic.ini and every file under versions/,
    and `ensure_schema` runs on each application startup -- which in the test
    suite means once per TestClient, hundreds of times. The migration scripts
    cannot change within a process, so re-reading them is pure cost.
    """
    script = ScriptDirectory.from_config(alembic_config())
    return script.get_current_head()


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def upgrade_to_head(database_url: str | None = None) -> None:
    command.upgrade(alembic_config(database_url), "head")


def downgrade_to_base(database_url: str | None = None) -> None:
    """Tear the schema back down. Tests only; never call this on real data."""
    command.downgrade(alembic_config(database_url), "base")


def ensure_schema(engine: Engine, settings: Settings) -> None:
    """Make the database match this code, or refuse to continue."""
    head = head_revision()
    current = current_revision(engine)

    if current == head:
        logger.info("database schema is at head (%s)", head)
        return

    if settings.auto_migrate:
        logger.info(
            "migrating database from %s to %s", current or "empty", head
        )
        upgrade_to_head(settings.database_url)
        return

    raise SchemaOutOfDate(
        f"The database is at revision {current or 'none'} but this code "
        f"expects {head}. AUTO_MIGRATE is off, so run migrations as a deploy "
        "step:\n\n    alembic upgrade head\n\n"
        "Refusing to start rather than serve requests against an unexpected "
        "schema."
    )
