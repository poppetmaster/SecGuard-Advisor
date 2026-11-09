"""Entorno compartido para pruebas de conversación."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.retrieval.index import ChromaIndex
from tests.fixtures.corpus import SeededDocument, create_case, seed_document
from tests.fixtures.fakes import FakeEmbedder

CASE_TEXT = "El control EV.CU aplica cifrado en reposo a los datos del caso y registra cada acceso."
PUBLIC_TEXT = (
    "El marco de ciberseguridad define seis funciones centrales: gobernar, identificar, "
    "proteger, detectar, responder y recuperar."
)


@dataclass(frozen=True, slots=True)
class ConversationEnv:
    settings: Settings
    factory: sessionmaker[Session]
    case_id: str
    case_document: SeededDocument
    public_document: SeededDocument
    index: ChromaIndex


def build_env(
    tmp_path: Path,
    *,
    with_documents: bool = True,
    min_score: float | None = None,
) -> ConversationEnv:
    overrides = {} if min_score is None else {"retrieval_min_score": min_score}
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage", **overrides)
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case_id = create_case(session, "Caso de conversación")
        session.commit()
    index = ChromaIndex(settings.chroma_dir)
    embedder = FakeEmbedder()
    if with_documents:
        case_document = seed_document(
            factory,
            texts=[CASE_TEXT],
            index=index,
            embedder=embedder,
            case_id=case_id,
            title="Política interna de cifrado",
            pages=[4],
        )
        public_document = seed_document(
            factory,
            texts=[PUBLIC_TEXT],
            index=index,
            embedder=embedder,
            source_id="csf2",
            title="The NIST Cybersecurity Framework (CSF) 2.0",
            pages=[2],
        )
    else:
        from tests.fixtures.corpus import SeededDocument

        empty = SeededDocument(document_id="", version_id="", version_number=0, chunk_ids=())
        case_document = empty
        public_document = empty
    return ConversationEnv(
        settings=settings,
        factory=factory,
        case_id=case_id,
        case_document=case_document,
        public_document=public_document,
        index=index,
    )
