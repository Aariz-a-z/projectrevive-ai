"""Engine and session wiring.

SQLite locally, Postgres in production, same code. Phase 0 creates tables
directly; Alembic takes over in Phase 1 so schema changes are migrations rather
than create_all side effects.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base

_settings = get_settings()

_connect_args = (
    {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(_settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables directly from the models. **Tests only.**

    This bypasses migrations, so a database built this way can differ from
    one built by `alembic upgrade head` without anything noticing. That is
    acceptable for a test database that is deleted afterwards, and is why
    tests/test_migrations.py asserts the two produce the same schema.

    The application uses `app.db.migrate.ensure_schema` instead.
    """
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
