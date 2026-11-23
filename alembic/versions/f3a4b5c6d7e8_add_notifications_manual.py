"""add contacts, verification, confirmations and manual delivery

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-11-23 08:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: str | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contact_channels",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("alias", sa.String(length=80), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False, server_default="telegram"),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column("chat_type", sa.String(length=20), nullable=False, server_default="private"),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unverified"),
        sa.Column("verification_method", sa.String(length=40), nullable=True),
        sa.Column("verified_at", sa.String(length=40), nullable=True),
        sa.Column("verified_by", sa.String(length=120), nullable=True),
        sa.Column("verification_evidence", sa.Text(), nullable=True),
        sa.Column("chat_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("consent_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("consent_at", sa.String(length=40), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint("channel IN ('telegram')", name="channel_valid"),
        sa.CheckConstraint(
            "chat_type IN ('private','group','supergroup','channel')", name="chat_type_valid"
        ),
        sa.CheckConstraint(
            "status IN ('unverified','verified','revoked','disabled')", name="contact_status_valid"
        ),
        sa.CheckConstraint(
            "consent_status IN ('pending','granted','revoked')", name="consent_status_valid"
        ),
        sa.CheckConstraint(
            "status != 'verified' OR verified_at IS NOT NULL", name="verified_has_time"
        ),
        sa.CheckConstraint(
            "consent_status != 'granted' OR consent_at IS NOT NULL", name="consent_has_time"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "chat_id", name="uq_contact_channels_chat"),
    )
    op.create_index("ix_contact_channels_status", "contact_channels", ["status", "active"])

    op.create_table(
        "contact_case_links",
        sa.Column("contact_id", sa.String(length=32), nullable=False),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("authorized", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contact_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("contact_id", "case_id"),
    )
    op.create_index("ix_contact_case_links_case", "contact_case_links", ["case_id", "authorized"])

    op.create_table(
        "contact_verification_challenges",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("contact_id", sa.String(length=32), nullable=False),
        sa.Column("bot_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("code_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "purpose", sa.String(length=30), nullable=False, server_default="contact_verification"
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.String(length=40), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("consumed_at", sa.String(length=40), nullable=True),
        sa.Column("last_sent_at", sa.String(length=40), nullable=True),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("window_started_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint("purpose IN ('contact_verification')", name="challenge_purpose_valid"),
        sa.CheckConstraint(
            "status IN ('pending','consumed','expired','locked')", name="challenge_status_valid"
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND attempts <= max_attempts", name="challenge_attempts_range"
        ),
        sa.CheckConstraint("max_attempts = 3", name="challenge_max_attempts"),
        sa.CheckConstraint(
            "status != 'consumed' OR consumed_at IS NOT NULL", name="consumed_has_time"
        ),
        sa.ForeignKeyConstraint(["contact_id"], ["contact_channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_contact_challenges_contact_status",
        "contact_verification_challenges",
        ["contact_id", "status"],
    )

    op.create_table(
        "report_confirmations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("report_version_id", sa.String(length=32), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("contacts_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("invalidated_at", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_version_id"], ["report_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_report_confirmations_version",
        "report_confirmations",
        ["report_version_id", "created_at"],
    )
    op.create_index(
        "ix_report_confirmations_case", "report_confirmations", ["case_id", "created_at"]
    )

    op.create_table(
        "notification_events",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("case_id", sa.String(length=32), nullable=False),
        sa.Column("report_version_id", sa.String(length=32), nullable=False),
        sa.Column("contact_id", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("rule_id", sa.String(length=32), nullable=True),
        sa.Column("rule_version", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("content_policy_json", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("confirmed_by", sa.String(length=120), nullable=True),
        sa.Column("confirmed_at", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="prepared"),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint("mode IN ('manual','automatic')", name="event_mode_valid"),
        sa.CheckConstraint(
            "status IN ('prepared','queued','sending','accepted','partial','failed','uncertain','skipped')",
            name="event_status_valid",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_version_id"], ["report_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contact_channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_notification_events_idempotency"),
    )
    op.create_index(
        "ix_notification_events_case_status", "notification_events", ["case_id", "status"]
    )
    op.create_index("ix_notification_events_version", "notification_events", ["report_version_id"])

    op.create_table(
        "notification_components",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="prepared"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_message_id", sa.String(length=128), nullable=True),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint("kind IN ('summary','document')", name="component_kind_valid"),
        sa.CheckConstraint(
            "status IN ('prepared','requested','accepted','failed','uncertain','skipped')",
            name="component_status_valid",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="component_attempts_nonnegative"),
        sa.ForeignKeyConstraint(["event_id"], ["notification_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "kind", name="uq_notification_components_kind"),
    )

    op.create_table(
        "notification_attempts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=32), nullable=False),
        sa.Column("component_kind", sa.String(length=20), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="requested"),
        sa.Column("requested_at", sa.String(length=40), nullable=False),
        sa.Column("finished_at", sa.String(length=40), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("provider_message_id", sa.String(length=128), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "status IN ('requested','accepted','failed','uncertain')", name="attempt_status_valid"
        ),
        sa.CheckConstraint("attempt_no >= 1", name="attempt_no_positive"),
        sa.ForeignKeyConstraint(["event_id"], ["notification_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id", "component_kind", "attempt_no", name="uq_notification_attempts_no"
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_attempts")
    op.drop_table("notification_components")
    op.drop_index("ix_notification_events_version", table_name="notification_events")
    op.drop_index("ix_notification_events_case_status", table_name="notification_events")
    op.drop_table("notification_events")
    op.drop_index("ix_report_confirmations_case", table_name="report_confirmations")
    op.drop_index("ix_report_confirmations_version", table_name="report_confirmations")
    op.drop_table("report_confirmations")
    op.drop_index(
        "ix_contact_challenges_contact_status",
        table_name="contact_verification_challenges",
    )
    op.drop_table("contact_verification_challenges")
    op.drop_index("ix_contact_case_links_case", table_name="contact_case_links")
    op.drop_table("contact_case_links")
    op.drop_index("ix_contact_channels_status", table_name="contact_channels")
    op.drop_table("contact_channels")
