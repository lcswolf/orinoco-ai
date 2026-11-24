"""Text extraction for supported document uploads."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_CHARS = 200_000
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".xlsx", ".pptx"}


def extract_text(filename: str, data: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Supported file types are TXT, Markdown, PDF, DOCX, XLSX and PPTX.")
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("File is empty or exceeds the 10 MiB upload limit.")

    if extension in {".txt", ".md"}:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Text documents must use UTF-8 encoding.") from exc
    elif extension == ".pdf":
        text = _extract_pdf(data)
    elif extension == ".docx":
        text = _extract_docx(data)
    elif extension == ".xlsx":
        text = _extract_xlsx(data)
    else:
        text = _extract_pptx(data)

    cleaned = "\n".join(line.rstrip() for line in text.replace("\x00", "").splitlines()).strip()
    if not cleaned:
        raise ValueError("No readable text was found in this file.")
    return cleaned[:MAX_EXTRACTED_CHARS]


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported.")
        if len(reader.pages) > 100:
            raise ValueError("PDFs are limited to 100 pages.")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not read this PDF file.") from exc


def _extract_docx(data: bytes) -> str:
    from docx import Document

    try:
        document = Document(BytesIO(data))
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    except Exception as exc:
        raise ValueError("Could not read this DOCX file.") from exc


def _extract_xlsx(data: bytes) -> str:
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
        parts: list[str] = []
        cells_seen = 0
        for sheet in workbook.worksheets[:30]:
            parts.append(f"Sheet: {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                values = [str(value) for value in row if value is not None]
                if values:
                    parts.append(" | ".join(values))
                cells_seen += len(row)
                if cells_seen >= 20000:
                    parts.append("[Extraction stopped at the 20,000-cell limit.]")
                    break
            if cells_seen >= 20000:
                break
        workbook.close()
        return "\n".join(parts)
    except Exception as exc:
        raise ValueError("Could not read this XLSX workbook.") from exc


def _extract_pptx(data: bytes) -> str:
    from pptx import Presentation

    try:
        presentation = Presentation(BytesIO(data))
        if len(presentation.slides) > 200:
            raise ValueError("PowerPoint files are limited to 200 slides.")
        parts: list[str] = []
        for index, slide in enumerate(presentation.slides, start=1):
            parts.append(f"Slide {index}")
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    value = shape.text.strip()
                    if value:
                        parts.append(value)
        return "\n".join(parts)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not read this PPTX presentation.") from exc
