"""A SECRET_KEY too short to sign sessions with stops the app from starting.

This exists because of a warning that was being produced and ignored. Running
the backend in a container surfaced:

    InsecureKeyLengthWarning: The HMAC key is 22 bytes long, which is below
    the minimum recommended length of 32 bytes for SHA256

PyJWT emits that and then signs anyway. The key length is the whole strength
of the session cookie -- forging the signature forges the session -- so a
guessable key means anyone can mint a session for any account. Every
placeholder key in this repository was between 9 and 22 bytes when this was
written, including the ones in CI and docker-compose, so nothing would have
caught a deployment that set a short one.

A warning is the wrong response to a configuration error that cannot be
recovered from at runtime. Refusing to start is the right one, and it happens
where someone is still watching the deploy.
"""

from __future__ import annotations

import secrets

import pytest
from fastapi.testclient import TestClient

from app.auth.security import (
    MIN_SECRET_KEY_BYTES,
    WeakSigningKey,
    verify_signing_key,
)
from app.config import Settings
from app.main import create_app


class TestVerifySigningKey:
    def test_a_short_key_is_refused(self) -> None:
        """The exact case the container log showed: 22 bytes."""
        with pytest.raises(WeakSigningKey) as excinfo:
            verify_signing_key(Settings(secret_key="ci-only-not-a-real-key"))

        message = str(excinfo.value)
        assert "22 bytes" in message, "the message should name the actual length"
        assert "token_urlsafe" in message, "and say how to generate a good one"

    def test_a_key_one_byte_short_is_refused(self) -> None:
        """An off-by-one here would let almost-short keys through."""
        with pytest.raises(WeakSigningKey):
            verify_signing_key(Settings(secret_key="k" * (MIN_SECRET_KEY_BYTES - 1)))

    def test_a_key_of_exactly_the_minimum_is_accepted(self) -> None:
        verify_signing_key(Settings(secret_key="k" * MIN_SECRET_KEY_BYTES))

    def test_the_documented_generator_produces_an_acceptable_key(self) -> None:
        """DEPLOYMENT.md tells the reader to use this; it must pass."""
        verify_signing_key(Settings(secret_key=secrets.token_urlsafe(48)))

    def test_an_unset_key_is_not_an_error(self) -> None:
        """Development generates and persists a strong key instead."""
        verify_signing_key(Settings(secret_key=""))

    def test_length_is_counted_in_bytes_not_characters(self) -> None:
        """A 31-character key of multi-byte characters is long enough in bytes.

        Counting characters would reject it; HS256 cares about the byte
        length of the key, which is what RFC 7518 specifies.
        """
        key = "é" * 31  # 31 characters, 62 bytes in UTF-8
        assert len(key) < MIN_SECRET_KEY_BYTES
        verify_signing_key(Settings(secret_key=key))


class TestStartup:
    def test_the_app_refuses_to_start_with_a_short_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The check has to be wired into startup, not merely defined."""
        monkeypatch.setenv("SECRET_KEY", "too-short")

        from app.config import get_settings

        get_settings.cache_clear()
        try:
            with pytest.raises(WeakSigningKey):
                with TestClient(create_app()):
                    pass
        finally:
            get_settings.cache_clear()

    def test_the_app_starts_with_the_suite_configuration(
        self, client: TestClient
    ) -> None:
        """Guards against the check rejecting a legitimate key."""
        assert client.get("/api/health").status_code == 200
