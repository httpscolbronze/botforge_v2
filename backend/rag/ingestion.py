"""Document text extraction for PDF, DOCX, TXT and CSV.

Uploaded files are untrusted: we only ever read text out of them here, and the
result is later delivered to the model inside explicit "untrusted data" markers.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from backend.rag.chunking import normalise_text

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".md"}
MAX_PAGES = 400
MAX_CHARS = 4_000_000


class IngestionError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def extract_pages(path: Path, extension: str) -> list[dict[str, Any]]:
    extension = extension.lower()
    try:
        if extension == ".pdf":
            return _extract_pdf(path)
        if extension == ".docx":
            return _extract_docx(path)
        if extension in {".txt", ".md"}:
            return _extract_text(path)
        if extension == ".csv":
            return _extract_csv(path)
    except IngestionError:
        raise
    except Exception as exc:  # pragma: no cover - library specific failures
        raise IngestionError(f"Could not read the {extension} file: {exc}", 422) from exc
    raise IngestionError(
        f"Unsupported file type '{extension}'. Supported: PDF, DOCX, TXT, CSV, MD.", 415
    )


def _truncate(text: str, total: list[int]) -> str:
    total[0] += len(text)
    if total[0] > MAX_CHARS:
        raise IngestionError("Document is too large to index (over 4M characters).", 413)
    return text


def _extract_pdf(path: Path) -> list[dict[str, Any]]:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover
        raise IngestionError(
            "PyMuPDF is not installed on the server, so PDFs cannot be indexed. "
            "Run `pip install -r backend/requirements.txt`.",
            503,
        ) from exc

    pages: list[dict[str, Any]] = []
    total = [0]
    with fitz.open(path) as document:
        if document.is_encrypted:
            raise IngestionError("This PDF is password protected and cannot be indexed.", 422)
        if document.page_count > MAX_PAGES:
            raise IngestionError(
                f"PDF has {document.page_count} pages; the limit is {MAX_PAGES}.", 413
            )
        for page_number, page in enumerate(document, start=1):
            text = _truncate(normalise_text(page.get_text("text")), total)
            if text:
                pages.append({"page": page_number, "text": text})
    if not pages:
        raise IngestionError(
            "No selectable text found in this PDF. Scanned PDFs need OCR, which is not part "
            "of the MVP.",
            422,
        )
    return pages


def _extract_docx(path: Path) -> list[dict[str, Any]]:
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover
        raise IngestionError(
            "python-docx is not installed on the server, so DOCX files cannot be indexed. "
            "Run `pip install -r backend/requirements.txt`.",
            503,
        ) from exc

    document = docx.Document(str(path))
    blocks: list[str] = []
    for paragraph in document.paragraphs:
        text = normalise_text(paragraph.text)
        if text:
            blocks.append(text)
    for table in document.tables:
        for row in table.rows:
            cells = [normalise_text(cell.text) for cell in row.cells]
            line = " | ".join(cell for cell in cells if cell)
            if line:
                blocks.append(line)
    text = _truncate("\n\n".join(blocks), [0])
    if not text:
        raise IngestionError("This DOCX file contains no extractable text.", 422)
    # DOCX has no reliable page numbers, so citations say "document" instead.
    return [{"page": None, "text": text}]


def _extract_text(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - latin-1 always decodes
        raise IngestionError("Could not decode the text file.", 422)
    text = _truncate(normalise_text(text), [0])
    if not text:
        raise IngestionError("This text file is empty.", 422)
    return [{"page": None, "text": text}]


def _extract_csv(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = raw.decode("latin-1")
    reader = csv.reader(io.StringIO(decoded))
    rows = []
    for index, row in enumerate(reader):
        if index > 20_000:
            raise IngestionError("CSV has more than 20,000 rows; please split it.", 413)
        cells = [cell.strip() for cell in row]
        if any(cells):
            rows.append(" | ".join(cells))
    text = _truncate(normalise_text("\n".join(rows)), [0])
    if not text:
        raise IngestionError("This CSV file is empty.", 422)
    if not rows:
        raise IngestionError("This CSV file has no readable rows.", 422)
    header = rows[0].split(" | ")
    body = "\n".join(rows[1:]) if len(rows) > 1 else ""
    if header and body:
        text = f"CSV columns: {', '.join(header)}\n\n{body}"
    return [{"page": None, "text": text}]
