"""Aceptación local con el CSV real filtrado y Ollama local.

No usa el reporte original de 62 MB ni el almacenamiento del usuario. El CSV
real y su manifiesto se leen de ``../`` y todo el estado vive en ``tmp_path``.
Las salidas solo muestran agregados; no se imprimen filas ni valores privados.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from tests.fixtures.real_corpus import real_embedder

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.config import Settings
from secguard_advisor.conversation.llm import GenerationConfig, OllamaGenerator
from secguard_advisor.conversation.memory import open_memory
from secguard_advisor.conversation.tokenizer import load_prompt_counter
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url
from secguard_advisor.db.models import (
    Message,
    MessageCitation,
    QualysImport,
    QualysVulnerability,
    QualysVulnerabilityCve,
    Run,
    RunToolCall,
)
from secguard_advisor.retrieval.index import ChromaIndex
from secguard_advisor.vulnerabilities.validation import validate_csv
from secguard_advisor.web.app import create_app

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT.parent / "14-Qualys_Hallazgos_Active_New_ReOpened.csv"
MANIFEST_PATH = ROOT.parent / "14-Qualys_Hallazgos_Active_New_ReOpened_manifest.json"
ORIGIN = {"Origin": "http://testserver"}
HTMX = {**ORIGIN, "HX-Request": "true"}
QUESTIONS = (
    (
        "total",
        "¿Cuántos registros importados hay en total en la instantánea confirmada? "
        "Respondé solo con ese conteo.",
        662,
    ),
    (
        "severity",
        "¿Cuántos registros importados tienen severidad 5? Respondé solo con ese conteo.",
        70,
    ),
    (
        "priority",
        "¿Cuántos registros importados tienen prioridad conjunta de explotabilidad y malware? "
        "Respondé solo con ese conteo.",
        8,
    ),
)


def _require_inputs() -> None:
    if not CSV_PATH.exists() or not MANIFEST_PATH.exists():
        pytest.skip("Aceptación real no ejecutada: falta el CSV filtrado o su manifiesto en ../.")


def _create_case(client: TestClient, title: str) -> str:
    response = client.post("/cases", data={"title": title}, headers=ORIGIN, follow_redirects=False)
    assert response.status_code == 303
    return response.headers["location"].split("/")[-1]


def _upload(client: TestClient, case_id: str, content: bytes):
    response = client.post(
        f"/cases/{case_id}/vulnerabilities/imports/validate",
        files={"file": (CSV_PATH.name, content, "text/csv")},
        headers=HTMX,
    )
    redirect = response.headers.get("HX-Redirect")
    return client.get(redirect) if redirect else response


def _manifest_variants(tmp_path: Path) -> tuple[Path, Path]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    mismatch = tmp_path / "manifest_mismatch.json"
    changed = dict(payload)
    changed["output_detail_rows"] = int(payload["output_detail_rows"]) + 1
    mismatch.write_text(json.dumps(changed), encoding="utf-8")
    invalid = tmp_path / "manifest_invalid.json"
    invalid.write_text("{not json", encoding="utf-8")
    return mismatch, invalid


def test_real_csv_acceptance_http_sqlite_and_ollama(tmp_path: Path, monkeypatch) -> None:
    _require_inputs()
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    settings = Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        corpus_dir=tmp_path / "corpus",
    )
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    content = CSV_PATH.read_bytes()

    # Validación directa con manifiesto, fuera del formulario web.
    matched = validate_csv(content, settings=settings, manifest_path=MANIFEST_PATH)
    assert matched.status == "staged"
    assert matched.manifest.status == "matched"
    assert matched.row_count == 662
    assert len(matched.detected_columns) == 41
    assert matched.valid_rows == 662 and matched.invalid_rows == 0
    assert matched.status_counts == {"Active": 631, "New": 10, "Re-Opened": 21}
    assert matched.severity_counts == {"1": 20, "2": 316, "3": 94, "4": 162, "5": 70}
    assert matched.exploitability_counts == {"positive": 129, "indeterminate": 533}
    assert matched.malware_counts == {"positive": 8, "indeterminate": 654}
    assert matched.priority_counts == {"both_positive": 8}
    assert matched.possible_repeat_groups == 10
    assert matched.possible_repeat_rows == 11
    assert sum(1 for row in matched.rows if len(row.cves) > 1) == 179
    assert matched.manifest.status == "matched"

    absent = validate_csv(content, settings=settings)
    assert absent.manifest.status == "absent"
    assert absent.status == "staged"
    mismatch_path, invalid_path = _manifest_variants(tmp_path)
    mismatch = validate_csv(content, settings=settings, manifest_path=mismatch_path)
    assert mismatch.status == "rejected"
    assert mismatch.manifest.status == "mismatch"
    invalid = validate_csv(content, settings=settings, manifest_path=invalid_path)
    assert invalid.status == "rejected"
    assert invalid.manifest.status == "invalid"

    app = create_app(settings, ollama_probe=lambda: True)
    with TestClient(app) as client:
        case_id = _create_case(client, "Aceptación real Qualys")
        preview = _upload(client, case_id, content)
        assert preview.status_code == 200
        assert "Listo para confirmar" in preview.text
        assert "662" in preview.text
        with client.app.state.session_factory() as session:
            record = session.scalar(select(QualysImport).where(QualysImport.case_id == case_id))
            assert record is not None
            import_id = record.id
        confirmed = client.post(
            f"/cases/{case_id}/vulnerabilities/imports/{import_id}/confirm",
            headers=HTMX,
        )
        assert confirmed.status_code == 200
        section = client.get(f"/cases/{case_id}/vulnerabilities")
        assert section.status_code == 200
        assert "662" in section.text
        assert "Importación confirmada" in section.text or "Instantánea confirmada" in section.text

        repeated = _upload(client, case_id, content)
        assert "ya estaba confirmada" in repeated.text
        with client.app.state.session_factory() as session:
            records = list(
                session.scalars(select(QualysImport).where(QualysImport.case_id == case_id))
            )
            assert len(records) == 1
            assert records[0].id == import_id
            rows = session.scalar(
                select(func.count())
                .select_from(QualysVulnerability)
                .where(QualysVulnerability.import_id == import_id)
            )
            assert rows == 662

        other_case = _create_case(client, "Caso aislado")
        foreign = client.get(
            f"/cases/{other_case}/vulnerabilities",
            params={"import_id": import_id},
        )
        assert foreign.status_code == 404

        factory = client.app.state.session_factory
        with factory() as session:
            multi_cve = session.execute(
                select(QualysVulnerabilityCve.cve)
                .join(
                    QualysVulnerability,
                    QualysVulnerabilityCve.vulnerability_id == QualysVulnerability.id,
                )
                .where(QualysVulnerability.import_id == import_id)
                .group_by(QualysVulnerabilityCve.cve)
                .having(func.count() > 1)
                .limit(1)
            ).scalar_one()
            expected_cve = session.scalar(
                select(func.count(func.distinct(QualysVulnerability.id)))
                .select_from(QualysVulnerability)
                .join(
                    QualysVulnerabilityCve,
                    QualysVulnerabilityCve.vulnerability_id == QualysVulnerability.id,
                )
                .where(
                    QualysVulnerability.import_id == import_id,
                    QualysVulnerabilityCve.cve == multi_cve,
                )
            )
            relations = session.scalar(
                select(func.count())
                .select_from(QualysVulnerabilityCve)
                .join(
                    QualysVulnerability,
                    QualysVulnerabilityCve.vulnerability_id == QualysVulnerability.id,
                )
                .where(
                    QualysVulnerability.import_id == import_id,
                    QualysVulnerabilityCve.cve == multi_cve,
                )
            )
            expected_total = session.scalar(
                select(func.count())
                .select_from(QualysVulnerability)
                .where(QualysVulnerability.import_id == import_id)
            )
        assert expected_cve is not None and expected_cve > 1
        assert relations is not None and relations >= expected_cve
        assert expected_total == 662

        generator = OllamaGenerator(
            GenerationConfig(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                num_ctx=settings.generator_num_ctx,
                num_predict=settings.generator_num_predict,
                temperature=settings.generator_temperature,
                seed=settings.generator_seed,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        )
        embedder = real_embedder(settings)
        index = ChromaIndex(settings.chroma_dir)
        memory = open_memory(settings.checkpoints_path)
        try:
            for label, question, expected in QUESTIONS:
                context = start_question_turn(
                    factory,
                    settings,
                    scope=CaseScope(case_id=case_id),
                    question=question,
                    generator=generator,
                    embedder=embedder,
                    index=index,
                    token_counter=load_prompt_counter(settings.ollama_model),
                )
                result = execute_turn(context, memory=memory)
                assert result.status == "succeeded"
                assert result.outcome == "answered", (
                    f"el agente no respondió con la herramienta para {label}"
                )
                with factory() as session:
                    run = session.get(Run, context.run_id)
                    assert run is not None
                    assert 1 <= run.tool_calls_count <= 2
                    calls = list(
                        session.scalars(
                            select(RunToolCall)
                            .where(RunToolCall.run_id == run.id)
                            .order_by(RunToolCall.seq)
                        )
                    )
                    assert calls, f"sin llamada a findings_query para {label}"
                    imported_calls = [
                        call
                        for call in calls
                        if json.loads(call.result_summary_json or "{}").get("origin") == "imported"
                    ]
                    assert imported_calls, f"el agente no consultó importados para {label}"
                    summary = json.loads(imported_calls[0].result_summary_json or "{}")
                    assert summary["origin"] == "imported"
                    assert summary["total"] == expected
                    assert summary["snapshot"]["sequence"] == 1
                    if label == "total":
                        assert summary["severity_counts"]["5"] == 70
                        assert summary["priority_counts"]["both_positive"] == 8
                    if label == "severity":
                        assert summary["severity_counts"].get("5") == 70
                    if label == "priority":
                        assert summary["priority_counts"]["both_positive"] == 8
                    answer = session.scalar(
                        select(Message.content).where(Message.id == run.answer_message_id)
                    )
                    assert answer is not None
                    assert str(expected) in answer, f"respuesta sin {expected} para {label}"
                    assert session.scalar(select(func.count()).select_from(MessageCitation)) == 0
        finally:
            embedder.close()
            memory.close()
