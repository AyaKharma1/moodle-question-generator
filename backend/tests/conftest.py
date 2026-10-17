"""Test configuration.

Forces the app onto a local SQLite database and the mock AI provider BEFORE
any application module is imported, so no Postgres server or API key is needed
to run the suite. Each test gets a fresh schema.
"""
from __future__ import annotations

import os
import tempfile

# Must be set before importing app.* (engine is built from these at import).
_DB_PATH = os.path.join(tempfile.gettempdir(), "mqg_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["SECRET_KEY"] = "test-only-secret"
os.environ["AI_PROVIDER"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402,F401  (register tables on Base)
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _register_and_login(c: TestClient, email: str, password: str = "password123") -> str:
    c.post("/api/auth/register", json={"email": email, "password": password, "full_name": "Prof"})
    r = c.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def auth_client(client):
    token = _register_and_login(client, "prof@example.com")
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture
def make_user_client():
    """Factory for additional authenticated clients (for cross-user tests)."""
    def _make(email: str) -> TestClient:
        c = TestClient(app)
        token = _register_and_login(c, email)
        c.headers.update({"Authorization": f"Bearer {token}"})
        return c
    return _make
