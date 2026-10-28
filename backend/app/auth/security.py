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
