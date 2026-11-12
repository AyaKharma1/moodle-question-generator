from __future__ import annotations

import logging
import os

import math
from collections import defaultdict

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.database import get_db
from app.models import ImportFile, Question, QuestionOccurrence, QuestionStatus, User
from app.moodle_import import MoodleImportError
from app.question_bank.search import (
    FLAGS,
    SORTS,
    BankFilter,
    all_flagged_ids,
    apply_filters,
    facets,
    flagged_question_ids,
    order_by,
)
from app.question_bank.service import (
    DuplicateFileError,
    analyse,
    delete_import_file,
    export_map,
    import_moodle_file,
    overview,
)
from app.schemas.api import BankPage, ImportFileOut, ImportSummaryOut, QuestionOut
from app.security.deps import get_current_user

logger = logging.getLogger("app.bank")
router = APIRouter(prefix="/api/bank", tags=["question bank"])

MAX_FILES_PER_IMPORT = 20
MAX_SELECTABLE = 5000


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
) -> list[ImportFileOut]:
    files = list(db.scalars(
        select(ImportFile).where(ImportFile.owner_id == current.id).order_by(ImportFile.id.desc())
    ))
    cats: dict[int, list[str]] = defaultdict(list)
    for file_id, category in db.execute(
        select(QuestionOccurrence.import_file_id, QuestionOccurrence.category)
        .where(QuestionOccurrence.import_file_id.in_([f.id for f in files] or [-1]))
        .distinct()
    ):
        if category:
            cats[file_id].append(category)
    return [
        ImportFileOut.model_validate(f).model_copy(update={"categories": sorted(cats[f.id])})
        for f in files
    ]


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


# ---------------------------------------------------------------- search

def bank_filter(
    q: str | None = Query(default=None, max_length=200),
    fach: str | None = None,
    category: str | None = None,
    file: int | None = None,
    source: str | None = Query(default=None, pattern="^(import|ai)$"),
    type: str | None = Query(default=None, max_length=32),
    flag: str | None = None,
    exported: str | None = Query(default=None, pattern="^(yes|no)$"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> BankFilter:
    if flag is not None and flag not in FLAGS:
        raise HTTPException(status_code=422, detail=f"flag muss einer von {', '.join(FLAGS)} sein")
    f = BankFilter(q=q, fach=fach, category=category, import_file_id=file, source=source,
                   qtype=type, flag=flag, exported=exported)
    if flag:
        f.flagged_ids = flagged_question_ids(analyse(db, current), flag)
    if exported:
        f.exported_ids = set(export_map(db, current))
    return f


@router.get("/questions", response_model=BankPage)
def search_questions(
    f: BankFilter = Depends(bank_filter),
    sort: str = "newest",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> BankPage:
    """Search, filter, sort and page through the whole bank."""
    if sort not in SORTS:
        raise HTTPException(status_code=422, detail=f"sort muss einer von {', '.join(SORTS)} sein")

    base = apply_filters(select(Question), db, current, f)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    pages = max(1, math.ceil(total / page_size))
    page = min(page, pages)
    rows = db.scalars(
        order_by(base, sort).options(selectinload(Question.answers))
        .limit(page_size).offset((page - 1) * page_size)
    ).all()

    exports = export_map(db, current)
    return BankPage(
        items=[QuestionOut.model_validate(r).model_copy(update={"exported_in": exports.get(r.id, [])})
               for r in rows],
        total=total, page=page, page_size=page_size, pages=pages,
        facets=facets(db, current, f),
    )


@router.get("/selectable-ids")
def selectable_ids(
    f: BankFilter = Depends(bank_filter),
    sort: str = "newest",
    exclude_flagged: bool = False,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    """Ids of every exportable (approved) question matching the filters.

    Lets the UI select "all N results" across pages, or draw a random sample.
    ``exclude_flagged`` leaves out contradicting, near-duplicate and broken
    questions, which should not go into a test unchecked.
    """
    if sort not in SORTS:
        raise HTTPException(status_code=422, detail=f"sort muss einer von {', '.join(SORTS)} sein")
    stmt = apply_filters(select(Question.id), db, current, f).where(
        Question.status == QuestionStatus.approved.value
    )
    ids = list(db.scalars(order_by(stmt, sort).limit(MAX_SELECTABLE + 1)))
    truncated = len(ids) > MAX_SELECTABLE
    ids = ids[:MAX_SELECTABLE]
    if exclude_flagged:
        flagged = all_flagged_ids(analyse(db, current))
        ids = [i for i in ids if i not in flagged]
    return {"ids": ids, "total": len(ids), "truncated": truncated}
