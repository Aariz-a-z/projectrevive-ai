"""Timestamps survive a database round trip with their time zone intact.

This exists because of a bug that was visible in the dashboard for several
days and went unquestioned. A freshly created object serialised as
`...04:50:48Z`; the same row read back serialised as `...04:50:48`, with no
offset, because the column could not carry one. Browsers parse an offsetless
string as *local* time, so every stored timestamp displayed several hours
adrift — here, five and a half.

Nothing failed. No test asserted it, no exception was raised, and the only
symptom was a plausible-looking wrong number.

On PostgreSQL the same defect is worse than cosmetic: `timestamp without time
zone` discards the offset using the session's zone, so a managed database
outside UTC would shift every historical value silently.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import StatementError

from app.db.models import User
from app.db.session import SessionLocal
from app.db.types import UtcDateTime
from tests.conftest import make_pdf


class TestColumnType:
    def test_a_round_trip_returns_an_aware_datetime(self) -> None:
        """The actual defect: what goes in aware must come back aware."""
        db = SessionLocal()
        try:
            user = User(
                id="tz" + "0" * 30,
                email="roundtrip@example.com",
                password_hash="x",
                created_at=datetime(2026, 3, 1, 12, 30, tzinfo=timezone.utc),
            )
            db.add(user)
            db.commit()
            db.expunge_all()

            loaded = db.get(User, user.id)
            assert loaded is not None
            assert loaded.created_at.tzinfo is not None, (
                "a naive datetime here is what made the dashboard show the "
                "wrong time"
            )
            assert loaded.created_at == datetime(
                2026, 3, 1, 12, 30, tzinfo=timezone.utc
            )
        finally:
            db.query(User).filter(User.email == "roundtrip@example.com").delete()
            db.commit()
            db.close()

    def test_a_non_utc_input_is_stored_as_the_same_instant(self) -> None:
        """Storing must normalise, not truncate the offset away."""
        db = SessionLocal()
        tokyo = timezone(timedelta(hours=9))
        try:
            user = User(
                id="tz" + "1" * 30,
                email="tokyo@example.com",
                password_hash="x",
                created_at=datetime(2026, 3, 1, 21, 30, tzinfo=tokyo),
            )
            db.add(user)
            db.commit()
            db.expunge_all()

            loaded = db.get(User, user.id)
            assert loaded is not None
            # 21:30 in Tokyo is 12:30 UTC. The instant must be preserved.
            assert loaded.created_at == datetime(
                2026, 3, 1, 12, 30, tzinfo=timezone.utc
            )
            assert loaded.created_at.utcoffset() == timedelta(0)
        finally:
            db.query(User).filter(User.email == "tokyo@example.com").delete()
            db.commit()
            db.close()

    def test_a_naive_datetime_is_refused_rather_than_guessed_at(self) -> None:
        """Assuming UTC would silently mislabel a local time."""
        db = SessionLocal()
        try:
            db.add(
                User(
                    id="tz" + "2" * 30,
                    email="naive@example.com",
                    password_hash="x",
                    created_at=datetime(2026, 3, 1, 12, 30),
                )
            )
            with pytest.raises((ValueError, StatementError)):
                db.commit()
        finally:
            db.rollback()
            db.close()

    def test_the_type_declares_itself_timezone_aware(self) -> None:
        assert UtcDateTime.impl.timezone is True


class TestApiSerialisation:
    def test_a_created_object_carries_an_offset(
        self, auth_client: TestClient
    ) -> None:
        body = auth_client.get("/api/auth/me").json()
        assert body["created_at"].endswith("Z") or "+" in body["created_at"][10:]

    def test_a_stored_analysis_carries_an_offset_too(
        self, auth_client: TestClient
    ) -> None:
        """The path that was broken: a value loaded back out of the database."""
        created = auth_client.post(
            "/api/analyses",
            files={"file": ("r.pdf", make_pdf(["T", "CNN. " * 40]), "application/pdf")},
        ).json()

        fetched = auth_client.get(f"/api/analyses/{created['id']}").json()
        stamp = fetched["created_at"]

        assert stamp.endswith("Z") or "+" in stamp[10:], (
            f"{stamp!r} has no time zone; a browser would read it as local time"
        )

    def test_the_same_row_serialises_identically_however_it_was_obtained(
        self, auth_client: TestClient
    ) -> None:
        """Fresh and reloaded disagreed before, which is why it went unnoticed."""
        created = auth_client.post(
            "/api/analyses",
            files={"file": ("r.pdf", make_pdf(["T", "CNN. " * 40]), "application/pdf")},
        ).json()
        fetched = auth_client.get(f"/api/analyses/{created['id']}").json()

        assert created["created_at"] == fetched["created_at"]

    def test_the_timestamp_is_recent_in_real_terms(
        self, auth_client: TestClient
    ) -> None:
        """Catches an offset error that leaves the string well-formed."""
        body = auth_client.get("/api/auth/me").json()
        parsed = datetime.fromisoformat(body["created_at"].replace("Z", "+00:00"))

        drift = abs((datetime.now(timezone.utc) - parsed).total_seconds())
        assert drift < 300, (
            f"timestamp is {drift / 3600:.1f} hours from now, which is the "
            "shape of a time-zone bug rather than a slow test"
        )
