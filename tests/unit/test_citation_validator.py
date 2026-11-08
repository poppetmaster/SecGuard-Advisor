"""Pruebas del validador automático de citas (control 1)."""

from pathlib import Path

import pytest
from tests.fixtures.corpus import create_case, seed_document

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory

TEXT = (
    "El marco de ciberseguridad define funciones centrales para gobernar, "
    "identificar, proteger, detectar, responder y recuperar."
)


@pytest.fixture
def context(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'citations.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case_id = create_case(session, "Caso de citas")
        session.commit()
    seeded = seed_document(
        factory,
        texts=[TEXT],
        case_id=case_id,
        pages=[12],
        sections=["GOVERN"],
    )
    yield factory, CaseScope(case_id=case_id), seeded
    engine.dispose()


def _check(context, **overrides):
    from secguard_advisor.retrieval.citations import check_citation

    factory, scope, seeded = context
    payload = {
        "chunk_id": seeded.chunk_ids[0],
        "version_id": seeded.version_id,
        "page": 12,
        "section": "GOVERN",
        "quote": "funciones centrales para gobernar",
    }
    payload.update(overrides)
    with factory() as session:
        return check_citation(session, scope, **payload)


def test_literal_quote_is_valid(context) -> None:
    result = _check(context)

    assert result.status == "valid"
    assert result.reason is None
    assert result.chunk is not None


def test_quote_match_ignores_case_spacing_and_soft_hyphens(context) -> None:
    result = _check(context, quote="FUNCIONES   centrales\npara gobernar")

    assert result.status == "valid"


def test_quote_with_soft_hyphen_is_normalized(context) -> None:
    result = _check(context, quote="ciber\u00adseguridad define funciones")

    assert result.status == "valid"


def test_nonexistent_chunk_is_rejected(context) -> None:
    result = _check(context, chunk_id="0" * 32)

    assert result.status == "rejected"
    assert result.reason == "chunk_missing"


def test_version_mismatch_is_rejected(context) -> None:
    result = _check(context, version_id="1" * 32)

    assert result.status == "rejected"
    assert result.reason == "version_mismatch"


def test_page_mismatch_is_rejected(context) -> None:
    result = _check(context, page=99)

    assert result.status == "rejected"
    assert result.reason == "page_mismatch"


def test_section_mismatch_is_rejected(context) -> None:
    result = _check(context, section="PROTECT")

    assert result.status == "rejected"
    assert result.reason == "section_mismatch"


def test_paraphrase_is_rejected(context) -> None:
    result = _check(context, quote="el marco dice que hay que gobernar todo")

    assert result.status == "rejected"
    assert result.reason == "quote_not_found"


def test_empty_quote_is_rejected(context) -> None:
    result = _check(context, quote="   ")

    assert result.status == "rejected"
    assert result.reason == "quote_empty"


def test_quote_over_400_characters_is_rejected(context) -> None:
    result = _check(context, quote="a" * 401)

    assert result.status == "rejected"
    assert result.reason == "quote_too_long"


def test_chunk_of_another_case_is_rejected(tmp_path: Path) -> None:
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'other.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        case_a = create_case(session, "Caso A")
        case_b = create_case(session, "Caso B")
        session.commit()
    seeded = seed_document(factory, texts=[TEXT], case_id=case_a, pages=[1])
    with factory() as session:
        from secguard_advisor.retrieval.citations import check_citation

        result = check_citation(
            session,
            CaseScope(case_id=case_b),
            chunk_id=seeded.chunk_ids[0],
            version_id=seeded.version_id,
            page=1,
            section=None,
            quote="funciones centrales",
        )
    engine.dispose()

    assert result.status == "rejected"
    assert result.reason == "scope_mismatch"
