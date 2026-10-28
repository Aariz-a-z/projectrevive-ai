"""Auth request and response shapes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=512)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=512)


class UserPublic(BaseModel):
    """What the client is allowed to see. Never includes the password hash."""

    id: str
    email: str
    created_at: datetime
