"""Tests for bounded text extraction from supported document types."""

from io import BytesIO

import pytest

from orinoco.documents.extract import extract_text


def test_plain_text_and_markdown_extraction() -> None:
    assert extract_text("notes.txt", b"Hello\nOrinoco") == "Hello\nOrinoco"
    assert extract_text("guide.md", b"# Heading\nUseful content") == "# Heading\nUseful content"


def test_docx_extraction() -> None:
    from docx import Document

    document = Document()
    document.add_paragraph("DOCX extraction works.")
    buffer = BytesIO()
    document.save(buffer)

    assert "DOCX extraction works." in extract_text("guide.docx", buffer.getvalue())


def test_xlsx_extraction() -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active["A1"] = "Spreadsheet fact"
    buffer = BytesIO()
    workbook.save(buffer)

    assert "Spreadsheet fact" in extract_text("facts.xlsx", buffer.getvalue())


def test_pptx_extraction() -> None:
    from pptx import Presentation
    from pptx.util import Inches

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    shape = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    shape.text_frame.text = "Presentation detail"
    buffer = BytesIO()
    presentation.save(buffer)

    assert "Presentation detail" in extract_text("briefing.pptx", buffer.getvalue())


def test_unsupported_and_oversized_files_are_rejected() -> None:
    with pytest.raises(ValueError, match="Supported file types"):
        extract_text("malware.exe", b"no")

    with pytest.raises(ValueError, match="10 MiB"):
        extract_text("notes.txt", b"x" * (10 * 1024 * 1024 + 1))
