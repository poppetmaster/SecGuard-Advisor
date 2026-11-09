"""add trace confirmation audit

Revision ID: 9c3e4f5a6b7d
Revises: 8a1c2f3d4e5f
Create Date: 2026-11-09 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9c3e4f5a6b7d"
down_revision: str | None = "8a1c2f3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("trace_confirmed_by", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("trace_confirmed_at", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("trace_evidence_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_column("trace_evidence_json")
        batch_op.drop_column("trace_confirmed_at")
        batch_op.drop_column("trace_confirmed_by")
