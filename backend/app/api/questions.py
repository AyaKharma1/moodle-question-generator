from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_generation.factory import get_provider
from app.ai_generation.service import run_generation
from app.config import Settings, get_settings
from app.database import get_db
from app.models import (
    Answer,
    Question,
    QuestionReview,
    QuestionStatus,
    User,
)
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


@router.get("", response_model=list[QuestionOut])
def list_questions(
    status: Optional[str] = None,
    document_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[Question]:
    stmt = select(Question).where(Question.owner_id == current.id)
    if status:
        stmt = stmt.where(Question.status == status)
    if document_id:
        stmt = stmt.where(Question.document_id == document_id)
    return list(db.scalars(stmt.order_by(Question.id.desc())))


@router.get("/{qid}", response_model=QuestionOut)
def get_question(
    qid: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> Question:
    return _owned_question(db, qid, current)


@router.put("/{qid}", response_model=QuestionOut)
def update_question(
    qid: int,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Question:
    q = _owned_question(db, qid, current)

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

    created = persist_generated(db, owner=current, document=q.document, outcome=outcome)
    db.delete(q)  # replace the old one
    db.commit()
    db.refresh(created[0])
    return created[0]
