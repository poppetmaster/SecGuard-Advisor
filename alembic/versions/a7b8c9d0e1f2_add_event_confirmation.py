"""link notification events to their manual confirmation

Revision ID: a7b8c9d0e1f2
Revises: f3a4b5c6d7e8
Create Date: 2026-11-23 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_NAME = "fk_notification_events_confirmation"


def upgrade() -> None:
    with op.batch_alter_table("notification_events") as batch:
        batch.add_column(sa.Column("confirmation_id", sa.String(length=32), nullable=True))
        batch.create_foreign_key(
            FK_NAME,
            "report_confirmations",
            ["confirmation_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("notification_events") as batch:
        batch.drop_constraint(FK_NAME, type_="foreignkey")
        batch.drop_column("confirmation_id")
