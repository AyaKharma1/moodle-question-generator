from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import ImportFile, User
from app.moodle_import import MoodleImportError
from app.question_bank.service import (
    DuplicateFileError,
    analyse,
    delete_import_file,
    import_moodle_file,
    overview,
)
from app.schemas.api import ImportFileOut, ImportSummaryOut
from app.security.deps import get_current_user

logger = logging.getLogger("app.bank")
router = APIRouter(prefix="/api/bank", tags=["question bank"])

MAX_FILES_PER_IMPORT = 20


def _owned_file(db: Session, file_id: int, user: User) -> ImportFile:
    f = db.get(ImportFile, file_id)
    if f is None or f.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return f


@router.post("/import", response_model=list[ImportSummaryOut])
async def import_files(
    files: list[UploadFile] = File(...),
    fach: str | None = Form(default=None, max_length=255),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current: User = Depends(get_current_user),
) -> list[ImportSummaryOut]:
    """Import one or more Moodle XML files. Each file succeeds or fails alone."""
    if len(files) > MAX_FILES_PER_IMPORT:
        raise HTTPException(status_code=400, detail=f"Maximal {MAX_FILES_PER_IMPORT} Dateien pro Import.")

    results: list[ImportSummaryOut] = []
    for upload in files:
        filename = os.path.basename(upload.filename or "import.xml")[:255]
        data = await upload.read()
        if not filename.lower().endswith(".xml"):
            results.append(ImportSummaryOut(filename=filename, error="Nur .xml-Dateien (Moodle-XML) sind erlaubt."))
            continue
        if len(data) > settings.max_upload_bytes:
            mb = settings.max_upload_bytes / (1024 * 1024)
            results.append(ImportSummaryOut(filename=filename, error=f"Datei ist größer als {mb:.0f} MB."))
            continue
        try:
            summary = import_moodle_file(db, owner=current, filename=filename, data=data, fach=fach)
        except (MoodleImportError, DuplicateFileError) as exc:
            db.rollback()
            results.append(ImportSummaryOut(filename=filename, error=str(exc)))
            continue
        db.commit()
        logger.info("user=%s imported %s: %d questions (%d new)",
                    current.id, filename, summary.total, summary.new)
        results.append(ImportSummaryOut(**summary.__dict__))
    return results


@router.get("/files", response_model=list[ImportFileOut])
def list_files(
    db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> list[ImportFile]:
    return list(db.scalars(
        select(ImportFile).where(ImportFile.owner_id == current.id).order_by(ImportFile.id.desc())
    ))


@router.delete("/files/{file_id}", status_code=204, response_class=Response)
def remove_file(
    file_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> Response:
    deleted = delete_import_file(db, _owned_file(db, file_id, current))
    db.commit()
    logger.info("user=%s removed import file=%s (%d questions deleted)", current.id, file_id, deleted)
    return Response(status_code=204)


@router.get("/overview")
def bank_overview(
    db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> dict:
    return overview(db, current)


@router.get("/analysis")
def bank_analysis(
    db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> dict:
    return analyse(db, current)
