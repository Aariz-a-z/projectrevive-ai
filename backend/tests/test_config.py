"""Settings handling, including the deployment papercuts."""

from __future__ import annotations

import pytest

from app.config import Settings


class TestDatabaseUrl:
    def test_accepts_the_postgres_scheme_providers_hand_out(self) -> None:
        """Heroku, Railway and others issue postgres://; SQLAlchemy 2 rejects it."""
        settings = Settings(database_url="postgres://u:p@host:5432/db")
        assert settings.database_url == "postgresql://u:p@host:5432/db"

    def test_leaves_the_canonical_scheme_alone(self) -> None:
        url = "postgresql://u:p@host:5432/db"
        assert Settings(database_url=url).database_url == url

    def test_leaves_sqlite_alone(self) -> None:
        url = "sqlite:///./projectrevive.db"
        assert Settings(database_url=url).database_url == url

    def test_does_not_rewrite_a_password_containing_the_scheme(self) -> None:
        """Only a leading scheme is rewritten, not the string anywhere."""
        url = "postgresql://user:postgres://weird@host:5432/db"
        assert Settings(database_url=url).database_url == url


class TestDeclaredDefaults:
    """Asserts the declared defaults, not an instantiated Settings.

    The test suite sets SECRET_KEY, LLM_PROVIDER and DATABASE_URL in the
    environment, so `Settings()` reflects the suite rather than the shipped
    defaults. Reading the field definitions is what actually checks what a
    fresh deployment would get.
    """

    def _default(self, name: str):
        return Settings.model_fields[name].default

    def test_secure_cookies_are_off_by_default(self) -> None:
        """Development is HTTP; a Secure cookie would never be sent."""
        assert self._default("cookie_secure") is False

    def test_proxy_headers_are_distrusted_by_default(self) -> None:
        """Trusting them without a proxy lets any client forge its address."""
        assert self._default("trust_proxy_headers") is False

    def test_no_secret_key_is_baked_in(self) -> None:
        """A default would sit in the public repository and be forgeable."""
        assert self._default("secret_key") == ""

    def test_the_default_provider_spends_nothing(self) -> None:
        assert self._default("llm_provider") == "mock"

    def test_rate_limiting_is_on_by_default(self) -> None:
        assert self._default("rate_limit_enabled") is True


class TestProductionSettings:

    @pytest.mark.parametrize("value", ["low", "medium", "high", "xhigh", "max"])
    def test_effort_levels_are_accepted(self, value: str) -> None:
        assert Settings(analysis_effort=value).analysis_effort == value

    def test_an_unknown_effort_level_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            Settings(analysis_effort="turbo")
