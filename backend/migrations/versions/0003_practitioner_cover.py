"""practitioners.away_until and cover_id: a named cover while someone is away (TSL-160)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: a database created by create_all already has the columns.
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("practitioners")}
    with op.batch_alter_table("practitioners") as batch_op:
        if "away_until" not in cols:
            batch_op.add_column(sa.Column("away_until", sa.DateTime(timezone=True), nullable=True))
        if "cover_id" not in cols:
            batch_op.add_column(sa.Column("cover_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("practitioners") as batch_op:
        batch_op.drop_column("cover_id")
        batch_op.drop_column("away_until")
