"""add provider usage, budget ledger and external authorization

Revision ID: e6f7a8b9c0d1
Revises: d4b8c1e2f3a5
Create Date: 2026-11-22 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d4b8c1e2f3a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_processing_authorizations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("authorized_by", sa.String(length=200), nullable=False),
        sa.Column("authorized_at", sa.String(length=40), nullable=False),
        sa.Column("revoked_at", sa.String(length=40), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "scope IN ('public_corpus', 'fictional_case')",
            name="external_auth_scope_valid",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_external_auth_case",
        "external_processing_authorizations",
        ["case_id", "revoked_at"],
    )

    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "generator_max_output_tokens",
                sa.Integer(),
                nullable=False,
                server_default="1200",
            )
        )
        batch_op.add_column(
            sa.Column(
                "generator_timeout_seconds",
                sa.Float(),
                nullable=False,
                server_default="90",
            )
        )
        batch_op.add_column(sa.Column("usage_input_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("usage_output_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("usage_cached_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("usage_cache_write_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("usage_source", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column("external_authorization_id", sa.String(length=32), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_runs_external_authorization",
            "external_processing_authorizations",
            ["external_authorization_id"],
            ["id"],
        )

    op.create_table(
        "provider_usage",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("usage_source", sa.String(length=20), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("cost_status", sa.String(length=20), nullable=False),
        sa.Column("tariff_version", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "operation IN ('decide', 'generate', 'repair')",
            name="provider_usage_operation_valid",
        ),
        sa.CheckConstraint(
            "usage_source IN ('observed', 'estimated', 'unknown')",
            name="usage_source_valid",
        ),
        sa.CheckConstraint(
            "cost_status IN ('calculated', 'unknown', 'not_applicable')",
            name="usage_cost_status_valid",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_usage_run", "provider_usage", ["run_id"])

    op.create_table(
        "provider_budget_ledger",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("reserved_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("settled_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "state IN ('reserved', 'settled', 'released', 'reconciled')",
            name="budget_state_valid",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_budget_run", "provider_budget_ledger", ["run_id"])
    op.create_index("ix_provider_budget_state", "provider_budget_ledger", ["state"])


def downgrade() -> None:
    op.drop_index("ix_provider_budget_state", table_name="provider_budget_ledger")
    op.drop_index("ix_provider_budget_run", table_name="provider_budget_ledger")
    op.drop_table("provider_budget_ledger")
    op.drop_index("ix_provider_usage_run", table_name="provider_usage")
    op.drop_table("provider_usage")
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_constraint("fk_runs_external_authorization", type_="foreignkey")
        batch_op.drop_column("external_authorization_id")
        batch_op.drop_column("usage_source")
        batch_op.drop_column("usage_cache_write_tokens")
        batch_op.drop_column("usage_cached_tokens")
        batch_op.drop_column("usage_output_tokens")
        batch_op.drop_column("usage_input_tokens")
        batch_op.drop_column("generator_timeout_seconds")
        batch_op.drop_column("generator_max_output_tokens")
    op.drop_index("ix_external_auth_case", table_name="external_processing_authorizations")
    op.drop_table("external_processing_authorizations")
