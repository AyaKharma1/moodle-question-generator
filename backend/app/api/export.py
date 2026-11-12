from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ExportHistory, Question, QuestionStatus, User
from app.moodle_export import ExportItem, ExportValidationError, category_path_for, export_bank, with_prefix
from app.question_management.service import row_to_domain
from app.schemas.api import ExportRequest
from app.security.deps import get_current_user

logger = logging.getLogger("app.export")
router = APIRouter(prefix="/api/export", tags=["export"])

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def _safe_filename(name: str | None) -> str:
    base = _SAFE_NAME.sub("_", (name or "moodle_questions").strip()) or "moodle_questions"
    if not base.endswith(".xml"):
        base += ".xml"
    return base[:100]


def _export_item(q: Question, prefix: str | None = None) -> ExportItem:
    # Imported questions go back exactly as Moodle exported them; their
    # original category path is kept so Moodle restores the same structure.
    if q.raw_xml:
        return ExportItem(
            category_path=with_prefix(q.category_path or category_path_for(q.fach, q.category), prefix),
            raw_xml=q.raw_xml,
        )
    return ExportItem(
        category_path=with_prefix(category_path_for(q.fach, q.category), prefix),
        question=row_to_domain(q),
        name=q.name,
    )


@router.post("")
def export_xml(
    payload: ExportRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Response:
    rows = list(
        db.scalars(
            select(Question).where(
                Question.id.in_(payload.question_ids),
                Question.owner_id == current.id,
            )
        )
    )
    found_ids = {r.id for r in rows}
    missing = [qid for qid in payload.question_ids if qid not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"Questions not found: {missing}")

    # HARD RULE: only instructor-approved questions may be exported. The AI
    # never publishes anything on its own.
    not_approved = [r.id for r in rows if r.status != QuestionStatus.approved.value]
    if not_approved:
        raise HTTPException(
            status_code=409,
            detail=f"These questions are not approved and cannot be exported: {not_approved}",
        )

    # Preserve the requested order; a question selected twice is written once.
    by_id = {r.id: r for r in rows}
    ordered = [by_id[qid] for qid in dict.fromkeys(payload.question_ids)]

    try:
        xml = export_bank([_export_item(r, payload.category_prefix) for r in ordered])
    except ExportValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    filename = _safe_filename(payload.filename)
    db.add(ExportHistory(
        owner_id=current.id,
        filename=filename,
        question_count=len(ordered),
        question_ids=[r.id for r in ordered],
    ))
    db.commit()
    logger.info("user=%s exported %d questions to %s", current.id, len(ordered), filename)

    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/history")
def export_history(
    db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> list[dict]:
    rows = list(db.scalars(
        select(ExportHistory).where(ExportHistory.owner_id == current.id).order_by(ExportHistory.id.desc())
    ))
    wanted = {qid for r in rows for qid in r.question_ids or []}
    names = dict(db.execute(
        select(Question.id, Question.name).where(Question.owner_id == current.id, Question.id.in_(wanted or {-1}))
    ).all())
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "question_count": r.question_count,
            "question_ids": r.question_ids,
            # names let the history be searched by question without loading the bank
            "question_names": [names.get(qid) or "gelöschte Frage" for qid in r.question_ids or []],
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
