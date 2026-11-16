"""Quality findings, contradictions and the lecturer's decisions."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Question, User
from app.question_bank import findings as fx
from app.question_bank.service import analysis_cached, findings_cached
from app.moodle_import.parser import plain_text
from app.moodle_import.report import type_name
from app.schemas.api import ConflictDecisionIn, DecisionIn
from app.security.deps import get_current_user

logger = logging.getLogger("app.quality")
router = APIRouter(prefix="/api/bank", tags=["quality"])


def catalog_view() -> dict:
    return {code: {"severity": k.severity, "severity_label": fx.SEVERITY_LABELS[k.severity],
                   "title": k.title, "why": k.why, "action": k.action}
            for code, k in fx.CATALOG.items()}


@router.get("/findings")
def list_findings(
    severity: str | None = Query(default=None, pattern="^(critical|review|info)$"),
    code: str | None = None,
    state: str = Query(default="open", pattern="^(open|done|all)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    """Findings by severity. ``state``: still open, already decided by the lecturer, or all."""
    if code is not None and code not in fx.CATALOG:
        raise HTTPException(status_code=422, detail="Unbekannte Art von Hinweis.")
    findings = fx.with_state(findings_cached(db, current), fx.decisions_of(db, current))
    summary = fx.summarize(findings)

    shown = [f for f in findings
             if (severity is None or f["severity"] == severity) and (code is None or f["code"] == code)
             and (state == "all" or (state == "done") == f["done"])]
    total = len(shown)
    chunk = shown[(page - 1) * page_size: page * page_size]

    rows = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_({f["question_id"] for f in chunk} or {-1})))}
    items = []
    for f in chunk:
        q = rows.get(f["question_id"])
        if q is None:
            continue
        text = plain_text(q.question_text)
        items.append({**f, "question": {
            "id": q.id, "name": q.name, "type_name": type_name(q.moodle_type or q.question_type),
            "fach": q.fach, "category": q.category, "text": text if len(text) <= 240 else text[:240] + "…",
            "files": [o["filename"] for o in q.origins[:3]],
            "decision": q.decision, "decision_note": q.decision_note,
        }})
    return {"summary": summary, "catalog": catalog_view(), "items": items,
            "total": total, "page": page, "page_size": page_size}


@router.get("/conflicts")
def list_conflicts(
    state: str = Query(default="open", pattern="^(open|done)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db), current: User = Depends(get_current_user),
) -> dict:
    """Contradicting variants of the same question, side by side. Open or already settled."""
    return fx.conflict_groups(db, current, analysis_cached(db, current), state, page, page_size)


@router.post("/conflicts/{text_fingerprint}/decide")
def decide_conflict(text_fingerprint: str, payload: ConflictDecisionIn,
                    db: Session = Depends(get_db), current: User = Depends(get_current_user)) -> dict:
    """Record which variant stays (``keep``) or that all of them stay. The app never chooses."""
    try:
        members = fx.decide_conflict(db, current, text_fingerprint, payload.keep, payload.note)
    except fx.DecisionError as exc:
        raise HTTPException(status_code=404 if "nicht gefunden" in str(exc) else 422, detail=str(exc))
    db.commit()
    logger.info("user=%s decided conflict %s (keep=%s)", current.id, text_fingerprint[:8], payload.keep)
    return {"ids": [m.id for m in members], "keep": payload.keep}


@router.post("/conflicts/{text_fingerprint}/reopen")
def reopen_conflict(text_fingerprint: str, db: Session = Depends(get_db), current: User = Depends(get_current_user)) -> dict:
    try:
        members = fx.reopen_conflict(db, current, text_fingerprint)
    except fx.DecisionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    return {"ids": [m.id for m in members]}


@router.get("/questions/{qid}/history")
def question_history(qid: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)) -> dict:
    """Everything the app knows about one question: sources, variants, similar questions, exports, findings."""
    analysis = analysis_cached(db, current)
    all_findings = fx.with_state(findings_cached(db, current), fx.decisions_of(db, current))
    result = fx.question_history(db, current, qid, all_findings, analysis)
    if result is None:
        raise HTTPException(status_code=404, detail="Frage nicht gefunden")
    return result


@router.post("/questions/{qid}/decision")
def decide_question(qid: int, payload: DecisionIn,
                    db: Session = Depends(get_db), current: User = Depends(get_current_user)) -> dict:
    """Mark a question as reviewed or excluded (or open again). Nothing is deleted."""
    try:
        q = fx.set_decision(db, current, qid, payload.state, payload.note)
    except fx.DecisionError as exc:
        raise HTTPException(status_code=404 if "nicht gefunden" in str(exc) else 422, detail=str(exc))
    db.commit()
    logger.info("user=%s set question=%s to %s", current.id, qid, payload.state)
    return {"id": q.id, "decision": q.decision, "decision_note": q.decision_note}
