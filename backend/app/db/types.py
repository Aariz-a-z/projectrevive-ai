"""A datetime column that is always UTC-aware, on every backend.

Storing an aware datetime in a plain `DateTime` column loses the offset, and
loses it differently depending on the database:

- SQLite has no time-zone type at all, so values come back naive. A caller
  then cannot tell whether it is holding UTC or local time, and serialising it
  produces a string with no offset. A browser parses that as *local* time,
  which displayed timestamps here several hours adrift.
- PostgreSQL's `timestamp without time zone` discards the offset using the
  session's time zone. That is correct only as long as every server involved
  is UTC. A managed database in another zone would shift every value, and
  nothing would error.

A TypeDecorator rather than `DateTime(timezone=True)` alone, because that flag
is honoured by PostgreSQL and ignored by SQLite: the two would disagree, and
development would stop reproducing production. This normalises on the way in
and the way out, so a round trip returns the same instant, aware, everywhere.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator):
    """Stores UTC, returns UTC-aware, regardless of the backend."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: object
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # A naive datetime here is a bug in the caller, not something to
            # guess about: assuming UTC would silently mislabel a local time.
            raise ValueError(
                "naive datetime passed to a UtcDateTime column; attach a "
                "timezone (datetime.now(timezone.utc)) at the source"
            )
        return value.astimezone(timezone.utc)

    def process_result_value(
        self, value: datetime | None, dialect: object
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # SQLite round-trips naive values whatever the column says. What
            # went in was UTC, so this restores the label rather than
            # converting anything.
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
