"""Reading uploads without trusting their size.

``await upload.read()`` loads the whole file into memory before any size check
could run, so one huge upload could exhaust the server. ``read_limited`` reads
in small blocks and stops as soon as the limit is exceeded.
"""
from __future__ import annotations

from fastapi import UploadFile

CHUNK_BYTES = 1024 * 1024


async def read_limited(upload: UploadFile, limit: int) -> tuple[bytes, bool]:
    """Read at most ``limit`` bytes. Returns ``(data, too_big)``.

    When the file is too big nothing more is read and ``data`` is empty.
    """
    parts: list[bytes] = []
    size = 0
    while True:
        block = await upload.read(CHUNK_BYTES)
        if not block:
            return b"".join(parts), False
        size += len(block)
        if size > limit:
            return b"", True
        parts.append(block)


def megabytes(n: int) -> str:
    return f"{n / (1024 * 1024):.0f}"
