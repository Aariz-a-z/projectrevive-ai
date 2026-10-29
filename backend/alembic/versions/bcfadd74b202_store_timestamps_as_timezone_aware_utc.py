"""store timestamps as timezone-aware UTC

Revision ID: bcfadd74b202
Revises: 2490614b4cb4
Create Date: 2026-10-29 10:21:49.571737

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bcfadd74b202'
down_revision: Union[str, Sequence[str], None] = '2490614b4cb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make the timestamp columns time-zone aware.

    Written by hand. Autogenerate found nothing, because it compared against
    SQLite, where DateTime and DateTime(timezone=True) render identically.
    On PostgreSQL the column genuinely changes from `timestamp without time
    zone` to `timestamptz`, and running autogenerate on a developer's SQLite
    database would have silently shipped no migration at all.

    `postgresql_using` matters as much as the type change. Converting to
    timestamptz without it makes PostgreSQL read the existing naive values in
    the *session's* time zone. Those values are UTC, so on any server not set
    to UTC every historical timestamp would shift, with no error.
    """
    for table in ("users", "analyses"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(),
                type_=sa.DateTime(timezone=True),
                existing_nullable=False,
                postgresql_using="created_at AT TIME ZONE 'UTC'",
            )


def downgrade() -> None:
    """Back to naive, converting to UTC rather than to the server's zone."""
    for table in ("users", "analyses"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(timezone=True),
                type_=sa.DateTime(),
                existing_nullable=False,
                postgresql_using="created_at AT TIME ZONE 'UTC'",
            )
