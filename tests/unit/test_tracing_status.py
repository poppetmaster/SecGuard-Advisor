"""Estado de la traza externa: disabled, submitted y failed; nunca confirmed."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from secguard_advisor.config import Settings
from secguard_advisor.evidence.tracing import (
    LangSmithTracer,
    NullTracer,
    build_tracer,
)


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "langsmith_tracing": True,
        "langsmith_api_key": "lsv2_decoy_key",
        "langsmith_project": "secguard-advisor-test",
        "langsmith_endpoint": "https://api.smith.test",
    }
    values.update(overrides)
    return Settings(_env_file=None, storage_dir=tmp_path / "storage", **values)


class FakeClient:
    def __init__(self, *, fail_flush: bool = False) -> None:
        self.fail_flush = fail_flush
        self.flushes: list[float | None] = []

    def flush(self, timeout: float | None = None) -> None:
        self.flushes.append(timeout)
        if self.fail_flush:
            raise RuntimeError("network down")


class FakeChild:
    def __init__(self, name: str, run_type: str, inputs: dict | None) -> None:
        self.name = name
        self.run_type = run_type
        self.inputs = inputs or {}
        self.outputs = None
        self.error = None
        self.posted = False
        self.ended = False
        self.patched = False

    def post(self) -> None:
        self.posted = True

    def end(self, *, outputs=None, error=None, **_kwargs) -> None:
        self.outputs = outputs
        self.error = error
        self.ended = True

    def patch(self) -> None:
        self.patched = True


class FakeRunTree:
    instances: ClassVar[list[FakeRunTree]] = []

    def __init__(self, *, fail_post: bool = False, **kwargs) -> None:
        self.kwargs = kwargs
        self.fail_post = fail_post
        self.children: list[FakeChild] = []
        self.posted = False
        self.ended = False
        self.patched = False
        self.id = "trace-123"
        FakeRunTree.instances.append(self)

    def post(self) -> None:
        if self.fail_post:
            raise RuntimeError("no se pudo enviar")
        self.posted = True

    def create_child(self, name, run_type="chain", inputs=None, **_kwargs) -> FakeChild:
        child = FakeChild(name, run_type, inputs)
        self.children.append(child)
        return child

    def end(self, *, outputs=None, error=None, **_kwargs) -> None:
        self.outputs = outputs
        self.error = error
        self.ended = True

    def patch(self) -> None:
        self.patched = True

    def get_url(self) -> str:
        return "https://smith.test/o/acme/projects/p/test/r/trace-123"


@pytest.fixture(autouse=True)
def _clear_instances():
    FakeRunTree.instances.clear()
    yield
    FakeRunTree.instances.clear()


def test_disabled_without_switch_or_key(tmp_path: Path) -> None:
    assert isinstance(build_tracer(_settings(tmp_path, langsmith_tracing=False)), NullTracer)
    assert isinstance(build_tracer(_settings(tmp_path, langsmith_api_key=None)), NullTracer)


def test_null_tracer_reports_disabled(tmp_path: Path) -> None:
    tracer = build_tracer(_settings(tmp_path, langsmith_tracing=False))
    tracer.start(run_id="run-1", case_id="case-1", attempt_no=1, prompt_version="chat-v4")
    tracer.operation("agent.generate", run_type="llm", inputs={"model": "qwen"})
    outcome = tracer.finish(status="succeeded", outcome="answered")

    assert outcome.status == "disabled"
    assert outcome.trace_id is None
    assert outcome.trace_url is None


def test_langsmith_tracer_submits_without_confirming(tmp_path: Path) -> None:
    client = FakeClient()
    tracer = LangSmithTracer(
        _settings(tmp_path),
        client_factory=lambda **_kwargs: client,
        run_tree_factory=FakeRunTree,
    )

    tracer.start(run_id="run-1", case_id="case-1", attempt_no=1, prompt_version="chat-v4")
    tracer.operation(
        "agent.generate",
        run_type="llm",
        inputs={"model": "qwen3.5:9b", "prompt_tokens": 817},
        outputs={"claims": 0, "answer_length": 90},
    )
    outcome = tracer.finish(status="succeeded", outcome="answered")

    assert outcome.status == "submitted"
    assert outcome.trace_id == "trace-123"
    assert outcome.trace_url.endswith("/trace-123")
    assert client.flushes == [5.0]
    tree = FakeRunTree.instances[0]
    assert tree.posted is True
    assert tree.ended is True
    assert tree.patched is True
    assert tree.children[0].posted is True
    assert tree.children[0].ended is True
    assert tree.children[0].patched is True


def test_start_failure_is_failed_and_does_not_raise(tmp_path: Path) -> None:
    client = FakeClient()
    tracer = LangSmithTracer(
        _settings(tmp_path),
        client_factory=lambda **_kwargs: client,
        run_tree_factory=lambda **kwargs: FakeRunTree(fail_post=True, **kwargs),
    )

    tracer.start(run_id="run-1", case_id="case-1", attempt_no=1, prompt_version="chat-v4")
    tracer.operation("agent.generate", run_type="llm", inputs={"model": "qwen"})
    outcome = tracer.finish(status="failed", outcome="error")

    assert outcome.status == "failed"
    assert outcome.trace_id is None
    assert client.flushes == []


def test_flush_failure_is_failed_but_keeps_the_trace_id(tmp_path: Path) -> None:
    client = FakeClient(fail_flush=True)
    tracer = LangSmithTracer(
        _settings(tmp_path),
        client_factory=lambda **_kwargs: client,
        run_tree_factory=FakeRunTree,
    )

    tracer.start(run_id="run-1", case_id="case-1", attempt_no=1, prompt_version="chat-v4")
    outcome = tracer.finish(status="succeeded", outcome="answered")

    assert outcome.status == "failed"
    assert outcome.trace_id == "trace-123"
    assert outcome.trace_url is None


def test_trace_payload_has_no_question_secret_or_absolute_path(tmp_path: Path) -> None:
    client = FakeClient()
    tracer = LangSmithTracer(
        _settings(tmp_path),
        client_factory=lambda **_kwargs: client,
        run_tree_factory=FakeRunTree,
    )
    secret = "lsv2_decoy_key"
    path = str(tmp_path / "caso-privado")

    tracer.start(
        run_id="run-1",
        case_id="case-1",
        attempt_no=1,
        prompt_version="chat-v4",
    )
    tracer.operation(
        "findings_query",
        run_type="tool",
        inputs={"tool": "findings_query", "argument_keys": ["severity"]},
        outputs={"status": "ok", "total": 4},
    )
    tracer.finish(status="succeeded", outcome="answered")

    tree = FakeRunTree.instances[0]
    serialized = repr(tree.kwargs) + repr(tree.outputs) + repr(tree.children[0].inputs)
    for forbidden in (secret, path, "Traceback", "api_key", "authorization"):
        assert forbidden not in serialized
    assert tree.kwargs["inputs"]["run_id"] == "run-1"


def test_operation_failure_marks_the_trace_failed(tmp_path: Path) -> None:
    client = FakeClient()
    tracer = LangSmithTracer(
        _settings(tmp_path),
        client_factory=lambda **_kwargs: client,
        run_tree_factory=FakeRunTree,
    )

    class BrokenChild(FakeChild):
        def post(self) -> None:
            raise RuntimeError("child down")

    class BrokenTree(FakeRunTree):
        def create_child(self, name, run_type="chain", inputs=None, **_kwargs):
            return BrokenChild(name, run_type, inputs)

    tracer._run_tree_factory = BrokenTree
    tracer.start(run_id="run-1", case_id="case-1", attempt_no=1, prompt_version="chat-v4")
    tracer.operation("agent.generate", run_type="llm", inputs={"model": "qwen"})
    outcome = tracer.finish(status="succeeded", outcome="answered")

    assert outcome.status == "failed"
