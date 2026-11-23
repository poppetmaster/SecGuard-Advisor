"""add report status and qualys provenance

Revision ID: e2f3a4b5c6d7
Revises: d8e9f0a1b2c3
Create Date: 2026-11-23 07:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: str | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("qualys_imports") as batch:
        batch.add_column(
            sa.Column(
                "provenance",
                sa.String(length=20),
                nullable=False,
                server_default="private_qualys",
            )
        )
        batch.create_check_constraint(
            "provenance_valid", "provenance IN ('private_qualys','synthetic_public')"
        )
    with op.batch_alter_table("report_versions") as batch:
        batch.add_column(
            sa.Column("status", sa.String(length=20), nullable=False, server_default="ready")
        )
        batch.create_check_constraint(
            "version_status_valid", "status IN ('generating','ready','failed')"
        )


def downgrade() -> None:
    with op.batch_alter_table("report_versions") as batch:
        batch.drop_constraint("version_status_valid", type_="check")
        batch.drop_column("status")
    with op.batch_alter_table("qualys_imports") as batch:
        batch.drop_constraint("provenance_valid", type_="check")
        batch.drop_column("provenance")
