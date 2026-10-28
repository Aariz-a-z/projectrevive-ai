"""Signup, login, logout and session introspection."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.policy import validate_password
from app.auth.schemas import LoginRequest, SignupRequest, UserPublic
from app.auth.security import (
    create_access_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db
from app.errors import (
    AccountTemporarilyLocked,
    EmailAlreadyRegistered,
    InvalidCredentials,
)
from app.ratelimit.deps import limit_login, limit_signup, login_failures

router = APIRouter(prefix="/auth", tags=["auth"])

# Verified against when no account matches, so a wrong email costs the same
# time as a wrong password and cannot be distinguished by timing.
_DUMMY_HASH = hash_password("timing-equalisation-placeholder")


def _set_session_cookie(response: Response, user: User, settings: Settings) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=create_access_token(user.id, settings),
        max_age=settings.access_token_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _public(user: User) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, created_at=user.created_at)


@router.post(
    "/signup",
    response_model=UserPublic,
    status_code=201,
    dependencies=[Depends(limit_signup)],
)
def signup(
    payload: SignupRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserPublic:
    email = payload.email.strip().lower()

    validate_password(
        payload.password, email=email, minimum=settings.min_password_length
    )

    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise EmailAlreadyRegistered()

    user = User(
        id=uuid.uuid4().hex,
        email=email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()

    _set_session_cookie(response, user, settings)
    return _public(user)


@router.post(
    "/login", response_model=UserPublic, dependencies=[Depends(limit_login)]
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserPublic:
    email = payload.email.strip().lower()
    failures = login_failures(settings)

    # Checked before touching the database, so a locked account costs an
    # attacker a request and nothing else.
    locked_for = failures.locked_for(email)
    if locked_for > 0:
        raise AccountTemporarilyLocked(
            locked_for,
            "Too many failed sign-in attempts for this account. "
            f"Try again in {locked_for} seconds.",
        )

    user = db.scalar(select(User).where(User.email == email))

    if user is None:
        # Failures are recorded for unknown addresses too. Tracking only real
        # accounts would make lockout behaviour differ between a registered
        # and an unregistered email, which is exactly the account enumeration
        # the identical error responses already avoid.
        verify_password(_DUMMY_HASH, payload.password)
        failures.record_failure(email)
        raise InvalidCredentials()

    if not verify_password(user.password_hash, payload.password):
        failures.record_failure(email)
        raise InvalidCredentials()

    failures.record_success(email)

    # Transparently upgrade the stored hash if Argon2 parameters have changed.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        db.commit()

    _set_session_cookie(response, user, settings)
    return _public(user)


@router.post("/logout", status_code=204)
def logout(
    response: Response, settings: Settings = Depends(get_settings)
) -> Response:
    response.delete_cookie(
        key=settings.cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.status_code = 204
    return response


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> UserPublic:
    return _public(user)
