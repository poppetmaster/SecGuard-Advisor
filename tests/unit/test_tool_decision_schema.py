"""Pruebas del esquema tipado de ToolDecision.arguments (Entrega 1)."""

import pytest
from pydantic import ValidationError

from secguard_advisor.conversation.llm import ToolArguments, ToolDecision
from secguard_advisor.tools.findings import ToolArgumentError, parse_arguments


def test_arguments_are_coerced_to_the_findings_schema() -> None:
    decision = ToolDecision(
        use_findings=True,
        arguments={"severity": "High", "group_by": "asset", "limit": 5},
    )

    assert isinstance(decision.arguments, ToolArguments)
    assert decision.arguments.severity == "High"
    assert decision.arguments.group_by == "asset"
    assert decision.arguments.limit == 5


def test_defaults_match_the_findings_schema() -> None:
    decision = ToolDecision(use_findings=False)

    assert decision.arguments.origin is None
    assert decision.arguments.detail is None
    assert decision.arguments.status_group is None


def test_extra_fields_and_case_id_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ToolDecision(use_findings=True, arguments={"case_id": "otro-caso"})

    with pytest.raises(ValidationError):
        ToolDecision(use_findings=True, arguments={"unexpected": True})


def test_invalid_values_reach_the_existing_tool_validator() -> None:
    severity = ToolDecision(use_findings=True, arguments={"severity": "Urgent"})
    limit = ToolDecision(use_findings=True, arguments={"limit": 0})

    with pytest.raises(ToolArgumentError):
        parse_arguments(severity.model_dump()["arguments"])
    with pytest.raises(ToolArgumentError):
        parse_arguments(limit.model_dump()["arguments"])


def test_model_dump_is_accepted_by_the_existing_parser() -> None:
    decision = ToolDecision(
        use_findings=True,
        arguments={"origin": "imported", "status_group": "pending_known"},
    )

    dumped = decision.model_dump(exclude_unset=True)["arguments"]

    assert isinstance(dumped, dict)
    assert parse_arguments(dumped).origin == "imported"
    assert parse_arguments(dumped).status_group == "pending_known"
