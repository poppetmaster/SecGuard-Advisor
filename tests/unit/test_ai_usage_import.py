"""Importación idempotente del informe de evaluación 005."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from secguard_advisor.ai_usage.evaluation_import import import_evaluation
from secguard_advisor.ai_usage.evaluations import build_comparison_view
from secguard_advisor.config import Settings
from secguard_advisor.db.base import Base
from secguard_advisor.db.engine import create_engine_for_url, create_session_factory
from secguard_advisor.db.models import AiEvaluation, AiEvaluationResult, AiRequest

EVIDENCE = Path("docs/evidencia/005-evaluacion-proveedores")


def _factory(tmp_path: Path):
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    settings.ensure_directories()
    engine = create_engine_for_url(settings.database_url)
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def test_import_reads_report_without_fabricating_requests(tmp_path: Path) -> None:
    factory = _factory(tmp_path)

    with factory() as session:
        report = import_evaluation(session, EVIDENCE)
        session.commit()

    with factory() as session:
        assert report.created == 30
        assert report.updated == 0
        assert session.scalar(select(func.count()).select_from(AiRequest)) == 0
        evaluation = session.scalar(select(AiEvaluation))
        assert evaluation.version == "005-evaluation-v1"
        assert evaluation.detail_level == "aggregate"
        assert evaluation.dataset_sha256.startswith("998dc34b")
        results = list(
            session.scalars(
                select(AiEvaluationResult).where(AiEvaluationResult.provider == "deepseek")
            )
        )
        assert len(results) == 10
        blocked = next(item for item in results if item.scenario == "S08")
        assert blocked.result == "blocked"
        assert blocked.executed is False
        assert blocked.run_id is None
        assert blocked.detail_level == "aggregate"
        assert blocked.quality_method.startswith("AI-assisted")
        calculated = [item for item in results if item.cost_status == "calculated"]
        assert sum(item.cost_usd for item in calculated) > Decimal("0")


def test_comparison_counts_blocked_consumption_and_common_sample(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    with factory() as session:
        import_evaluation(session, EVIDENCE)
        session.commit()
    with factory() as session:
        view = build_comparison_view(session)

    by_provider = {item["provider"]: item for item in view["providers"]}
    deepseek = by_provider["deepseek"]
    anthropic = by_provider["anthropic"]
    assert deepseek["consumption"]["known_cost_usd"] == Decimal("0.006201")
    assert deepseek["consumption"]["known_cost_records"] == 8
    assert deepseek["consumption"]["unknown_cost_records"] == 2
    assert deepseek["consumption"]["blocked"] == 1
    assert anthropic["consumption"]["known_cost_usd"] == Decimal("0.006150")
    assert anthropic["consumption"]["known_cost_records"] == 7
    assert anthropic["consumption"]["unknown_cost_records"] == 3
    assert view["comparison_sample"]["size"] == 9
    assert "S08" not in view["comparison_sample"]["ids"]
    assert deepseek["functional"]["success_denominator"] == 9
    assert deepseek["functional"]["success_rate"] == round(6 / 9, 4)
    assert anthropic["functional"]["success_rate"] == round(4 / 9, 4)
    assert by_provider["ollama"]["functional"]["success_rate"] == round(5 / 9, 4)


def test_import_is_idempotent(tmp_path: Path) -> None:
    factory = _factory(tmp_path)

    with factory() as session:
        first = import_evaluation(session, EVIDENCE)
        session.commit()
    with factory() as session:
        second = import_evaluation(session, EVIDENCE)
        session.commit()

    with factory() as session:
        assert first.created == 30
        assert second.created == 0
        assert second.updated == 30
        assert session.scalar(select(func.count()).select_from(AiEvaluation)) == 1
        assert session.scalar(select(func.count()).select_from(AiEvaluationResult)) == 30


def test_import_requires_the_frozen_report(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    with factory() as session:
        try:
            import_evaluation(session, tmp_path / "missing")
        except FileNotFoundError:
            pass
        else:  # pragma: no cover - contrato explícito
            raise AssertionError("Se esperaba FileNotFoundError")
