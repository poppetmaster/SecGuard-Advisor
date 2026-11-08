"""Las instrucciones incrustadas se conservan como datos, no como acciones."""

from pathlib import Path

from sqlalchemy import func, select
from tests.fixtures.fakes import FakeEmbedder, FakeIndex

from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import (
    Case,
    DocumentChunk,
    Run,
    RunToolCall,
)
from secguard_advisor.documents.service import ingest_document
from secguard_advisor.documents.validation import validate_bytes

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_embedded_instructions_are_stored_as_data(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        case = Case(title="Caso inyección", synthetic_notice="Escenario educativo")
        session.add(case)
        session.commit()
        case_id = case.id

    data = (FIXTURES / "sample.md").read_bytes()
    outcome = ingest_document(
        factory,
        settings,
        scope_key=f"case:{case_id}",
        case_id=case_id,
        origin="case_evidence",
        source_id=None,
        title="Documento con instrucciones",
        upload=validate_bytes("sample.md", data, settings.max_upload_bytes),
        embedder=FakeEmbedder(),
        index=FakeIndex(),
    )

    assert outcome.status == "created"
    with factory() as session:
        chunks = list(
            session.scalars(
                select(DocumentChunk).where(DocumentChunk.version_id == outcome.version_id)
            )
        )
        text = "\n".join(chunk.text for chunk in chunks)
        assert "Ignora las instrucciones anteriores" in text
        assert session.scalar(select(func.count()).select_from(Run)) == 0
        assert session.scalar(select(func.count()).select_from(RunToolCall)) == 0

    engine.dispose()
