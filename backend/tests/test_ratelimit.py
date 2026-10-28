"""Rate limiting: the primitives, and the endpoints that use them.

The primitive tests inject a clock rather than sleeping, so backoff growth up
to ten minutes is verified in microseconds.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app
from app.ratelimit.limiter import FailureTracker, SlidingWindowLimiter
from tests.conftest import TEST_PASSWORD, make_pdf, register


# --- primitives -------------------------------------------------------------


class TestSlidingWindow:
    def test_allows_up_to_the_limit_then_blocks(self) -> None:
        limiter = SlidingWindowLimiter(limit=3, window_seconds=60)

        assert [limiter.check("a", now=0.0).allowed for _ in range(3)] == [
            True,
            True,
            True,
        ]
        blocked = limiter.check("a", now=0.0)
        assert blocked.allowed is False
        assert blocked.retry_after > 0

    def test_keys_are_independent(self) -> None:
        limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
        assert limiter.check("a", now=0.0).allowed is True
        assert limiter.check("b", now=0.0).allowed is True
        assert limiter.check("a", now=0.0).allowed is False

    def test_window_slides(self) -> None:
        limiter = SlidingWindowLimiter(limit=2, window_seconds=10)
        limiter.check("a", now=0.0)
        limiter.check("a", now=1.0)
        assert limiter.check("a", now=5.0).allowed is False

        # The first event ages out at t=10, freeing one slot.
        assert limiter.check("a", now=10.5).allowed is True

    def test_blocked_attempts_do_not_extend_the_block(self) -> None:
        """A client that keeps hammering must not push its own unblock out."""
        limiter = SlidingWindowLimiter(limit=1, window_seconds=10)
        limiter.check("a", now=0.0)

        for moment in (1.0, 2.0, 3.0, 9.0):
            assert limiter.check("a", now=moment).allowed is False

        # Still unblocks based on the original event at t=0, not the last try.
        assert limiter.check("a", now=10.5).allowed is True

    def test_retry_after_counts_down(self) -> None:
        limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
        limiter.check("a", now=0.0)
        early = limiter.check("a", now=10.0).retry_after
        later = limiter.check("a", now=50.0).retry_after
        assert early > later >= 1

    def test_rejects_nonsense_configuration(self) -> None:
        with pytest.raises(ValueError):
            SlidingWindowLimiter(limit=0, window_seconds=60)


class TestFailureTracker:
    def _tracker(self) -> FailureTracker:
        return FailureTracker(threshold=3, base_seconds=10, max_seconds=600)

    def test_no_lock_below_the_threshold(self) -> None:
        tracker = self._tracker()
        assert tracker.record_failure("x", now=0.0) == 0
        assert tracker.record_failure("x", now=0.0) == 0
        assert tracker.locked_for("x", now=0.0) == 0

    def test_locks_at_the_threshold_and_backs_off(self) -> None:
        tracker = self._tracker()
        locks = [tracker.record_failure("x", now=0.0) for _ in range(5)]
        # 1st and 2nd are free; then 10, 20, 40 seconds.
        assert locks == [0, 0, 10, 20, 40]
        assert tracker.locked_for("x", now=0.0) > 0

    def test_backoff_is_capped(self) -> None:
        tracker = FailureTracker(threshold=1, base_seconds=10, max_seconds=100)
        locks = [tracker.record_failure("x", now=0.0) for _ in range(10)]
        assert max(locks) == 100, "backoff must not grow past max_seconds"

    def test_lock_expires(self) -> None:
        tracker = self._tracker()
        for _ in range(3):
            tracker.record_failure("x", now=0.0)
        assert tracker.locked_for("x", now=5.0) > 0
        assert tracker.locked_for("x", now=11.0) == 0

    def test_success_clears_the_record(self) -> None:
        tracker = self._tracker()
        for _ in range(4):
            tracker.record_failure("x", now=0.0)
        assert tracker.locked_for("x", now=0.0) > 0

        tracker.record_success("x")
        assert tracker.locked_for("x", now=0.0) == 0
        # And the counter restarted, so the next failure is free again.
        assert tracker.record_failure("x", now=0.0) == 0


# --- endpoints --------------------------------------------------------------


def _client(**overrides) -> Iterator[TestClient]:
    """A TestClient whose settings are overridden for one test."""
    app = create_app()
    settings = Settings(**overrides)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


class TestSignupLimit:
    def test_signup_is_capped_per_address(self) -> None:
        client = _client(signup_attempts_per_ip=3, signup_window_seconds=3600)

        for i in range(3):
            created = client.post(
                "/api/auth/signup",
                json={"email": f"rl{i}@example.com", "password": TEST_PASSWORD},
            )
            assert created.status_code == 201, created.text

        blocked = client.post(
            "/api/auth/signup",
            json={"email": "rl-over@example.com", "password": TEST_PASSWORD},
        )
        assert blocked.status_code == 429
        body = blocked.json()
        assert body["code"] == "rate_limited"
        assert body["retry_after_seconds"] > 0
        assert blocked.headers["retry-after"] == str(body["retry_after_seconds"])


class TestLoginLimit:
    def test_login_is_capped_per_address(self) -> None:
        client = _client(login_attempts_per_ip=4, login_window_seconds=300)

        # Spread across different emails: a per-IP cap must still bite, which
        # is what stops one host sweeping many accounts.
        for i in range(4):
            response = client.post(
                "/api/auth/login",
                json={"email": f"sweep{i}@example.com", "password": "guess-guess"},
            )
            assert response.status_code == 401

        blocked = client.post(
            "/api/auth/login",
            json={"email": "sweep99@example.com", "password": "guess-guess"},
        )
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"]


class TestAccountLockout:
    def test_account_locks_after_repeated_failures(self) -> None:
        client = _client(
            login_attempts_per_ip=100,
            lockout_threshold=3,
            lockout_base_seconds=30,
            lockout_max_seconds=600,
        )
        email = "locked@example.com"
        client.post(
            "/api/auth/signup", json={"email": email, "password": TEST_PASSWORD}
        )

        for _ in range(2):
            assert (
                client.post(
                    "/api/auth/login",
                    json={"email": email, "password": "wrong-password"},
                ).status_code
                == 401
            )

        third = client.post(
            "/api/auth/login", json={"email": email, "password": "wrong-password"}
        )
        assert third.status_code == 401

        # Now locked: even the CORRECT password is refused while the lock holds.
        locked = client.post(
            "/api/auth/login", json={"email": email, "password": TEST_PASSWORD}
        )
        assert locked.status_code == 429
        assert locked.json()["code"] == "account_locked"
        assert locked.json()["retry_after_seconds"] > 0

    def test_a_correct_password_clears_the_failure_count(self) -> None:
        client = _client(login_attempts_per_ip=100, lockout_threshold=3)
        email = "clears@example.com"
        client.post(
            "/api/auth/signup", json={"email": email, "password": TEST_PASSWORD}
        )

        for _ in range(2):
            client.post(
                "/api/auth/login", json={"email": email, "password": "wrong-password"}
            )

        ok = client.post(
            "/api/auth/login", json={"email": email, "password": TEST_PASSWORD}
        )
        assert ok.status_code == 200

        # Counter reset, so two more failures still do not lock.
        for _ in range(2):
            assert (
                client.post(
                    "/api/auth/login",
                    json={"email": email, "password": "wrong-password"},
                ).status_code
                == 401
            )

    def test_unknown_emails_lock_out_identically(self) -> None:
        """Otherwise lockout behaviour itself reveals which accounts exist."""
        client = _client(login_attempts_per_ip=100, lockout_threshold=3)

        for _ in range(3):
            client.post(
                "/api/auth/login",
                json={"email": "ghost@example.com", "password": "wrong-password"},
            )

        response = client.post(
            "/api/auth/login",
            json={"email": "ghost@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 429
        assert response.json()["code"] == "account_locked"


class TestUploadLimit:
    def test_analyses_are_capped_per_account(self, sample_pdf: bytes) -> None:
        client = _client(upload_per_user=2, upload_window_seconds=3600)
        register(client, "uploader@example.com")

        for _ in range(2):
            created = client.post(
                "/api/analyses",
                files={"file": ("r.pdf", sample_pdf, "application/pdf")},
            )
            assert created.status_code == 201

        blocked = client.post(
            "/api/analyses",
            files={"file": ("r.pdf", sample_pdf, "application/pdf")},
        )
        assert blocked.status_code == 429
        assert blocked.json()["code"] == "rate_limited"


class TestProxyHeaders:
    def test_forwarded_header_is_ignored_by_default(self) -> None:
        """Honouring it unconditionally would make every per-IP limit useless.

        Any client can set X-Forwarded-For, so a spoofed value per request
        would give an attacker a fresh identity each time.
        """
        client = _client(signup_attempts_per_ip=2, signup_window_seconds=3600)

        for i in range(2):
            client.post(
                "/api/auth/signup",
                json={"email": f"px{i}@example.com", "password": TEST_PASSWORD},
                headers={"X-Forwarded-For": f"10.0.0.{i}"},
            )

        blocked = client.post(
            "/api/auth/signup",
            json={"email": "px-spoof@example.com", "password": TEST_PASSWORD},
            headers={"X-Forwarded-For": "10.0.0.99"},
        )
        assert blocked.status_code == 429, "a spoofed address must not reset the limit"

    def test_forwarded_header_is_used_when_explicitly_trusted(self) -> None:
        client = _client(
            signup_attempts_per_ip=1,
            signup_window_seconds=3600,
            trust_proxy_headers=True,
        )

        first = client.post(
            "/api/auth/signup",
            json={"email": "tp1@example.com", "password": TEST_PASSWORD},
            headers={"X-Forwarded-For": "203.0.113.1"},
        )
        assert first.status_code == 201

        # A genuinely different client behind the same proxy is not punished.
        second = client.post(
            "/api/auth/signup",
            json={"email": "tp2@example.com", "password": TEST_PASSWORD},
            headers={"X-Forwarded-For": "203.0.113.2"},
        )
        assert second.status_code == 201

        # The same client is.
        third = client.post(
            "/api/auth/signup",
            json={"email": "tp3@example.com", "password": TEST_PASSWORD},
            headers={"X-Forwarded-For": "203.0.113.1"},
        )
        assert third.status_code == 429


class TestDisabled:
    def test_limits_can_be_turned_off(self) -> None:
        client = _client(rate_limit_enabled=False, signup_attempts_per_ip=1)
        for i in range(4):
            response = client.post(
                "/api/auth/signup",
                json={"email": f"off{i}@example.com", "password": TEST_PASSWORD},
            )
            assert response.status_code == 201
