import io

import docx
import pytest

from app.config import Settings
from app.document_processing import (
    ExtractionError,
    StorageError,
    extract_text,
    save_upload,
)


def _settings(tmp_path):
    return Settings(upload_dir=str(tmp_path), max_upload_bytes=1024)


# ---------------- extraction ----------------

def test_extract_txt():
    data = "Ein Primärschlüssel identifiziert einen Datensatz eindeutig.".encode("utf-8")
    assert "Primärschlüssel" in extract_text(data, "lecture.txt")


def test_extract_docx():
    d = docx.Document()
    d.add_paragraph("Die Normalisierung reduziert Redundanz in Datenbanken.")
    buf = io.BytesIO()
    d.save(buf)
    assert "Normalisierung" in extract_text(buf.getvalue(), "lecture.docx")


def test_corrupt_pdf_raises_clear_error():
    with pytest.raises(ExtractionError):
        extract_text(b"%PDF-1.4 this is not really a pdf body", "broken.pdf")


def test_extension_content_mismatch_rejected():
    # Real text content but claims to be a PDF.
    with pytest.raises(ExtractionError):
        extract_text(b"just some long enough plain text here", "fake.pdf")


def test_unsupported_binary_rejected():
    with pytest.raises(ExtractionError):
        extract_text(b"\x00\x01\x02\x03\x04binarynonsense", "x.txt")


def test_too_little_text_rejected():
    with pytest.raises(ExtractionError):
        extract_text(b"short", "tiny.txt")


# ---------------- storage / malicious uploads ----------------

def test_oversized_upload_rejected(tmp_path):
    big = b"x" * 2048
    with pytest.raises(StorageError):
        save_upload(big, "big.txt", _settings(tmp_path))


def test_disallowed_extension_rejected(tmp_path):
    with pytest.raises(StorageError):
        save_upload(b"hello world", "malware.exe", _settings(tmp_path))


def test_path_traversal_filename_is_neutralized(tmp_path):
    stored = save_upload(b"safe content here", "../../../../etc/passwd.txt", _settings(tmp_path))
    # Stored under a random name, inside the upload dir, not at the traversal path.
    assert stored.path.startswith(str(tmp_path))
    assert "etc" not in stored.stored_name
    assert stored.stored_name.endswith(".txt")


def test_empty_upload_rejected(tmp_path):
    with pytest.raises(StorageError):
        save_upload(b"", "empty.txt", _settings(tmp_path))
