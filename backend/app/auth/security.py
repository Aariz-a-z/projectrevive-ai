"""Password hashing and session tokens.

Argon2id is used rather than bcrypt: it is the current password-hashing
recommendation and has no silent 72-byte truncation, so a long passphrase is
hashed in full instead of being quietly cut short.

The session token is a JWT carried in an httpOnly cookie. httpOnly means page
JavaScript cannot read it, so a cross-site scripting bug cannot exfiltrate a
session the way it could from localStorage.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import Settings
from app.errors import InvalidSession

logger = logging.getLogger(__name__)

_hasher = PasswordHasher()
ALGORITHM = "HS256"

# RFC 7518 section 3.2: an HMAC-SHA256 key must be at least as long as the
# hash output. A shorter one is the weakest link in the session cookie,
# because forging the signature forges the session.
MIN_SECRET_KEY_BYTES = 32

# Dev-only key file. Never committed; see .gitignore.
_DEV_KEY_PATH = Path(__file__).resolve().parents[2] / ".secret_key"
_warned = False


def resolve_secret_key(settings: Settings) -> str:
    """Return the signing key, generating a persisted dev key if unset.

    A hardcoded fallback secret would be worse than useless -- it would be in
    the public repository, so anyone could forge a session. Instead an unset
    key produces a random one, stored outside version control.
    """
    global _warned

    if settings.secret_key:
        return settings.secret_key

    if not _warned:
        logger.warning(
            "SECRET_KEY is not set. Using a generated development key stored "
            "at %s. Set SECRET_KEY explicitly before deploying.",
            _DEV_KEY_PATH,
        )
        _warned = True

    if _DEV_KEY_PATH.exists():
        existing = _DEV_KEY_PATH.read_text(encoding="utf-8").strip()
        if existing:
            return existing

    generated = secrets.token_urlsafe(48)
    _DEV_KEY_PATH.write_text(generated, encoding="utf-8")
    return generated


class WeakSigningKey(RuntimeError):
    """An explicitly configured SECRET_KEY too short to sign sessions with."""


def verify_signing_key(settings: Settings) -> None:
    """Refuse to start when SECRET_KEY is too short for HS256.

    PyJWT only emits `InsecureKeyLengthWarning` for this, which is one line in
    a boot log among many and was in fact missed here until a container run
    surfaced it. The consequence is not cosmetic: the key length is the entire
    strength of the session cookie, so a guessable key lets anyone mint a
    session for any account.

    Checked at startup rather than on the first login, so a misconfigured
    deployment fails while someone is still watching it, in the same spirit as
    the schema check above it.

    An unset key is not an error -- `resolve_secret_key` generates a strong
    one and persists it for development.
    """
    key = settings.secret_key
    if not key:
        return

    length = len(key.encode("utf-8"))
    if length < MIN_SECRET_KEY_BYTES:
        raise WeakSigningKey(
            f"SECRET_KEY is {length} bytes; HS256 needs at least "
            f"{MIN_SECRET_KEY_BYTES}. Generate one with: "
            'python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    """Constant-time-ish verification that never raises for a wrong password."""
    try:
        _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return True


def needs_rehash(stored_hash: str) -> bool:
    """True when Argon2 parameters have moved on since this hash was made."""
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return False


def create_access_token(user_id: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, resolve_secret_key(settings), algorithm=ALGORITHM)


def read_access_token(token: str, settings: Settings) -> str:
    """Return the user id in a valid token, or raise InvalidSession."""
    try:
        payload = jwt.decode(
            token, resolve_secret_key(settings), algorithms=[ALGORITHM]
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidSession("Your session has expired. Sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidSession() from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidSession()
    return subject
