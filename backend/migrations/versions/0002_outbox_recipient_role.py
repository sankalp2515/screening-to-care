"""outbox.recipient_role: lets the notifier pick channels per kind of person

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: a database created by create_all on v0.2 already has the column.
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("outbox")}
    if "recipient_role" not in cols:
        with op.batch_alter_table("outbox") as batch_op:
            batch_op.add_column(sa.Column("recipient_role", sa.String(length=40), nullable=False,
                                          server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("outbox") as batch_op:
        batch_op.drop_column("recipient_role")
