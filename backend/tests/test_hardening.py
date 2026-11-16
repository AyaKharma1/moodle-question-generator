"""Upload limits, production start check and German messages."""
from __future__ import annotations

import asyncio
import io

import pytest

from app.config import DEFAULT_SECRET_KEY, Settings, get_settings
from app.document_processing.limits import read_limited


class _Stream:
    """Minimal stand-in for UploadFile that counts what was really read."""

    def __init__(self, total: int):
        self.left, self.read_bytes = total, 0

    async def read(self, size: int) -> bytes:
        block = min(size, self.left)
        self.left -= block
        self.read_bytes += block
        return b"x" * block


def test_read_limited_stops_early_instead_of_loading_everything():
    huge = _Stream(500 * 1024 * 1024)
    data, too_big = asyncio.run(read_limited(huge, 3 * 1024 * 1024))
    assert too_big and data == b""
    assert huge.read_bytes <= 4 * 1024 * 1024            # at most limit + one block, not 500 MB

    small = _Stream(1000)
    data, too_big = asyncio.run(read_limited(small, 3 * 1024 * 1024))
    assert not too_big and len(data) == 1000


def test_import_refuses_big_files_but_keeps_the_others(auth_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 2000)
    small = b'<quiz><question type="truefalse"><name><text>A</text></name><questiontext format="html"><text>kurz</text></questiontext><answer fraction="100"><text>true</text></answer><answer fraction="0"><text>false</text></answer></question></quiz>'
    big = small + b" " * 5000
    r = auth_client.post("/api/bank/import", files=[
        ("files", ("gross.xml", io.BytesIO(big), "text/xml")),
        ("files", ("klein.xml", io.BytesIO(small), "text/xml")),
    ]).json()
    assert "größer als" in r[0]["error"] and "kleinere Exporte" in r[0]["error"]
    assert r[1]["error"] is None and r[1]["new"] == 1


def test_import_has_a_total_budget(auth_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_bytes", 10_000)
    monkeypatch.setattr(settings, "max_import_total_bytes", 1200)
    def xml(n):
        return (f'<quiz><question type="truefalse"><name><text>F{n}</text></name><questiontext format="html">'
                f'<text>Frage Nummer {n} zum Thema{n}</text></questiontext><answer fraction="100"><text>true</text></answer>'
                f'<answer fraction="0"><text>false</text></answer></question></quiz>').encode() + b" " * 600
    r = auth_client.post("/api/bank/import", files=[("files", (f"{n}.xml", io.BytesIO(xml(n)), "text/xml")) for n in range(3)]).json()
    assert r[0]["error"] is None
    assert any("Gesamtgröße" in (x["error"] or "") for x in r[1:])


def test_oversized_request_is_refused_before_it_is_read(auth_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_request_bytes", 1000)
    r = auth_client.post("/api/bank/import", files={"files": ("a.xml", io.BytesIO(b"<quiz>" + b" " * 3000 + b"</quiz>"), "text/xml")})
    assert r.status_code == 413 and "zu groß" in r.json()["detail"]


def test_production_refuses_to_start_with_a_weak_secret():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings(environment="production", secret_key=DEFAULT_SECRET_KEY).assert_production_safe()
    with pytest.raises(RuntimeError):
        Settings(environment="production", secret_key="kurz").assert_production_safe()
    Settings(environment="production", secret_key="x" * 40).assert_production_safe()      # fine
    Settings(environment="development", secret_key=DEFAULT_SECRET_KEY).assert_production_safe()   # dev may use it


def test_messages_the_professor_sees_are_german(auth_client):
    from fastapi.testclient import TestClient
    from app.main import app
    anonymous = TestClient(app)           # `client` and `auth_client` share one object, so use a separate one
    assert "abgelaufen" in anonymous.get("/api/questions").json()["detail"]
    bad = anonymous.post("/api/auth/login", data={"username": "x@y.de", "password": "falsch1234"})
    assert bad.status_code == 401 and "falsch" in bad.json()["detail"]
    assert auth_client.get("/api/questions/99999").json()["detail"] == "Frage nicht gefunden"
    assert auth_client.get("/api/documents/99999").json()["detail"] == "Dokument nicht gefunden"
    dup = auth_client.post("/api/auth/register", json={"email": "prof@example.com", "password": "password123"})
    assert dup.status_code == 409 and "bereits registriert" in dup.json()["detail"]
