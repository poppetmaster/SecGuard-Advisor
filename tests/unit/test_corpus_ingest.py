"""Pruebas de la ingesta del corpus público."""

import json
from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import select
from tests.fixtures.fakes import FakeEmbedder, FakeIndex

from secguard_advisor.config import Settings
from secguard_advisor.corpus.ingest import ingest_public_corpus, load_manifest
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import Document, DocumentVersion

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        corpus_dir=tmp_path / "corpus",
    )


def _manifest(settings: Settings, data: bytes, *, status: str = "verified") -> None:
    originals = settings.corpus_dir / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    (originals / "csf2.pdf").write_bytes(data)
    payload = {
        "schema_version": 1,
        "sources": [
            {
                "id": "csf2",
                "title": "The NIST Cybersecurity Framework (CSF) 2.0",
                "version_label": "NIST CSWP 29",
                "sha256": sha256(data).hexdigest(),
                "status": status,
                "retrieved_at": "2026-11-08T00:00:00+00:00",
                "license": "U.S. Government work",
            }
        ],
    }
    (settings.corpus_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def factory(tmp_path: Path):
    settings = _settings(tmp_path)
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    yield settings, create_session_factory(engine)
    engine.dispose()


def test_verified_source_is_ingested_as_public(factory) -> None:
    settings, session_factory = factory
    data = (FIXTURES / "sample.pdf").read_bytes()
    _manifest(settings, data)

    outcomes = ingest_public_corpus(
        session_factory,
        settings,
        embedder=FakeEmbedder(),
        index=FakeIndex(),
    )

    assert len(outcomes) == 1
    assert outcomes[0].status == "created"
    with session_factory() as session:
        document = session.get(Document, outcomes[0].document_id)
        version = session.get(DocumentVersion, outcomes[0].version_id)
        assert document.case_id is None
        assert document.origin == "public_corpus"
        assert document.source_id == "csf2"
        assert version.status == "available"
        assert (
            session.scalar(
                select(DocumentVersion).where(DocumentVersion.scope_key == "public:csf2")
            )
            is not None
        )
    assert not list(settings.originals_dir.rglob("*.pdf"))


def test_wrong_hash_is_reported(factory) -> None:
    settings, session_factory = factory
    _manifest(settings, (FIXTURES / "sample.pdf").read_bytes())
    manifest_path = settings.corpus_dir / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["sources"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    outcomes = ingest_public_corpus(
        session_factory,
        settings,
        embedder=FakeEmbedder(),
        index=FakeIndex(),
    )

    assert outcomes[0].status == "failed"
    assert "hash" in outcomes[0].message.lower()


def test_unverified_source_is_skipped(factory) -> None:
    settings, session_factory = factory
    _manifest(settings, (FIXTURES / "sample.pdf").read_bytes(), status="failed")

    outcomes = ingest_public_corpus(
        session_factory,
        settings,
        embedder=FakeEmbedder(),
        index=FakeIndex(),
    )

    assert outcomes[0].status == "skipped"


def test_missing_manifest_is_reported(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(FileNotFoundError):
        load_manifest(settings)
