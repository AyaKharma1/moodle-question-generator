"""Persistence and conversion helpers for questions.

Bridges three representations:
  * GeneratedQuestion (domain schema, used by AI + exporter)
  * ORM rows (Question/Answer/QuestionSource, used for storage & review)
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai_generation.service import GenerationOutcome
from app.models import (
    Answer,
    Document,
    Question,
    QuestionSource,
    QuestionStatus,
    User,
)
from app.schemas.question import (
    AnswerOption,
    Difficulty,
    GeneratedQuestion,
    Language,
    QuestionType,
)


def persist_generated(
    db: Session, *, owner: User, document: Document, outcome: GenerationOutcome
) -> list[Question]:
    """Store generated questions as PENDING, with answers, source and snapshot."""
    created: list[Question] = []
    for item in outcome.reviewed:
        gq = item.question
        row = Question(
            owner_id=owner.id,
            document_id=document.id,
            question_type=gq.question_type.value,
            question_text=gq.question_text,
            explanation=gq.explanation,
            difficulty=gq.difficulty.value,
            language=gq.language.value,
            status=QuestionStatus.pending.value,
            grounding_score=item.validation.grounding_score,
            is_duplicate=item.validation.is_duplicate,
            ai_generated=True,
            original_snapshot=gq.model_dump(mode="json"),
        )
        for pos, a in enumerate(gq.answers):
            row.answers.append(
                Answer(text=a.text, is_correct=a.is_correct, feedback=a.feedback, position=pos)
            )
        if gq.source_reference:
            row.sources.append(
                QuestionSource(
                    document_id=document.id,
                    snippet=gq.source_reference,
                    grounding_score=item.validation.grounding_score,
                )
            )
        db.add(row)
        created.append(row)

    db.flush()  # assign ids without committing yet
    return created


def row_to_domain(q: Question) -> GeneratedQuestion:
    """Convert a stored question into the domain model the exporter consumes."""
    return GeneratedQuestion(
        question_type=QuestionType(q.question_type),
        question_text=q.question_text,
        answers=[
            AnswerOption(text=a.text, is_correct=a.is_correct, feedback=a.feedback)
            for a in q.answers
        ],
        explanation=q.explanation,
        difficulty=Difficulty(q.difficulty),
        language=Language(q.language),
        source_reference=(q.sources[0].snippet if q.sources else None),
    )
