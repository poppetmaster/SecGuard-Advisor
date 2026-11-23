"""add ai requests and evaluation history

Revision ID: a3c4d5e6f7a8
Revises: f7a8b9c0d1e2
Create Date: 2026-11-23 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3c4d5e6f7a8"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_evaluations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("import_key", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=60), nullable=False),
        sa.Column("frozen_at", sa.String(length=40), nullable=True),
        sa.Column("dataset_sha256", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("detail_level", sa.String(length=20), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=True),
        sa.Column("imported_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "source IN ('report_import', 'manual', 'telemetry')",
            name="ai_eval_source_valid",
        ),
        sa.CheckConstraint(
            "detail_level IN ('aggregate', 'requests')",
            name="ai_eval_detail_valid",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_key"),
    )

    op.create_table(
        "ai_requests",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("retry_of_request_id", sa.String(length=32), nullable=True),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("started_at", sa.String(length=40), nullable=False),
        sa.Column("finished_at", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_included_in_output", sa.Boolean(), nullable=True),
        sa.Column("usage_source", sa.String(length=20), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=18, scale=9), nullable=True),
        sa.Column("cost_status", sa.String(length=20), nullable=False),
        sa.Column("provider_reported_cost_usd", sa.Numeric(precision=18, scale=9), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("tariff_version", sa.String(length=40), nullable=True),
        sa.Column("tariff_effective_at", sa.String(length=40), nullable=True),
        sa.Column("evaluation_id", sa.String(length=32), nullable=True),
        sa.Column("scenario", sa.String(length=20), nullable=True),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "operation IN ('decide', 'generate', 'repair', 'remote_count')",
            name="ai_request_operation_valid",
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'error', 'timeout', 'uncertain')",
            name="ai_request_status_valid",
        ),
        sa.CheckConstraint(
            "usage_source IN ('observed', 'estimated', 'unavailable')",
            name="ai_request_usage_valid",
        ),
        sa.CheckConstraint(
            "cost_status IN ('calculated', 'unknown', 'not_applicable')",
            name="ai_request_cost_valid",
        ),
        sa.CheckConstraint("attempt_no >= 1", name="ai_request_attempt_positive"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["retry_of_request_id"], ["ai_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "operation", "attempt_no", name="uq_ai_requests_run_operation_attempt"
        ),
    )
    op.create_index("ix_ai_requests_started", "ai_requests", ["started_at"])
    op.create_index("ix_ai_requests_provider", "ai_requests", ["provider", "model"])
    op.create_index("ix_ai_requests_status", "ai_requests", ["status"])
    op.create_index("ix_ai_requests_evaluation", "ai_requests", ["evaluation_id", "scenario"])

    op.create_table(
        "ai_evaluation_results",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("evaluation_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("scenario", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=True),
        sa.Column("executed", sa.Boolean(), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=True),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_tokens", sa.Integer(), nullable=True),
        sa.Column("usage_source", sa.String(length=20), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=18, scale=9), nullable=True),
        sa.Column("cost_status", sa.String(length=20), nullable=False),
        sa.Column("tariff_version", sa.String(length=40), nullable=True),
        sa.Column("citations_emitted", sa.Integer(), nullable=False),
        sa.Column("citations_valid", sa.Integer(), nullable=False),
        sa.Column("citations_resolvable", sa.Integer(), nullable=False),
        sa.Column("findings_match", sa.Boolean(), nullable=True),
        sa.Column("abstention_ok", sa.Boolean(), nullable=True),
        sa.Column("quality_score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("quality_method", sa.String(length=80), nullable=True),
        sa.Column("manual_review", sa.String(length=20), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=True),
        sa.Column("detail_level", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "provider IN ('ollama', 'deepseek', 'anthropic')",
            name="ai_eval_provider_valid",
        ),
        sa.CheckConstraint(
            "result IN ('approved', 'failed', 'blocked')", name="ai_eval_result_valid"
        ),
        sa.CheckConstraint(
            "usage_source IS NULL OR usage_source IN ('observed', 'estimated', 'unavailable')",
            name="ai_eval_usage_source_valid",
        ),
        sa.CheckConstraint(
            "cost_status IN ('calculated', 'unknown', 'not_applicable')",
            name="ai_eval_cost_status_valid",
        ),
        sa.CheckConstraint(
            "manual_review IN ('none', 'recorded')", name="ai_eval_manual_review_valid"
        ),
        sa.CheckConstraint(
            "detail_level IN ('aggregate', 'linked')", name="ai_eval_result_detail_valid"
        ),
        sa.ForeignKeyConstraint(["evaluation_id"], ["ai_evaluations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_id", "provider", "scenario", name="uq_ai_eval_result_provider_scenario"
        ),
    )
    op.create_index("ix_ai_eval_results_eval", "ai_evaluation_results", ["evaluation_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_eval_results_eval", table_name="ai_evaluation_results")
    op.drop_table("ai_evaluation_results")
    op.drop_index("ix_ai_requests_evaluation", table_name="ai_requests")
    op.drop_index("ix_ai_requests_status", table_name="ai_requests")
    op.drop_index("ix_ai_requests_provider", table_name="ai_requests")
    op.drop_index("ix_ai_requests_started", table_name="ai_requests")
    op.drop_table("ai_requests")
    op.drop_table("ai_evaluations")
