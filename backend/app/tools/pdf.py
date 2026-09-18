"""PDF text extract with retries. Fail closed on empty/unreadable pages."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class PdfExtractError(ValueError):
    """Raised when a PDF cannot yield usable clinical text."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
    retry=retry_if_exception_type((OSError, ConnectionError)),
    reraise=True,
)
def extract_pdf_text(source: bytes | str | Path, min_chars: int = 40) -> str:
    """Extract text from a PDF path or in-memory bytes with retries."""
    if isinstance(source, (str, Path)):
        reader = PdfReader(str(source))
    else:
        reader = PdfReader(BytesIO(source))

    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if len(text) < min_chars:
        raise PdfExtractError("Paste the note as text.")
    return text
