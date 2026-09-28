"""GET /runs/{id}/recap.{pdf,html,docx}: the Recap tab's «Export»."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fakes.job_view import seed_concluded_job
from fakes.run_result import build_app
from fastapi.testclient import TestClient

from voxtrama.rendering.recap_document import Block
from voxtrama.rendering.recap_pdf import recap_pdf


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app, engine = build_app(tmp_path)
    seed_concluded_job(engine, tmp_path, "job-1")
    return TestClient(app)


def test_the_html_export_is_one_standalone_page(client: TestClient) -> None:
    response = client.get("/runs/job-1/recap.html")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "<h2>Decisions</h2>" in response.text
    assert "Owners by Friday. (spk0 · 0:12)" in response.text
    assert "Revisit next month. [Needs review]" in response.text
    assert "<script" not in response.text and "/static/" not in response.text


def test_the_docx_export_is_a_word_package_with_the_recap(client: TestClient) -> None:
    response = client.get("/runs/job-1/recap.docx")

    package = zipfile.ZipFile(io.BytesIO(response.content))
    assert {"[Content_Types].xml", "word/document.xml", "word/styles.xml"} <= set(
        package.namelist()
    )
    document = package.read("word/document.xml").decode()
    assert "The roadmap needs owners. (spk1 · 0:08)" in document


def test_the_pdf_export_is_a_pdf_with_the_recap(client: TestClient) -> None:
    response = client.get("/runs/job-1/recap.pdf")

    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-1.4") and response.content.endswith(b"%%EOF\n")
    assert b"\x95 Owners by Friday. \\(spk0 \xb7 0:12\\))" in response.content


def test_an_unknown_format_is_404(client: TestClient) -> None:
    assert client.get("/runs/job-1/recap.xls").status_code == 404


def test_a_long_recap_breaks_lines_and_pages() -> None:
    blocks = [Block("title", "T")] + [Block("bullet", "word " * 60) for _ in range(40)]

    pdf = recap_pdf(blocks)

    assert b"/Count 1 " not in pdf
    assert pdf.count(b"/Type /Page ") > 1
