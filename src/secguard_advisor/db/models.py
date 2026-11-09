"""Modelo relacional de SecGuard Advisor."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from secguard_advisor.db.base import Base


def new_id() -> str:
    """Genera un identificador hexadecimal de 32 caracteres."""
    return uuid4().hex


def utc_now_iso() -> str:
    """Devuelve la fecha actual en ISO-8601 UTC."""
    return datetime.now(UTC).isoformat()


def _status_check(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column} IN ({joined})", name=name)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    ai_application: Mapped[str | None] = mapped_column(Text)
    data_processed: Mapped[str | None] = mapped_column(Text)
    restrictions: Mapped[str | None] = mapped_column(Text)
    context_is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    synthetic_notice: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(
        String(40), nullable=False, default=utc_now_iso, onupdate=utc_now_iso
    )

    __table_args__ = (CheckConstraint("length(trim(title)) > 0", name="title_not_empty"),)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)

    __table_args__ = (UniqueConstraint("case_id", "name", name="uq_assets_case_name"),)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False)
    case_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("cases.id", ondelete="CASCADE")
    )
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)

    __table_args__ = (
        _status_check("origin", ("case_evidence", "public_corpus"), "origin_valid"),
        CheckConstraint(
            "(origin = 'case_evidence' AND case_id IS NOT NULL AND source_id IS NULL) "
            "OR (origin = 'public_corpus' AND case_id IS NULL AND source_id IS NOT NULL)",
            name="origin_scope",
        ),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column("bytes", Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    declared_version: Mapped[str | None] = mapped_column(String(100))
    declared_date: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    readable_pages: Mapped[int | None] = mapped_column(Integer)
    unreadable_pages: Mapped[str | None] = mapped_column(Text)
    extraction_version: Mapped[str] = mapped_column(String(60), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(60), nullable=False)
    chunking_version: Mapped[str] = mapped_column(String(60), nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    embedding_dim: Mapped[int | None] = mapped_column(Integer)
    retrieved_at: Mapped[str | None] = mapped_column(String(40))
    license: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)
    superseded_at: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_versions_number"),
        UniqueConstraint("scope_key", "sha256", name="uq_document_versions_content"),
        Index("ix_document_versions_scope_status", "scope_key", "status"),
        _status_check(
            "status",
            (
                "pending",
                "processing",
                "available",
                "no_usable_text",
                "failed",
                "superseded",
            ),
            "status_valid",
        ),
        CheckConstraint("bytes > 0", name="bytes_positive"),
        CheckConstraint("version_number >= 1", name="version_positive"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    version_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count_source: Mapped[str] = mapped_column(String(60), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    index_status: Mapped[str] = mapped_column(String(20), nullable=False)
    index_error: Mapped[str | None] = mapped_column(Text)
    locator: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)

    __table_args__ = (
        UniqueConstraint("version_id", "chunk_index", name="uq_document_chunks_order"),
        Index("ix_document_chunks_version_index", "version_id", "index_status"),
        _status_check("index_status", ("pending", "indexed", "failed"), "index_valid"),
        CheckConstraint("token_count > 0", name="token_count_positive"),
        CheckConstraint("chunk_index >= 0", name="chunk_index_non_negative"),
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("cases.id"))
    version_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)
    started_at: Mapped[str | None] = mapped_column(String(40))
    finished_at: Mapped[str | None] = mapped_column(String(40))
    heartbeat_at: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (
        Index("ix_ingestion_jobs_status", "status"),
        Index("ix_ingestion_jobs_version", "version_id"),
        _status_check(
            "status",
            ("queued", "running", "succeeded", "failed", "interrupted"),
            "status_valid",
        ),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    thread_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(
        String(40), nullable=False, default=utc_now_iso, onupdate=utc_now_iso
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)

    __table_args__ = (
        UniqueConstraint("conversation_id", "seq", name="uq_messages_conversation_seq"),
        _status_check("role", ("user", "assistant"), "role_valid"),
        _status_check("status", ("complete", "error"), "status_valid"),
        CheckConstraint("seq >= 1", name="seq_positive"),
    )


class MessageCitation(Base):
    __tablename__ = "message_citations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    message_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("document_chunks.id"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(String(32), nullable=False)
    document_version_id: Mapped[str] = mapped_column(String(32), nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[str] = mapped_column(String(120), nullable=False)
    check_status: Mapped[str] = mapped_column(String(20), nullable=False)
    check_reason: Mapped[str | None] = mapped_column(Text)
    support_review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unreviewed"
    )
    support_reviewed_by: Mapped[str | None] = mapped_column(String(120))
    support_reviewed_at: Mapped[str | None] = mapped_column(String(40))
    support_review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)

    __table_args__ = (
        Index("ix_message_citations_message", "message_id"),
        _status_check("check_status", ("valid", "rejected"), "check_valid"),
        _status_check(
            "support_review_status",
            ("unreviewed", "supported", "not_supported"),
            "review_valid",
        ),
        CheckConstraint(
            "support_review_status = 'unreviewed' "
            "OR (support_reviewed_by IS NOT NULL AND support_reviewed_at IS NOT NULL)",
            name="review_requires_author",
        ),
    )


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(String(32), ForeignKey("cases.id"), nullable=False)
    conversation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("conversations.id"), nullable=False
    )
    question_message_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("messages.id"))
    answer_message_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("messages.id"))
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="chat")
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retry_of_run_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("runs.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    outcome: Mapped[str | None] = mapped_column(String(40))
    generator_model: Mapped[str] = mapped_column(String(100), nullable=False)
    generator_digest: Mapped[str | None] = mapped_column(String(100))
    generator_num_ctx: Mapped[int] = mapped_column(Integer, nullable=False)
    generator_temperature: Mapped[float] = mapped_column(Float, nullable=False)
    generator_seed: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    steps_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)
    trace_status: Mapped[str] = mapped_column(String(20), nullable=False, default="disabled")
    trace_id: Mapped[str | None] = mapped_column(String(120))
    trace_url: Mapped[str | None] = mapped_column(Text)
    trace_confirmed_by: Mapped[str | None] = mapped_column(String(200))
    trace_confirmed_at: Mapped[str | None] = mapped_column(String(40))
    trace_evidence_json: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)
    finished_at: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (
        Index("ix_runs_case_started", "case_id", "started_at"),
        Index(
            "ux_runs_one_active_per_case",
            "case_id",
            unique=True,
            sqlite_where=text("status = 'running'"),
        ),
        UniqueConstraint("question_message_id", "attempt_no", name="uq_runs_question_attempt"),
        _status_check("kind", ("chat",), "kind_valid"),
        _status_check(
            "status",
            ("running", "succeeded", "failed", "timeout", "interrupted"),
            "status_valid",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN "
            "('answered', 'insufficient_evidence', "
            "'abstained_invalid_citations', 'error')",
            name="outcome_valid",
        ),
        _status_check(
            "trace_status", ("disabled", "submitted", "confirmed", "failed"), "trace_valid"
        ),
        CheckConstraint("attempt_no >= 1", name="attempt_positive"),
    )


class RunStep(Base):
    __tablename__ = "run_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    detail_json: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_run_steps_run_seq"),
        _status_check("origin", ("deterministic", "model"), "origin_valid"),
        _status_check("status", ("ok", "error", "skipped"), "status_valid"),
    )


class RunSource(Base):
    __tablename__ = "run_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("document_chunks.id"), nullable=False
    )
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    used_in_answer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("run_id", "chunk_id", name="uq_run_sources_run_chunk"),
        _status_check("origin", ("public_corpus", "case_evidence"), "origin_valid"),
    )


class RunToolCall(Base):
    __tablename__ = "run_tool_calls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(60), nullable=False)
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_summary_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(60))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_run_tool_calls_run_seq"),
        _status_check("origin", ("model_requested", "deterministic"), "origin_valid"),
        _status_check("status", ("ok", "invalid_arguments", "error"), "status_valid"),
    )


class SyntheticDataset(Base):
    __tablename__ = "synthetic_datasets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    applies_to_case_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("cases.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("synthetic_datasets.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    severity_raw: Mapped[str] = mapped_column(String(20), nullable=False)
    severity_label: Mapped[str] = mapped_column(String(20), nullable=False)
    cvss_base: Mapped[float | None] = mapped_column(Float)
    qid: Mapped[str | None] = mapped_column(String(20))
    first_detected: Mapped[str | None] = mapped_column(String(40))
    last_detected: Mapped[str | None] = mapped_column(String(40))
    provenance: Mapped[str] = mapped_column(String(120), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)

    __table_args__ = (
        Index("ix_findings_case_severity", "case_id", "severity_label"),
        Index("ix_findings_case_asset", "case_id", "asset_id"),
        Index("ix_findings_case_qid", "case_id", "qid"),
        _status_check(
            "severity_label",
            ("Critical", "High", "Medium", "Low", "Info"),
            "severity_valid",
        ),
        CheckConstraint(
            "cvss_base IS NULL OR (cvss_base >= 0 AND cvss_base <= 10)",
            name="cvss_range",
        ),
    )


class FindingCve(Base):
    __tablename__ = "finding_cves"

    finding_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("findings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    cve: Mapped[str] = mapped_column(String(20), primary_key=True)

    __table_args__ = (Index("ix_finding_cves_cve", "cve"),)


class QualysImport(Base):
    __tablename__ = "qualys_imports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    csv_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    csv_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    manifest_status: Mapped[str] = mapped_column(String(20), nullable=False, default="absent")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    manual_review_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    possible_repeat_groups: Mapped[int] = mapped_column(Integer, nullable=False)
    possible_repeat_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    status_counts_json: Mapped[str] = mapped_column(Text, nullable=False)
    severity_counts_json: Mapped[str] = mapped_column(Text, nullable=False)
    exploitability_counts_json: Mapped[str] = mapped_column(Text, nullable=False)
    malware_counts_json: Mapped[str] = mapped_column(Text, nullable=False)
    priority_counts_json: Mapped[str] = mapped_column(Text, nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(60), nullable=False)
    severity_policy_version: Mapped[str] = mapped_column(String(60), nullable=False)
    status_policy_version: Mapped[str] = mapped_column(String(60), nullable=False)
    priority_rule_version: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)
    validated_at: Mapped[str | None] = mapped_column(String(40))
    confirmed_at: Mapped[str | None] = mapped_column(String(40))
    cancelled_at: Mapped[str | None] = mapped_column(String(40))
    expires_at: Mapped[str | None] = mapped_column(String(40))
    confirmed_sequence: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_qualys_imports_case_status", "case_id", "status"),
        Index("ix_qualys_imports_case_sequence", "case_id", "confirmed_sequence"),
        Index(
            "ux_qualys_imports_confirmed_hash",
            "case_id",
            "csv_sha256",
            unique=True,
            sqlite_where=text("status = 'confirmed'"),
        ),
        Index(
            "ux_qualys_imports_confirmed_sequence",
            "case_id",
            "confirmed_sequence",
            unique=True,
            sqlite_where=text("confirmed_sequence IS NOT NULL"),
        ),
        _status_check(
            "status",
            ("validating", "staged", "rejected", "confirmed", "cancelled", "expired", "failed"),
            "status_valid",
        ),
        _status_check(
            "manifest_status",
            ("absent", "matched", "mismatch", "invalid"),
            "manifest_status_valid",
        ),
        CheckConstraint("csv_bytes >= 0", name="csv_bytes_nonnegative"),
        CheckConstraint("row_count >= 0", name="row_count_nonnegative"),
        CheckConstraint("valid_rows >= 0", name="valid_rows_nonnegative"),
        CheckConstraint("invalid_rows >= 0", name="invalid_rows_nonnegative"),
        CheckConstraint("warning_rows >= 0", name="warning_rows_nonnegative"),
        CheckConstraint("manual_review_rows >= 0", name="manual_review_rows_nonnegative"),
        CheckConstraint("possible_repeat_groups >= 0", name="repeat_groups_nonnegative"),
        CheckConstraint("possible_repeat_rows >= 0", name="repeat_rows_nonnegative"),
        CheckConstraint(
            "confirmed_sequence IS NULL OR confirmed_sequence >= 1", name="sequence_positive"
        ),
        CheckConstraint("status != 'staged' OR invalid_rows = 0", name="staged_valid_rows"),
        CheckConstraint("status != 'confirmed' OR invalid_rows = 0", name="confirmed_valid_rows"),
        CheckConstraint(
            "status NOT IN ('staged','confirmed') OR row_count >= 1",
            name="staged_not_empty",
        ),
        CheckConstraint(
            "manifest_status != 'matched' OR manifest_sha256 IS NOT NULL",
            name="matched_has_manifest",
        ),
        CheckConstraint(
            "status != 'confirmed' OR confirmed_sequence IS NOT NULL",
            name="confirmed_has_sequence",
        ),
        CheckConstraint(
            "confirmed_at IS NULL OR status = 'confirmed'",
            name="confirmed_at_status",
        ),
        CheckConstraint(
            "status != 'confirmed' OR confirmed_at IS NOT NULL",
            name="confirmed_has_time",
        ),
    )


class QualysVulnerability(Base):
    __tablename__ = "qualys_vulnerabilities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    import_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("qualys_imports.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    asset_label: Mapped[str] = mapped_column(String(200), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64))
    dns: Mapped[str | None] = mapped_column(String(200))
    netbios: Mapped[str | None] = mapped_column(String(200))
    fqdn: Mapped[str | None] = mapped_column(String(200))
    qid: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    vuln_type: Mapped[str | None] = mapped_column(String(20))
    status_raw: Mapped[str] = mapped_column(String(40), nullable=False)
    status_normalized: Mapped[str] = mapped_column(String(20), nullable=False)
    status_group: Mapped[str] = mapped_column(String(20), nullable=False)
    severity_raw: Mapped[str] = mapped_column(String(20), nullable=False)
    severity_level: Mapped[int] = mapped_column(Integer, nullable=False)
    severity_label: Mapped[str] = mapped_column(String(20), nullable=False)
    severity_policy_version: Mapped[str] = mapped_column(String(60), nullable=False)
    port: Mapped[int | None] = mapped_column(Integer)
    protocol: Mapped[str | None] = mapped_column(String(20))
    first_detected: Mapped[str | None] = mapped_column(String(40))
    last_detected: Mapped[str | None] = mapped_column(String(40))
    first_detected_normalized: Mapped[str | None] = mapped_column(String(40))
    last_detected_normalized: Mapped[str | None] = mapped_column(String(40))
    date_last_fixed: Mapped[str | None] = mapped_column(String(40))
    first_reopened: Mapped[str | None] = mapped_column(String(40))
    last_reopened: Mapped[str | None] = mapped_column(String(40))
    times_detected: Mapped[int | None] = mapped_column(Integer)
    times_reopened: Mapped[int | None] = mapped_column(Integer)
    exploitability_raw: Mapped[str | None] = mapped_column(Text)
    exploitability_eval: Mapped[str] = mapped_column(String(20), nullable=False)
    exploitability_reason: Mapped[str | None] = mapped_column(String(200))
    malware_raw: Mapped[str | None] = mapped_column(Text)
    malware_eval: Mapped[str] = mapped_column(String(20), nullable=False)
    malware_reason: Mapped[str | None] = mapped_column(String(200))
    priority_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority_reason: Mapped[str | None] = mapped_column(String(300))
    priority_rule_version: Mapped[str] = mapped_column(String(60), nullable=False)
    vendor_metrics_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)

    __table_args__ = (
        UniqueConstraint("import_id", "row_number", name="uq_qualys_vulns_import_row"),
        Index("ix_qualys_vulns_case_import", "case_id", "import_id"),
        Index("ix_qualys_vulns_case_status", "case_id", "status_group"),
        Index("ix_qualys_vulns_case_severity", "case_id", "severity_level"),
        Index("ix_qualys_vulns_case_qid", "case_id", "qid"),
        Index("ix_qualys_vulns_case_asset", "case_id", "asset_label"),
        Index("ix_qualys_vulns_case_priority", "case_id", "priority_flag"),
        Index("ix_qualys_vulns_case_indicators", "case_id", "exploitability_eval", "malware_eval"),
        CheckConstraint("row_number >= 1", name="row_number_positive"),
        CheckConstraint("severity_level BETWEEN 1 AND 5", name="severity_level_range"),
        _status_check(
            "status_normalized",
            ("active", "new", "reopened", "fixed", "manual_review"),
            "status_normalized_valid",
        ),
        _status_check(
            "status_group",
            ("pending_known", "fixed", "manual_review"),
            "status_group_valid",
        ),
        _status_check(
            "exploitability_eval",
            ("positive", "negative_no_info", "indeterminate"),
            "exploitability_eval_valid",
        ),
        _status_check(
            "malware_eval",
            ("positive", "negative_no_info", "indeterminate"),
            "malware_eval_valid",
        ),
        CheckConstraint(
            "(priority_flag = 0) OR "
            "(exploitability_eval = 'positive' AND malware_eval = 'positive')",
            name="priority_requires_both",
        ),
    )


class QualysVulnerabilityCve(Base):
    __tablename__ = "qualys_vulnerability_cves"

    vulnerability_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("qualys_vulnerabilities.id", ondelete="CASCADE"), primary_key=True
    )
    cve: Mapped[str] = mapped_column(String(20), primary_key=True)

    __table_args__ = (Index("ix_qualys_vuln_cves_cve", "cve"),)


class QualysImportIssue(Base):
    __tablename__ = "qualys_import_issues"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    import_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("qualys_imports.id", ondelete="CASCADE"), nullable=False
    )
    row_number: Mapped[int | None] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    field: Mapped[str | None] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=utc_now_iso)

    __table_args__ = (
        _status_check(
            "severity",
            ("error", "warning", "manual_review"),
            "severity_valid",
        ),
        Index("ix_qualys_import_issues_import", "import_id", "severity"),
        Index("ix_qualys_import_issues_row", "import_id", "row_number"),
    )
