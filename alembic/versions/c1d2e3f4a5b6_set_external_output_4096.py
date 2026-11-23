"""set external profiles max output to 4096

Revision ID: c1d2e3f4a5b6
Revises: a3c4d5e6f7a8
Create Date: 2026-11-23 05:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "a3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE ai_provider_profiles "
            "SET max_output_tokens = 4096 "
            "WHERE provider IN ('deepseek', 'anthropic') "
            "AND max_output_tokens < 4096"
        )
    )


def downgrade() -> None:
    # No se restaura un valor anterior: la migración es de configuración
    # operativa y no conserva historial de límites.
    pass
