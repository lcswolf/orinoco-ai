"""Text extraction for supported document uploads."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_CHARS = 200_000
MAX_PDF_STREAM_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGE_CONTENT_BYTES = 32 * 1024 * 1024
MAX_PDF_CONTENT_STREAMS_PER_PAGE = 4
MAX_OFFICE_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_OFFICE_ARCHIVE_ENTRIES = 2_000
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".xlsx", ".pptx"}


def extract_text(filename: str, data: bytes) -> str:
    """Validate an uploaded file and extract bounded UTF-8 text for document search."""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Supported file types are TXT, Markdown, PDF, DOCX, XLSX and PPTX.")
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("File is empty or exceeds the 10 MiB upload limit.")

    if extension in {".docx", ".xlsx", ".pptx"}:
        _validate_office_archive(data)

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



def _validate_office_archive(data: bytes) -> None:
    """Reject malformed, encrypted or oversized Office ZIP archives before parsing.

    Office formats are ZIP containers. A small upload can expand to a very
    large amount of XML or embedded media, so enforce both declared and actual
    uncompressed-size limits before handing the file to a document library.
    """
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_OFFICE_ARCHIVE_ENTRIES:
                raise ValueError("Office documents contain too many archive entries.")
            declared_size = sum(entry.file_size for entry in entries)
            if declared_size > MAX_OFFICE_ARCHIVE_BYTES:
                raise ValueError("Office document expands beyond the 25 MiB safety limit.")
            if any(entry.flag_bits & 0x1 for entry in entries):
                raise ValueError("Encrypted Office documents are not supported.")

            actual_size = 0
            for entry in entries:
                with archive.open(entry) as member:
                    while True:
                        chunk = member.read(64 * 1024)
                        if not chunk:
                            break
                        actual_size += len(chunk)
                        if actual_size > MAX_OFFICE_ARCHIVE_BYTES:
                            raise ValueError("Office document expands beyond the 25 MiB safety limit.")
    except ValueError:
        raise
    except (BadZipFile, OSError, RuntimeError) as exc:
        raise ValueError("This Office document is not a valid readable ZIP archive.") from exc


def _extract_pdf(data: bytes) -> str:
    """Extract bounded text from a non-encrypted PDF within stream and page limits."""
    from pypdf import PdfReader, filters

    # pypdf's default filter limits are generous for general-purpose tools.
    # Lower them for untrusted uploads so a compressed stream cannot expand
    # into hundreds of megabytes while running inside a small VPS container.
    for setting in (
        "MAX_DECLARED_STREAM_LENGTH",
        "MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH",
        "JBIG2_MAX_OUTPUT_LENGTH",
        "LZW_MAX_OUTPUT_LENGTH",
        "RUN_LENGTH_MAX_OUTPUT_LENGTH",
        "ZLIB_MAX_OUTPUT_LENGTH",
        "FLATE_MAX_BUFFER_SIZE",
    ):
        current = getattr(filters, setting, None)
        if isinstance(current, int):
            setattr(filters, setting, min(current, MAX_PDF_STREAM_BYTES))

    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported.")
        if len(reader.pages) > 100:
            raise ValueError("PDFs are limited to 100 pages.")

        parts: list[str] = []
        remaining_chars = MAX_EXTRACTED_CHARS
        for page in reader.pages:
            # Pages may store content in an array of separate streams. Bound
            # both the stream count and combined decoded content before parsing.
            raw_contents = page.get("/Contents")
            if raw_contents is not None and hasattr(raw_contents, "get_object"):
                raw_contents = raw_contents.get_object()
            if isinstance(raw_contents, (list, tuple)) and len(raw_contents) > MAX_PDF_CONTENT_STREAMS_PER_PAGE:
                raise ValueError("PDF pages contain too many content streams.")
            content_stream = page.get_contents()
            if content_stream is not None and len(content_stream.get_data()) > MAX_PDF_PAGE_CONTENT_BYTES:
                raise ValueError("PDF page content exceeds the 32 MiB safety limit.")

            page_text = page.extract_text() or ""
            if page_text and remaining_chars > 0:
                if parts:
                    parts.append("\n")
                    remaining_chars -= 1
                excerpt = page_text[:remaining_chars]
                parts.append(excerpt)
                remaining_chars -= len(excerpt)
            if remaining_chars <= 0:
                break
        return "".join(parts)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not read this PDF file within the parsing safety limits.") from exc


def _extract_docx(data: bytes) -> str:
    """Extract paragraph and table text from a DOCX document."""
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
    """Extract bounded cell values and always close the read-only workbook."""
    from openpyxl import load_workbook

    workbook = None
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
        return "\n".join(parts)
    except Exception as exc:
        raise ValueError("Could not read this XLSX workbook.") from exc
    finally:
        if workbook is not None:
            try:
                workbook.close()
            except Exception:
                # Preserve the original extraction error if closing a malformed
                # workbook also fails.
                pass


def _extract_pptx(data: bytes) -> str:
    """Extract text from presentation shapes while enforcing the slide limit."""
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
