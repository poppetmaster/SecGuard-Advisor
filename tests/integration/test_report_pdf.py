"""Real local PDF rendering and automated structure checks."""

from __future__ import annotations

import io
import re

import pytest
from pypdf import PdfReader
from sqlalchemy import select

from secguard_advisor.db.models import ReportArtifact
from secguard_advisor.reports.service import create_report_version

pytestmark = pytest.mark.integration


def test_real_pdf_has_two_or_three_pages_and_text(report_context) -> None:
    with report_context.session_factory() as session:
        result = create_report_version(
            session,
            report_context.settings,
            case_id=report_context.case_id,
            snapshot_id=report_context.snapshot_id,
            author="Prueba PDF",
            synthesize=False,
        )
        session.commit()
        artifact = session.scalar(
            select(ReportArtifact).where(
                ReportArtifact.report_version_id == result.version_id,
                ReportArtifact.kind == "pdf",
            )
        )
        assert artifact is not None
        pdf_bytes = (report_context.settings.reports_dir / artifact.relative_path).read_bytes()
    assert pdf_bytes.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert 2 <= len(reader.pages) <= 3
    texts = [page.extract_text() or "" for page in reader.pages]
    assert all(len(text.strip()) > 40 for text in texts)
    joined = re.sub(r"\s+", " ", "\n".join(texts)).strip()
    assert "Informe ejecutivo" in joined
    assert "Resumen ejecutivo" in joined
    assert "Distribución de severidad" in joined
    assert "Focos, recomendaciones y limitaciones" in joined
    assert "localhost" not in joined.lower()
