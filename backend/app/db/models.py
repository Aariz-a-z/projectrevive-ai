"""Persistence model.

Deliberately absent: the uploaded file and its full extracted text. README
section 10 says not to retain uploaded documents longer than necessary, so the
bytes are processed in memory and dropped. What is kept is the structured
profile, which includes the short evidence quotes the UI must show.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """An account.

    Only a password *hash* is stored, never the password. Email is held
    lowercased so addresses cannot be registered twice under different casing.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Every analysis belongs to exactly one account, and the API filters by it
    # on every read, so one user can never fetch another user's analysis.
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Source document metadata (not its contents).
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128))
    page_count: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(32), default="complete")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Provenance of the analysis itself, so the UI can say what produced it.
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0)

    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    # Merged rule and model findings, as a FindingsReport dump.
    findings: Mapped[dict] = mapped_column(JSON, default=dict)
    # Ranked recommendations, as a RecommendationReport dump.
    recommendations: Mapped[dict] = mapped_column(JSON, default=dict)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
