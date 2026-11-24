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


def test_office_zip_bomb_expansion_is_rejected() -> None:
    """A compact Office upload must not expand beyond the extraction safety cap."""
    from zipfile import ZIP_DEFLATED, ZipFile

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"0" * (25 * 1024 * 1024 + 1))

    compressed = buffer.getvalue()
    assert len(compressed) < 10 * 1024 * 1024
    with pytest.raises(ValueError, match="25 MiB safety limit"):
        extract_text("large.docx", compressed)


def test_pdf_content_stream_count_is_bounded(monkeypatch) -> None:
    """Reject pages with excessive content-stream arrays before text parsing."""
    import pypdf

    class FakePage:
        def get(self, key):
            assert key == "/Contents"
            return [object(), object(), object(), object(), object()]

        def get_contents(self):
            raise AssertionError("content streams should be rejected before decoding")

        def extract_text(self):
            raise AssertionError("text extraction should not run for an oversized stream array")

    class FakeReader:
        is_encrypted = False
        pages = [FakePage()]

        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(pypdf, "PdfReader", FakeReader)

    with pytest.raises(ValueError, match="too many content streams"):
        extract_text("large.pdf", b"%PDF-test")


def test_pdf_text_accumulation_stops_at_global_extraction_limit(monkeypatch) -> None:
    """Do not retain all page text before applying the document-wide character cap."""
    import pypdf

    class FakeContent:
        def get_data(self):
            return b"small content stream"

    class FakePage:
        def get(self, key):
            assert key == "/Contents"
            return [object()]

        def get_contents(self):
            return FakeContent()

        def extract_text(self):
            return "x" * 150_000

    class FakeReader:
        is_encrypted = False
        pages = [FakePage(), FakePage()]

        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(pypdf, "PdfReader", FakeReader)

    result = extract_text("long.pdf", b"%PDF-test")

    assert len(result) == 200_000


def test_pdf_decompression_filter_limits_are_lowered(monkeypatch) -> None:
    """Apply smaller decompression limits than pypdf's general-purpose defaults."""
    import pypdf
    import pypdf.filters

    class FakeReader:
        is_encrypted = False
        pages = []

        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(pypdf, "PdfReader", FakeReader)
    monkeypatch.setattr(
        pypdf.filters,
        "ZLIB_MAX_OUTPUT_LENGTH",
        75 * 1024 * 1024,
        raising=False,
    )

    with pytest.raises(ValueError, match="No readable text"):
        extract_text("empty.pdf", b"%PDF-test")

    assert pypdf.filters.ZLIB_MAX_OUTPUT_LENGTH <= 8 * 1024 * 1024
