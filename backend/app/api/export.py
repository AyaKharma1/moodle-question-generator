from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ExportHistory, Question, QuestionStatus, User
from app.moodle_export import ExportValidationError, export_questions
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

    # Preserve the requested order.
    by_id = {r.id: r for r in rows}
    ordered = [by_id[qid] for qid in payload.question_ids]

    try:
        xml = export_questions([row_to_domain(r) for r in ordered])
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
    rows = db.scalars(
        select(ExportHistory).where(ExportHistory.owner_id == current.id).order_by(ExportHistory.id.desc())
    )
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "question_count": r.question_count,
            "question_ids": r.question_ids,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
