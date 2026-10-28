"""Migrations: drift against the models, and that they actually run.

The failure this guards against is quiet. Someone adds a column to
`app/db/models.py`, tests pass because the test database is built with
`create_all`, and the omission only surfaces when a real deployment runs
`alembic upgrade head` and gets a schema without the column.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.config import Settings
from app.db.migrate import (
    SchemaOutOfDate,
    current_revision,
    ensure_schema,
    head_revision,
    upgrade_to_head,
)
from app.db.models import NAMING_CONVENTION, Base


@pytest.fixture
def fresh_db():
    """An empty SQLite file, with its URL. Removed afterwards."""
    path = Path(tempfile.mkdtemp()) / "migrate_test.db"
    url = f"sqlite:///{path.as_posix()}"
    engine = create_engine(url)
    try:
        yield engine, url
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)


class TestNoDrift:
    def test_migrations_produce_exactly_what_the_models_describe(
        self, fresh_db
    ) -> None:
        """Autogenerate against a migrated database must find nothing to do."""
        engine, url = fresh_db
        upgrade_to_head(url)

        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={"compare_type": True, "compare_server_default": True},
            )
            diff = compare_metadata(context, Base.metadata)

        assert diff == [], (
            "the models and the migrations disagree. Generate a migration "
            f"with: alembic revision --autogenerate. Differences: {diff}"
        )

    def test_migrated_schema_matches_create_all(self, fresh_db) -> None:
        """Tests build with create_all; the app migrates. They must agree."""
        engine, url = fresh_db
        upgrade_to_head(url)
        migrated = inspect(engine)

        other_path = Path(tempfile.mkdtemp()) / "created.db"
        created_engine = create_engine(f"sqlite:///{other_path.as_posix()}")
        try:
            Base.metadata.create_all(created_engine)
            created = inspect(created_engine)

            assert set(migrated.get_table_names()) - {"alembic_version"} == set(
                created.get_table_names()
            )
            for table in created.get_table_names():
                migrated_cols = {c["name"] for c in migrated.get_columns(table)}
                created_cols = {c["name"] for c in created.get_columns(table)}
                assert migrated_cols == created_cols, table
        finally:
            created_engine.dispose()
            other_path.unlink(missing_ok=True)


class TestMigrationsRun:
    def test_upgrade_creates_the_expected_tables(self, fresh_db) -> None:
        engine, url = fresh_db
        upgrade_to_head(url)

        tables = set(inspect(engine).get_table_names())
        assert {"users", "analyses", "alembic_version"} <= tables

    def test_upgrade_records_the_head_revision(self, fresh_db) -> None:
        engine, url = fresh_db
        upgrade_to_head(url)
        assert current_revision(engine) == head_revision()

    def test_an_empty_database_reports_no_revision(self, fresh_db) -> None:
        engine, _ = fresh_db
        assert current_revision(engine) is None

    def test_upgrade_is_idempotent(self, fresh_db) -> None:
        _, url = fresh_db
        upgrade_to_head(url)
        upgrade_to_head(url)  # must not raise

    def test_constraints_are_named_by_the_convention(self, fresh_db) -> None:
        """Unnamed constraints cannot be altered or dropped by a migration."""
        engine, url = fresh_db
        upgrade_to_head(url)
        inspector = inspect(engine)

        foreign_keys = inspector.get_foreign_keys("analyses")
        assert foreign_keys
        assert all(fk["name"] for fk in foreign_keys)
        assert any("fk_analyses_user_id_users" == fk["name"] for fk in foreign_keys)

        indexes = inspector.get_indexes("users")
        assert any(ix["name"] == "ix_users_email" for ix in indexes)

    def test_the_naming_convention_is_attached_to_the_metadata(self) -> None:
        assert Base.metadata.naming_convention == NAMING_CONVENTION


class TestEnsureSchema:
    def test_migrates_an_empty_database_when_auto_migrate_is_on(
        self, fresh_db
    ) -> None:
        engine, url = fresh_db
        ensure_schema(engine, Settings(database_url=url, auto_migrate=True))
        assert current_revision(engine) == head_revision()

    def test_refuses_to_start_on_an_old_schema_when_auto_migrate_is_off(
        self, fresh_db
    ) -> None:
        """Serving against an unexpected schema is worse than not starting."""
        engine, url = fresh_db
        settings = Settings(database_url=url, auto_migrate=False)

        with pytest.raises(SchemaOutOfDate) as exc:
            ensure_schema(engine, settings)

        assert "alembic upgrade head" in str(exc.value)

    def test_accepts_an_up_to_date_database_when_auto_migrate_is_off(
        self, fresh_db
    ) -> None:
        engine, url = fresh_db
        upgrade_to_head(url)
        ensure_schema(engine, Settings(database_url=url, auto_migrate=False))
