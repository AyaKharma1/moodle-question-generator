"""Text extraction from uploaded documents.

Security principles applied here:
  * Uploaded content is untrusted. We validate the *actual* file format by its
    magic bytes, not just the filename extension (an attacker can rename a file).
  * We never execute document content - we only read text out of it.
  * Corrupt or unsupported files raise a clear :class:`ExtractionError` instead
    of crashing the request.
"""
from __future__ import annotations

import io
import zipfile

from pypdf import PdfReader
from pypdf.errors import PyPdfError

try:  # python-docx
    import docx  # type: ignore
except Exception:  # pragma: no cover - import guarded for safety
    docx = None  # type: ignore


class ExtractionError(ValueError):
    """Raised when text cannot be safely extracted from a document."""


# Magic-byte signatures used to confirm the real format.
_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"  # docx is a zip container


def detect_kind(data: bytes, filename: str) -> str:
    """Return one of 'pdf' | 'docx' | 'txt' based on content, cross-checking the
    filename extension. Raises if content and extension disagree or are unknown.
    """
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    if data.startswith(_PDF_MAGIC):
        kind = "pdf"
    elif data.startswith(_ZIP_MAGIC):
        # Only accept it as docx if it really contains a Word document part.
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = zf.namelist()
        except zipfile.BadZipFile as exc:
            raise ExtractionError("File looks like a zip but is corrupted.") from exc
        if "word/document.xml" not in names:
            raise ExtractionError("Zip file is not a Word (.docx) document.")
        kind = "docx"
    else:
        # Fall back to text only if it decodes as UTF-8/Latin-1 cleanly.
        if _looks_like_text(data):
            kind = "txt"
        else:
            raise ExtractionError("Unsupported or unrecognized file format.")

    # Cross-check: extension must match detected kind (defense in depth).
    expected_ext = {"pdf": ".pdf", "docx": ".docx", "txt": ".txt"}[kind]
    if ext and ext != expected_ext:
        raise ExtractionError(
            f"File content is {kind} but the extension is {ext!r}."
        )
    return kind


def _looks_like_text(data: bytes) -> bool:
    if b"\x00" in data[:4096]:
        return False
    for enc in ("utf-8", "latin-1"):
        try:
            data.decode(enc)
            return True
        except UnicodeDecodeError:
            continue
    return False


def extract_text(data: bytes, filename: str) -> str:
    """Extract plain text from document bytes. Raises ExtractionError on failure."""
    kind = detect_kind(data, filename)
    if kind == "pdf":
        text = _extract_pdf(data)
    elif kind == "docx":
        text = _extract_docx(data)
    else:
        text = _extract_txt(data)

    text = text.strip()
    if len(text) < 20:
        raise ExtractionError(
            "Too little text could be extracted from the document "
            "(it may be empty, scanned as images, or protected)."
        )
    return text


def _extract_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # Attempt empty-password decryption; refuse otherwise.
            if reader.decrypt("") == 0:
                raise ExtractionError("Encrypted PDFs are not supported.")
        parts = [(page.extract_text() or "") for page in reader.pages]
    except ExtractionError:
        raise
    except (PyPdfError, Exception) as exc:  # noqa: BLE001 - pypdf raises many types
        raise ExtractionError("The PDF file is corrupted or unreadable.") from exc
    return "\n".join(parts)


def _extract_docx(data: bytes) -> str:
    if docx is None:  # pragma: no cover
        raise ExtractionError("DOCX support is not available on the server.")
    try:
        document = docx.Document(io.BytesIO(data))
        parts = [p.text for p in document.paragraphs]
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError("The DOCX file is corrupted or unreadable.") from exc
    return "\n".join(parts)


def _extract_txt(data: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("The text file is not valid UTF-8 or Latin-1.")
