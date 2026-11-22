"""Chroma no debe quedar como backend ejecutable ni como dependencia."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = (
    "import chromadb",
    "from chromadb",
    "ChromaIndex",
    "chroma_dir",
)


def test_product_code_has_no_executable_chroma_references() -> None:
    offenders: list[str] = []
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)}: {token}")
    assert offenders == []


def test_chroma_dependencies_are_removed() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "langchain-chroma" not in pyproject
    assert "chromadb" not in pyproject


def test_scripts_do_not_reference_chroma() -> None:
    for path in (ROOT / "scripts").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in ("ChromaIndex", "chroma_dir", "import chromadb"):
            assert token not in text, f"{path.name}: {token}"
