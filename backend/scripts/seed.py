"""Optional seed script: creates a demo instructor and loads the sample lecture
as a document, so the app can be tried immediately.

Usage (with the app's environment active):
    python -m scripts.seed

It is idempotent: running it twice will not create duplicates.
Credentials are printed once; change them for anything beyond local demo use.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal, engine, Base
from app.models import Document, User
from app.security.auth import hash_password

DEMO_EMAIL = "demo@hs-bochum.example"
DEMO_PASSWORD = "demo-password-123"
SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "sample_lecture_de.txt"


def main() -> None:
    Base.metadata.create_all(engine)  # harmless if migrations already ran
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                hashed_password=hash_password(DEMO_PASSWORD),
                full_name="Demo Dozent:in",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created demo user {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"Demo user {DEMO_EMAIL} already exists")

        if SAMPLE.exists():
            exists = db.scalar(
                select(Document).where(
                    Document.owner_id == user.id,
                    Document.original_filename == SAMPLE.name,
                )
            )
            if exists is None:
                text = SAMPLE.read_text(encoding="utf-8")
                db.add(Document(
                    owner_id=user.id,
                    original_filename=SAMPLE.name,
                    stored_name="seed-" + SAMPLE.name,
                    extension=".txt",
                    size_bytes=len(text.encode("utf-8")),
                    text_content=text,
                ))
                db.commit()
                print(f"Loaded sample document: {SAMPLE.name}")
            else:
                print("Sample document already loaded")
    finally:
        db.close()


if __name__ == "__main__":
    main()
