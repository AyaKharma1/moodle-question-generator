from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.ai_generation.factory import get_provider
from app.ai_generation.service import run_generation
from app.config import Settings, get_settings
from app.database import get_db
from app.models import (
    Answer,
    Question,
    QuestionOccurrence,
    QuestionReview,
    QuestionStatus,
    User,
)
from app.question_bank.search import build_search_text
from app.question_bank.service import export_map
from app.question_management.service import persist_generated, row_to_domain
from app.schemas.api import QuestionOut, QuestionUpdate, ReviewAction
from app.schemas.question import (
    AnswerOption,
    Difficulty,
    GeneratedQuestion,
    GenerationRequest,
    Language,
    QuestionType,
)
from app.security.deps import get_current_user

logger = logging.getLogger("app.questions")
router = APIRouter(prefix="/api/questions", tags=["questions"])


def _owned_question(db: Session, qid: int, user: User) -> Question:
    q = db.get(Question, qid)
    if q is None or q.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Question not found")
    return q


def _reject_imported(q: Question) -> None:
    # Moodle stays the source of truth for imported questions: editing them
    # here would silently diverge from the Moodle bank.
    if not q.ai_generated:
        raise HTTPException(
            status_code=409,
            detail="Importierte Fragen werden in Moodle bearbeitet, nicht hier.",
        )


@router.get("", response_model=list[QuestionOut])
def list_questions(
    status: Optional[str] = None,
    document_id: Optional[int] = None,
    fach: Optional[str] = None,
    category: Optional[str] = None,
    import_file_id: Optional[int] = None,
    source: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[QuestionOut]:
    stmt = select(Question).where(Question.owner_id == current.id)
    if status:
        stmt = stmt.where(Question.status == status)
    if document_id:
        stmt = stmt.where(Question.document_id == document_id)
    if fach:
        stmt = stmt.where(Question.fach == fach)
    if category:
        stmt = stmt.where(Question.category == category)
    if import_file_id:
        stmt = stmt.where(Question.occurrences.any(QuestionOccurrence.import_file_id == import_file_id))
    if source == "import":
        stmt = stmt.where(Question.ai_generated.is_(False))
    elif source == "ai":
        stmt = stmt.where(Question.ai_generated.is_(True))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Question.question_text.ilike(pattern), Question.name.ilike(pattern)))

    exports = export_map(db, current)
    return [
        QuestionOut.model_validate(row).model_copy(update={"exported_in": exports.get(row.id, [])})
        for row in db.scalars(stmt.options(selectinload(Question.answers)).order_by(Question.id.desc()))
    ]


@router.get("/{qid}", response_model=QuestionOut)
def get_question(
    qid: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> QuestionOut:
    row = _owned_question(db, qid, current)
    return QuestionOut.model_validate(row).model_copy(
        update={"exported_in": export_map(db, current).get(row.id, [])}
    )


@router.put("/{qid}", response_model=QuestionOut)
def update_question(
    qid: int,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Question:
    q = _owned_question(db, qid, current)
    _reject_imported(q)

    # Build the prospective edited question and re-validate structurally, so an
    # instructor edit can never produce an invalid (non-exportable) question.
    new_answers = payload.answers if payload.answers is not None else [
        AnswerOption(text=a.text, is_correct=a.is_correct, feedback=a.feedback)
        for a in q.answers
    ]
    try:
        GeneratedQuestion(
            question_type=QuestionType(q.question_type),
            question_text=payload.question_text or q.question_text,
            answers=[AnswerOption(**a.model_dump()) if hasattr(a, "model_dump") else a
                     for a in new_answers],
            explanation=payload.explanation or q.explanation,
            difficulty=payload.difficulty or Difficulty(q.difficulty),
            language=payload.language or Language(q.language),
        )
    except ValidationError as exc:
        messages = [
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=messages)

    if payload.question_text is not None:
        q.question_text = payload.question_text
    if payload.explanation is not None:
        q.explanation = payload.explanation
    if payload.difficulty is not None:
        q.difficulty = payload.difficulty.value
    if payload.language is not None:
        q.language = payload.language.value
    if payload.answers is not None:
        q.answers.clear()
        for pos, a in enumerate(payload.answers):
            q.answers.append(
                Answer(text=a.text, is_correct=a.is_correct, feedback=a.feedback, position=pos)
            )
    q.search_text = build_search_text(q)
    # An edited question returns to pending review.
    q.status = QuestionStatus.pending.value
    db.commit()
    db.refresh(q)
    return q


@router.delete("/{qid}", status_code=204, response_class=Response)
def delete_question(
    qid: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> Response:
    q = _owned_question(db, qid, current)
    db.delete(q)
    db.commit()
    return Response(status_code=204)


@router.post("/{qid}/review", response_model=QuestionOut)
def review_question(
    qid: int,
    payload: ReviewAction,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Question:
    q = _owned_question(db, qid, current)
    q.status = (
        QuestionStatus.approved.value
        if payload.action == "approve"
        else QuestionStatus.rejected.value
    )
    db.add(QuestionReview(
        question_id=q.id, reviewer_id=current.id, action=q.status, comment=payload.comment
    ))
    db.commit()
    db.refresh(q)
    logger.info("user=%s %s question=%s", current.id, q.status, q.id)
    return q


@router.post("/{qid}/regenerate", response_model=QuestionOut)
def regenerate_question(
    qid: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current: User = Depends(get_current_user),
) -> Question:
    q = _owned_question(db, qid, current)
    _reject_imported(q)
    if q.document_id is None or q.document is None:
        raise HTTPException(status_code=409, detail="Question has no source document to regenerate from")

    provider = get_provider(settings)
    req = GenerationRequest(
        document_id=q.document_id,
        question_type=QuestionType(q.question_type),
        num_questions=1,
        difficulty=Difficulty(q.difficulty),
        language=Language(q.language),
    )
    outcome = run_generation(provider=provider, source_text=q.document.text_content, request=req)
    if not outcome.reviewed:
        raise HTTPException(status_code=502, detail="Could not regenerate a question")

    created = persist_generated(
        db, owner=current, document=q.document, outcome=outcome,
        fach=q.fach, category=q.category,
    )
    db.delete(q)  # replace the old one
    db.commit()
    db.refresh(created[0])
    return created[0]
