"""Optional demo mode: loads a clearly labelled fictitious question bank."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.demo.data import FACH, PREFIX, build_files
from app.models import ImportFile, User
from app.question_bank.service import DuplicateFileError, clear_analysis_cache, delete_import_file, import_moodle_file
from app.security.deps import get_current_user

logger = logging.getLogger("app.demo")
router = APIRouter(prefix="/api/demo", tags=["demo"])

NOTICE = ("Demo-Daten: vollständig erfundene Fragen zur Demonstration, keine echten Hochschuldaten. "
          "Sie lassen sich jederzeit wieder entfernen.")


def demo_files(db: Session, user: User) -> list[ImportFile]:
    return list(db.scalars(select(ImportFile).where(
        ImportFile.owner_id == user.id, ImportFile.filename.like(f"{PREFIX}%"))))


@router.get("")
def status(db: Session = Depends(get_db), current: User = Depends(get_current_user)) -> dict:
    files = demo_files(db, current)
    return {"loaded": bool(files), "files": [f.filename for f in files], "fach": FACH, "notice": NOTICE}


@router.post("/load")
def load(db: Session = Depends(get_db), current: User = Depends(get_current_user)) -> dict:
    if demo_files(db, current):
        raise HTTPException(status_code=409, detail="Die Demo-Daten sind bereits geladen.")
    loaded = []
    for name, data in build_files().items():
        try:
            summary = import_moodle_file(db, owner=current, filename=name, data=data, fach=None)
        except DuplicateFileError:
            continue
        loaded.append({"filename": name, "total": summary.total, "new": summary.new})
    db.commit()
    clear_analysis_cache()
    logger.info("user=%s loaded demo data (%d files)", current.id, len(loaded))
    return {"loaded": True, "files": loaded, "notice": NOTICE}


@router.delete("")
def remove(db: Session = Depends(get_db), current: User = Depends(get_current_user)) -> dict:
    """Removes only the demo files and the questions that exist nowhere else."""
    removed = sum(delete_import_file(db, f) for f in demo_files(db, current))
    db.commit()
    clear_analysis_cache()
    logger.info("user=%s removed demo data (%d questions)", current.id, removed)
    return {"loaded": False, "questions_removed": removed}
