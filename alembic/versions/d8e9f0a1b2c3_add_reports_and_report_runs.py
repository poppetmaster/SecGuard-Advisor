"""add reports and report runs

Revision ID: d8e9f0a1b2c3
Revises: c1d2e3f4a5b6
Create Date: 2026-11-23 06:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_case_created", "reports", ["case_id", "created_at"])

    op.create_table(
        "report_versions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("report_id", sa.String(length=32), nullable=False),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("generation_key", sa.String(length=64), nullable=True),
        sa.Column("snapshot_import_id", sa.String(length=32), nullable=False),
        sa.Column("snapshot_sequence", sa.Integer(), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column("dataset_json", sa.Text(), nullable=False),
        sa.Column("dataset_sha256", sa.String(length=64), nullable=False),
        sa.Column("chart_specs_json", sa.Text(), nullable=False),
        sa.Column("synthesis_status", sa.String(length=20), nullable=False),
        sa.Column("ai_run_id", sa.String(length=32), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("focus_json", sa.Text(), nullable=False),
        sa.Column("recommendations_json", sa.Text(), nullable=False),
        sa.Column("limitations_json", sa.Text(), nullable=False),
        sa.Column("author_declared", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint("version_number >= 1", name="version_positive"),
        sa.CheckConstraint(
            "synthesis_status IN ('not_requested','completed','unavailable','failed')",
            name="synthesis_status_valid",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_import_id"], ["qualys_imports.id"]),
        sa.ForeignKeyConstraint(["ai_run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "version_number", name="uq_report_versions_number"),
    )
    op.create_index(
        "ux_report_versions_generation_key",
        "report_versions",
        ["generation_key"],
        unique=True,
        sqlite_where=sa.text("generation_key IS NOT NULL"),
    )
    op.create_index("ix_report_versions_case_created", "report_versions", ["case_id", "created_at"])
    op.create_index("ix_report_versions_snapshot", "report_versions", ["snapshot_import_id"])

    op.create_table(
        "report_artifacts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("report_version_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("chart_key", sa.String(length=40), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint("kind IN ('pdf','chart_svg')", name="artifact_kind_valid"),
        sa.CheckConstraint("bytes >= 0", name="artifact_bytes_nonnegative"),
        sa.ForeignKeyConstraint(["report_version_id"], ["report_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "report_version_id", "kind", "chart_key", name="uq_report_artifacts_kind_key"
        ),
    )

    op.drop_index("ux_runs_one_active_per_case", table_name="runs")
    with op.batch_alter_table("runs", recreate="always") as batch:
        batch.alter_column("conversation_id", existing_type=sa.String(length=32), nullable=True)
        batch.drop_constraint("kind_valid", type_="check")
        batch.drop_constraint("outcome_valid", type_="check")
        batch.create_check_constraint("kind_valid", "kind IN ('chat','report')")
        batch.create_check_constraint(
            "outcome_valid",
            "outcome IS NULL OR outcome IN ('answered','insufficient_evidence',"
            "'abstained_invalid_citations','error','report_ready','report_factual')",
        )
    op.create_index(
        "ux_runs_one_active_per_case",
        "runs",
        ["case_id"],
        unique=True,
        sqlite_where=sa.text("status = 'running' AND kind = 'chat'"),
    )


def downgrade() -> None:
    op.drop_index("ux_runs_one_active_per_case", table_name="runs")
    with op.batch_alter_table("runs", recreate="always") as batch:
        batch.drop_constraint("kind_valid", type_="check")
        batch.drop_constraint("outcome_valid", type_="check")
        batch.create_check_constraint("kind_valid", "kind IN ('chat')")
        batch.create_check_constraint(
            "outcome_valid",
            "outcome IS NULL OR outcome IN ('answered','insufficient_evidence',"
            "'abstained_invalid_citations','error')",
        )
        batch.alter_column("conversation_id", existing_type=sa.String(length=32), nullable=False)
    op.create_index(
        "ux_runs_one_active_per_case",
        "runs",
        ["case_id"],
        unique=True,
        sqlite_where=sa.text("status = 'running'"),
    )
    op.drop_table("report_artifacts")
    op.drop_index("ix_report_versions_snapshot", table_name="report_versions")
    op.drop_index("ix_report_versions_case_created", table_name="report_versions")
    op.drop_index("ux_report_versions_generation_key", table_name="report_versions")
    op.drop_table("report_versions")
    op.drop_index("ix_reports_case_created", table_name="reports")
    op.drop_table("reports")
