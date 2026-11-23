"""Validación previa de parejas externas autorizadas."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _module():
    spec = importlib.util.spec_from_file_location(
        "reevaluate_external_005", Path("scripts/reevaluate_external_005.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_authorized_plan_is_accepted() -> None:
    module = _module()
    module.validate_authorized_plan(module.AUTHORIZED_PLAN)


def test_deepseek_s10_is_rejected_before_calls() -> None:
    module = _module()
    plan = {key: list(value) for key, value in module.AUTHORIZED_PLAN.items()}
    plan["deepseek"].append("S10")

    try:
        module.validate_authorized_plan(plan)
    except ValueError as exc:
        assert "deepseek" in str(exc)
    else:  # pragma: no cover - contrato explícito
        raise AssertionError("DeepSeek S10 debía rechazarse")


def test_unknown_provider_is_rejected() -> None:
    module = _module()
    plan = {key: list(value) for key, value in module.AUTHORIZED_PLAN.items()}
    plan["ollama"] = ["S10"]

    try:
        module.validate_authorized_plan(plan)
    except ValueError as exc:
        assert "proveedores" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("El proveedor no autorizado debía rechazarse")
