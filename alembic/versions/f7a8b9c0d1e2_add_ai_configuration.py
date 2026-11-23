"""add ai configuration and provider profiles

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-11-22 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_configuration",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("active_provider", sa.String(length=20), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint("id = 1", name="ai_configuration_singleton"),
        sa.CheckConstraint(
            "active_provider IN ('ollama', 'deepseek', 'anthropic')",
            name="ai_active_provider_valid",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ai_provider_profiles",
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "provider IN ('ollama', 'deepseek', 'anthropic')",
            name="ai_profile_provider_valid",
        ),
        sa.CheckConstraint("max_output_tokens > 0", name="ai_profile_max_output_positive"),
        sa.CheckConstraint("timeout_seconds > 0", name="ai_profile_timeout_positive"),
        sa.PrimaryKeyConstraint("provider"),
    )


def downgrade() -> None:
    op.drop_table("ai_provider_profiles")
    op.drop_table("ai_configuration")
