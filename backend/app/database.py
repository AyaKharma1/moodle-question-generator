"""Database engine, session factory and the FastAPI session dependency.

The same ORM models run on PostgreSQL (docker-compose, production) and on
SQLite (fast local unit tests). We only use portable column types so no
database-specific features leak into the models.

All access goes through SQLAlchemy's ORM/Core, which uses parameterized
queries - the application never builds SQL by string concatenation, so SQL
injection is structurally prevented.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(database_url: str):
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    """Yield a database session and always close it (FastAPI dependency)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
