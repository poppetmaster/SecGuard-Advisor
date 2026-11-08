"""Guardia de aislamiento del corpus y del conjunto de evaluación final."""

from pathlib import Path

import secguard_advisor
from secguard_advisor.config import Settings

SRC = Path(secguard_advisor.__file__).parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_REFERENCES = (
    "docs/referencias",
    "CONSTITUTION.md",
    "AGENTS.md",
    ".agents",
    "data/eval/final",
    "tests/fixtures",
)


def test_source_does_not_reference_forbidden_paths() -> None:
    offenders: list[tuple[str, str]] = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_REFERENCES:
            if needle in text:
                offenders.append((str(path.relative_to(SRC)), needle))

    assert offenders == []


def test_final_evaluation_directory_is_reserved() -> None:
    readme = PROJECT_ROOT / "data" / "eval" / "final" / "README.md"

    assert readme.is_file()
    assert "reservado" in readme.read_text(encoding="utf-8").lower()


def test_consultative_corpus_is_not_the_academic_references() -> None:
    settings = Settings(_env_file=None)

    assert settings.corpus_dir == Path("data/corpus")
    assert "referencias" not in str(settings.corpus_dir)
