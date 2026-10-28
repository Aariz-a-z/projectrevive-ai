"""Request dependencies for authenticated routes."""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.security import read_access_token
from app.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db
from app.errors import InvalidSession, NotAuthenticated


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """The signed-in account, or a 401.

    The token is read from an httpOnly cookie rather than an Authorization
    header so that page JavaScript never touches it.
    """
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise NotAuthenticated()

    user_id = read_access_token(token, settings)
    user = db.get(User, user_id)
    if user is None:
        # A valid signature for an account that no longer exists.
        raise InvalidSession()
    return user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    """Like get_current_user but returns None instead of raising."""
    try:
        return get_current_user(request, db, settings)
    except NotAuthenticated:
        return None
