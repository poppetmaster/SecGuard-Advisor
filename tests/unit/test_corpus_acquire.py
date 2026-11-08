"""Pruebas de adquisición verificable e idempotente del corpus."""

import json
from dataclasses import replace
from pathlib import Path

import httpx

from secguard_advisor.config import Settings
from secguard_advisor.corpus import acquire as acquire_module
from secguard_advisor.corpus.acquire import CORPUS_SOURCES, acquire_corpus

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        storage_dir=tmp_path / "storage",
        corpus_dir=tmp_path / "corpus",
    )


def _client(counter: list[int]) -> httpx.Client:
    def handler(_request: httpx.Request) -> httpx.Response:
        counter.append(1)
        return httpx.Response(
            200,
            content=(FIXTURES / "sample.pdf").read_bytes(),
            headers={"content-type": "application/pdf"},
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def _single_source(monkeypatch, *, marker: str = "Hola mundo") -> None:
    monkeypatch.setattr(
        acquire_module,
        "CORPUS_SOURCES",
        (replace(CORPUS_SOURCES[0], marker=marker),),
    )


def test_first_run_downloads_and_verifies(tmp_path: Path, monkeypatch) -> None:
    _single_source(monkeypatch)
    settings = _settings(tmp_path)
    counter: list[int] = []

    report = acquire_corpus(settings, client=_client(counter))

    assert len(counter) == 1
    assert report.failed == 0
    assert report.sources[0]["status"] == "verified"
    manifest = json.loads((settings.corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sources"][0]["sha256"] == report.sources[0]["sha256"]


def test_second_run_reuses_verified_original_without_download(tmp_path: Path, monkeypatch) -> None:
    _single_source(monkeypatch)
    settings = _settings(tmp_path)
    counter: list[int] = []

    acquire_corpus(settings, client=_client(counter))
    manifest_before = (settings.corpus_dir / "manifest.json").read_bytes()
    second = acquire_corpus(settings, client=_client(counter))

    assert len(counter) == 1
    assert second.failed == 0
    assert second.sources[0]["status"] == "verified"
    assert (settings.corpus_dir / "manifest.json").read_bytes() == manifest_before


def test_refresh_forces_a_new_download(tmp_path: Path, monkeypatch) -> None:
    _single_source(monkeypatch)
    settings = _settings(tmp_path)
    counter: list[int] = []

    acquire_corpus(settings, client=_client(counter))
    acquire_corpus(settings, client=_client(counter), force_refresh=True)

    assert len(counter) == 2


def test_tampered_local_original_is_downloaded_again(tmp_path: Path, monkeypatch) -> None:
    _single_source(monkeypatch)
    settings = _settings(tmp_path)
    counter: list[int] = []

    acquire_corpus(settings, client=_client(counter))
    original = settings.corpus_dir / "originals" / "csf2.pdf"
    original.write_bytes(b"%PDF-1.6 alterado")
    report = acquire_corpus(settings, client=_client(counter))

    assert len(counter) == 2
    assert report.sources[0]["status"] == "verified"
    assert original.read_bytes() == (FIXTURES / "sample.pdf").read_bytes()


def test_marker_mismatch_marks_source_failed(tmp_path: Path, monkeypatch) -> None:
    _single_source(monkeypatch, marker="Título ausente")
    settings = _settings(tmp_path)
    counter: list[int] = []

    report = acquire_corpus(settings, client=_client(counter))

    assert report.failed == 1
    assert report.sources[0]["status"] == "failed"
