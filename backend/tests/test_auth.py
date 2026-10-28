"""Signup, login, sessions, and per-account isolation of analyses."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD, make_pdf, register

STRONG = TEST_PASSWORD


class TestSignup:
    def test_creates_an_account_and_signs_in(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/signup", json={"email": "New@Example.com", "password": STRONG}
        )
        assert response.status_code == 201, response.text

        body = response.json()
        assert body["email"] == "new@example.com", "email should be normalised"
        assert "password" not in body and "password_hash" not in body

        # The session cookie is set and immediately usable.
        assert client.get("/api/auth/me").json()["email"] == "new@example.com"

    def test_session_cookie_is_httponly(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/signup", json={"email": "c@example.com", "password": STRONG}
        )
        cookie_header = response.headers["set-cookie"].lower()
        assert "httponly" in cookie_header
        assert "samesite=lax" in cookie_header

    def test_rejects_a_duplicate_email_regardless_of_case(
        self, client: TestClient
    ) -> None:
        client.post(
            "/api/auth/signup", json={"email": "dup@example.com", "password": STRONG}
        )
        again = client.post(
            "/api/auth/signup", json={"email": "DUP@example.com", "password": STRONG}
        )
        assert again.status_code == 409
        assert again.json()["code"] == "email_already_registered"

    def test_rejects_an_invalid_email(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/signup", json={"email": "not-an-email", "password": STRONG}
        )
        assert response.status_code == 422


class TestPasswordPolicy:
    def test_rejects_a_short_password(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/signup", json={"email": "s@example.com", "password": "short1"}
        )
        assert response.status_code == 422
        assert response.json()["code"] == "weak_password"

    def test_rejects_a_common_password(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/signup",
            json={"email": "s2@example.com", "password": "password123"},
        )
        assert response.json()["code"] == "weak_password"
        assert "commonly used" in response.json()["message"]

    def test_rejects_an_all_digit_password(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/signup",
            json={"email": "s3@example.com", "password": "90210847163"},
        )
        assert response.json()["code"] == "weak_password"

    def test_rejects_a_password_containing_the_email(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/auth/signup",
            json={"email": "jonathan@example.com", "password": "jonathan-2026!"},
        )
        assert response.json()["code"] == "weak_password"
        assert "email address" in response.json()["message"]

    def test_accepts_a_long_passphrase_without_symbols(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/auth/signup",
            json={"email": "phrase@example.com", "password": "mountain river glass"},
        )
        assert response.status_code == 201


class TestLogin:
    def test_signs_in_with_correct_credentials(self, client: TestClient) -> None:
        email = register(client)
        client.post("/api/auth/logout")

        response = client.post(
            "/api/auth/login", json={"email": email, "password": STRONG}
        )
        assert response.status_code == 200
        assert client.get("/api/auth/me").json()["email"] == email

    def test_rejects_a_wrong_password(self, client: TestClient) -> None:
        email = register(client)
        response = client.post(
            "/api/auth/login", json={"email": email, "password": "wrong-password-xyz"}
        )
        assert response.status_code == 401
        assert response.json()["code"] == "invalid_credentials"

    def test_unknown_email_is_indistinguishable_from_a_wrong_password(
        self, client: TestClient
    ) -> None:
        """Different responses here would let anyone enumerate accounts."""
        email = register(client)
        wrong_password = client.post(
            "/api/auth/login", json={"email": email, "password": "wrong-password-xyz"}
        )
        unknown_email = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "wrong-password-xyz"},
        )
        assert wrong_password.status_code == unknown_email.status_code
        assert wrong_password.json() == unknown_email.json()


class TestSession:
    def test_me_requires_a_session(self, client: TestClient) -> None:
        response = client.get("/api/auth/me")
        assert response.status_code == 401
        assert response.json()["code"] == "not_authenticated"

    def test_logout_ends_the_session(self, auth_client: TestClient) -> None:
        assert auth_client.get("/api/auth/me").status_code == 200
        assert auth_client.post("/api/auth/logout").status_code == 204
        assert auth_client.get("/api/auth/me").status_code == 401

    def test_a_tampered_token_is_rejected(self, auth_client: TestClient) -> None:
        # Clear first: otherwise the real cookie from signup is still sent
        # alongside the bad one and the request succeeds for the wrong reason.
        auth_client.cookies.clear()
        auth_client.cookies.set("pr_session", "not.a.real.jwt")

        response = auth_client.get("/api/auth/me")
        assert response.status_code == 401
        assert response.json()["code"] == "invalid_session"

    def test_a_token_signed_with_the_wrong_key_is_rejected(
        self, auth_client: TestClient
    ) -> None:
        """A forged token must not authenticate, even with a valid `sub`."""
        import jwt

        real_id = auth_client.get("/api/auth/me").json()["id"]
        forged = jwt.encode(
            {"sub": real_id}, "attacker-key-that-is-long-enough-32b", algorithm="HS256"
        )

        auth_client.cookies.clear()
        auth_client.cookies.set("pr_session", forged)

        response = auth_client.get("/api/auth/me")
        assert response.status_code == 401
        assert response.json()["code"] == "invalid_session"

    def test_an_expired_token_is_rejected(self, auth_client: TestClient) -> None:
        import jwt

        from app.config import get_settings
        from app.auth.security import resolve_secret_key

        real_id = auth_client.get("/api/auth/me").json()["id"]
        expired = jwt.encode(
            {"sub": real_id, "exp": 1_000_000_000},
            resolve_secret_key(get_settings()),
            algorithm="HS256",
        )

        auth_client.cookies.clear()
        auth_client.cookies.set("pr_session", expired)

        response = auth_client.get("/api/auth/me")
        assert response.status_code == 401
        assert "expired" in response.json()["message"].lower()


class TestAnalysisOwnership:
    def test_upload_requires_a_session(self, client: TestClient) -> None:
        response = client.post(
            "/api/analyses",
            files={"file": ("r.pdf", make_pdf(["x" * 200]), "application/pdf")},
        )
        assert response.status_code == 401

    def test_listing_requires_a_session(self, client: TestClient) -> None:
        assert client.get("/api/analyses").status_code == 401

    def test_one_account_cannot_read_anothers_analysis(
        self, client: TestClient, sample_pdf: bytes
    ) -> None:
        register(client, "owner@example.com")
        created = client.post(
            "/api/analyses",
            files={"file": ("r.pdf", sample_pdf, "application/pdf")},
        ).json()

        client.post("/api/auth/logout")
        register(client, "intruder@example.com")

        # Reported as missing, not forbidden, so ids cannot be probed.
        assert client.get(f"/api/analyses/{created['id']}").status_code == 404
        assert client.get("/api/analyses").json() == []

    def test_one_account_cannot_delete_anothers_analysis(
        self, client: TestClient, sample_pdf: bytes
    ) -> None:
        register(client, "owner2@example.com")
        created = client.post(
            "/api/analyses",
            files={"file": ("r.pdf", sample_pdf, "application/pdf")},
        ).json()

        client.post("/api/auth/logout")
        register(client, "intruder2@example.com")
        assert client.delete(f"/api/analyses/{created['id']}").status_code == 404

        # Still there for its owner.
        client.post("/api/auth/logout")
        client.post(
            "/api/auth/login",
            json={"email": "owner2@example.com", "password": STRONG},
        )
        assert client.get(f"/api/analyses/{created['id']}").status_code == 200

    def test_owner_can_delete_their_own_analysis(
        self, auth_client: TestClient, sample_pdf: bytes
    ) -> None:
        created = auth_client.post(
            "/api/analyses",
            files={"file": ("r.pdf", sample_pdf, "application/pdf")},
        ).json()
        assert auth_client.delete(f"/api/analyses/{created['id']}").status_code == 204
        assert auth_client.get(f"/api/analyses/{created['id']}").status_code == 404
