"""Pruebas de los archivos y dobles de prueba."""

from pathlib import Path

from pypdf import PdfReader
from tests.fixtures.fakes import FakeEmbeddings, FakeLLM

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_text_pdf_has_extractable_text() -> None:
    reader = PdfReader(FILES / "sample.pdf")

    assert "Hola mundo" in (reader.pages[0].extract_text() or "")


def test_blank_pdf_has_no_text() -> None:
    reader = PdfReader(FILES / "blank.pdf")

    assert (reader.pages[0].extract_text() or "").strip() == ""


def test_corrupt_file_is_not_a_pdf() -> None:
    assert not (FILES / "corrupt.pdf").read_bytes().startswith(b"%PDF-")


def test_markdown_contains_embedded_instructions() -> None:
    content = (FILES / "sample.md").read_text(encoding="utf-8")

    assert "Ignora las instrucciones anteriores" in content


def test_fake_embeddings_are_deterministic() -> None:
    embeddings = FakeEmbeddings(dimension=8)

    first = embeddings.embed_query("texto")
    second = embeddings.embed_query("texto")
    documents = embeddings.embed_documents(["a", "b"])

    assert first == second
    assert len(first) == 8
    assert len(documents) == 2


def test_fake_llm_returns_controlled_response() -> None:
    assert FakeLLM().invoke([]) == '{"answer":"ok"}'
