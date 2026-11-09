"""Privacidad de payloads externos, prompts y errores con datos sintéticos."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from tests.fixtures.conversation import build_env
from tests.fixtures.fakes import FakeEmbedder, FakeTokenCounter, ScriptedGenerator

from secguard_advisor.cases.scope import CaseScope
from secguard_advisor.conversation.llm import AnswerPayload, ToolDecision
from secguard_advisor.conversation.turn import execute_turn, start_question_turn
from secguard_advisor.db.models import RunStep, RunToolCall
from secguard_advisor.evidence.tracing import TraceOutcome, _scrub
from secguard_advisor.vulnerabilities.service import QualysImportService
from secguard_advisor.vulnerabilities.validation import validate_csv

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
TITLE_DECOY = "TITLE-DECOY <script>alert(1)</script>"
ASSET_DECOY = "ASSET-DECOY.internal"
RESULTS_DECOY = "RESULTS-DECOY-full-export"
FILE_DECOY = "privado-cliente.csv"


class RecordingTracer:
    def __init__(self) -> None:
        self.starts: list[dict] = []
        self.operations: list[dict] = []
        self.finishes: list[dict] = []

    def start(self, **kwargs) -> None:
        self.starts.append(kwargs)

    def operation(self, name: str, **kwargs) -> None:
        self.operations.append({"name": name, **kwargs})

    def finish(self, **kwargs) -> TraceOutcome:
        self.finishes.append(kwargs)
        return TraceOutcome("submitted", trace_id="trace-synthetic", trace_url="http://trace")


def _decoy_csv(path: Path, *, invalid: bool = False) -> bytes:
    with (FIXTURES / "qualys_synthetic_valid.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fieldnames = list(rows[0])
    rows[0]["Title"] = TITLE_DECOY
    rows[0]["FQDN"] = ASSET_DECOY
    rows[0]["Results"] = RESULTS_DECOY
    rows[0]["Solution"] = "SOLUTION-DECOY"
    if invalid:
        rows[1]["QID"] = "PRIVATE-MARKER"
        rows[1]["Title"] = "PRIVATE-MARKER"
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    data = buffer.getvalue()
    path.write_text(data, encoding="utf-8-sig")
    return path.read_bytes()


def _assert_clean(blob: str) -> None:
    folded = blob.casefold()
    for decoy in (
        TITLE_DECOY,
        ASSET_DECOY,
        RESULTS_DECOY,
        FILE_DECOY,
        "PRIVATE-MARKER",
        "/Users/",
        "Traceback",
    ):
        assert decoy.casefold() not in folded


def test_external_payloads_prompts_and_summary_exclude_private_qualys_data(
    tmp_path: Path, monkeypatch
) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    csv_path = tmp_path / "fixture.csv"
    content = _decoy_csv(csv_path)
    service = QualysImportService(env.factory, env.settings)
    staged = service.stage_import(env.case_id, FILE_DECOY, content)
    service.confirm_import(env.case_id, staged.import_record.id)

    tracer = RecordingTracer()
    monkeypatch.setattr("secguard_advisor.conversation.turn.build_tracer", lambda _settings: tracer)
    generator = ScriptedGenerator(
        payloads=[AnswerPayload(answer="Hay 5 registros importados.", claims=[])],
        decisions=[
            ToolDecision(use_findings=True, arguments={"origin": "imported"}),
            ToolDecision(use_findings=False, arguments={}),
        ],
    )
    context = start_question_turn(
        env.factory,
        env.settings,
        scope=CaseScope(case_id=env.case_id),
        question="¿Cuántos registros importados hay en la instantánea?",
        generator=generator,
        embedder=FakeEmbedder(),
        index=env.index,
        token_counter=FakeTokenCounter(),
    )
    result = execute_turn(context)
    assert result.outcome == "answered"

    assert tracer.starts[0]["question_length"] == len(
        "¿Cuántos registros importados hay en la instantánea?"
    )
    assert tracer.starts[0]["metadata"]["generator_model"] == "fake-generator"
    assert tracer.starts[0]["metadata"]["embedding_model"] == "fake-embedding"
    assert tracer.starts[0]["metadata"]["embedding_dim"] == 4
    _assert_clean(json.dumps(tracer.starts, ensure_ascii=False, default=str))
    _assert_clean(json.dumps(tracer.operations, ensure_ascii=False, default=str))
    _assert_clean(json.dumps(tracer.finishes, ensure_ascii=False, default=str))
    _assert_clean("\n".join(generator.prompts))
    assert "Results" not in "\n".join(generator.prompts)
    _assert_clean("\n".join(generator.decision_prompts))

    with env.factory() as session:
        call = session.query(RunToolCall).filter(RunToolCall.run_id == context.run_id).one()
        assert call.result_summary_json is not None
        _assert_clean(call.result_summary_json)
        assert '"items"' not in call.result_summary_json
        for step in session.query(RunStep).filter(RunStep.run_id == context.run_id):
            _assert_clean(step.detail_json or "")


def test_invalid_row_errors_do_not_echo_values(tmp_path: Path) -> None:
    env = build_env(tmp_path, with_documents=False, min_score=-1.0)
    content = _decoy_csv(tmp_path / "invalid.csv", invalid=True)
    result = validate_csv(content, settings=env.settings)
    assert result.status == "rejected"
    messages = " ".join(issue.message for issue in result.issues)
    _assert_clean(messages)
    _assert_clean(result.error_message or "")


def test_trace_scrub_removes_paths_secrets_and_stack_traces() -> None:
    scrubbed = _scrub(
        {
            "path": "/Users/edwin/privado/qualys.csv",
            "api_key": "sk-super-secret-123456",
            "note": "Traceback (most recent call last)",
            "nested": ["/home/otro/dato", "texto normal"],
        }
    )
    rendered = json.dumps(scrubbed, ensure_ascii=False)
    assert "/Users/" not in rendered
    assert "sk-super-secret" not in rendered
    assert "Traceback" not in rendered
    assert "***" in rendered
