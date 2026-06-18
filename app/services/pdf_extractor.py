"""PDF text extraction for uploaded resumes."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract readable text from a PDF upload.

    This works best for text-based PDFs. Scanned image resumes require OCR,
    which is intentionally outside this MVP.
    """
    reader = PdfReader(BytesIO(pdf_bytes))
    page_text = []

    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            page_text.append(text.strip())

    return "\n\n".join(page_text).strip()
