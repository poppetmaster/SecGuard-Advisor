"""add run trace url

Revision ID: 8a1c2f3d4e5f
Revises: d2fac73b7c90
Create Date: 2026-11-09 01:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8a1c2f3d4e5f"
down_revision: str | None = "d2fac73b7c90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("trace_url", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_column("trace_url")
