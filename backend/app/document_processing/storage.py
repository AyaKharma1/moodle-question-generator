"""Secure storage of uploaded files.

Protections:
  * Extension allow-list + size limit enforced before anything touches disk.
  * The original filename is NEVER used to build the path on disk. We generate
    a random name, so path-traversal payloads like "../../etc/passwd" cannot
    escape the upload directory.
  * Files are written inside a dedicated upload directory and the final path is
    verified to still be inside it.
"""
from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings


class StorageError(ValueError):
    """Raised when an upload is rejected or cannot be stored safely."""


@dataclass
class StoredFile:
    stored_name: str
    path: str
    original_filename: str
    size_bytes: int
    extension: str


_SAFE_ORIGINAL = re.compile(r"[^A-Za-z0-9._ -]")


def _sanitize_original(name: str) -> str:
    """Keep a human-readable but harmless record of the original name."""
    name = os.path.basename(name or "")
    name = _SAFE_ORIGINAL.sub("_", name)
    return name[:200] or "upload"


def save_upload(data: bytes, filename: str, settings: Settings) -> StoredFile:
    if not data:
        raise StorageError("Uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        mb = settings.max_upload_bytes / (1024 * 1024)
        raise StorageError(f"File exceeds the maximum upload size of {mb:.0f} MB.")

    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in settings.allowed_extensions:
        allowed = ", ".join(sorted(settings.allowed_extensions))
        raise StorageError(f"File type {ext or '(none)'} not allowed. Allowed: {allowed}")

    upload_dir = Path(settings.upload_dir).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = (upload_dir / stored_name).resolve()

    # Final guard: the resolved destination must stay within upload_dir.
    if upload_dir not in dest.parents:
        raise StorageError("Resolved upload path escaped the upload directory.")

    dest.write_bytes(data)

    return StoredFile(
        stored_name=stored_name,
        path=str(dest),
        original_filename=_sanitize_original(filename),
        size_bytes=len(data),
        extension=ext,
    )
