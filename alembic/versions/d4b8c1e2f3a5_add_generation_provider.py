"""add generation provider and cost status

Revision ID: d4b8c1e2f3a5
Revises: b7f2c9d1e4a6
Create Date: 2026-11-22 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4b8c1e2f3a5"
down_revision: str | None = "b7f2c9d1e4a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "generator_provider",
                sa.String(length=20),
                nullable=False,
                server_default="ollama",
            )
        )
        batch_op.add_column(sa.Column("generator_identity", sa.String(length=200), nullable=True))
        batch_op.add_column(
            sa.Column(
                "cost_status",
                sa.String(length=20),
                nullable=False,
                server_default="not_applicable",
            )
        )
        batch_op.add_column(sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True))
        batch_op.add_column(sa.Column("cost_tariff_version", sa.String(length=40), nullable=True))
        batch_op.create_check_constraint(
            "provider_valid",
            "generator_provider IN ('ollama', 'deepseek', 'anthropic')",
        )
        batch_op.create_check_constraint(
            "cost_status_valid",
            "cost_status IN ('calculated', 'unknown', 'not_applicable')",
        )
        batch_op.create_check_constraint(
            "cost_calculated_has_amount",
            "cost_status != 'calculated' OR cost_usd IS NOT NULL",
        )
        batch_op.create_check_constraint(
            "cost_unknown_has_no_amount",
            "cost_status != 'unknown' OR cost_usd IS NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_constraint("cost_unknown_has_no_amount", type_="check")
        batch_op.drop_constraint("cost_calculated_has_amount", type_="check")
        batch_op.drop_constraint("cost_status_valid", type_="check")
        batch_op.drop_constraint("provider_valid", type_="check")
        batch_op.drop_column("cost_tariff_version")
        batch_op.drop_column("cost_usd")
        batch_op.drop_column("cost_status")
        batch_op.drop_column("generator_identity")
        batch_op.drop_column("generator_provider")
