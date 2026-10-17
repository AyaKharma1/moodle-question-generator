from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai_generation.base import AIProviderError
from app.ai_generation.factory import get_provider
from app.ai_generation.service import run_generation
from app.api.documents import _owned_document
from app.config import Settings, get_settings
from app.database import get_db
from app.models import User
from app.question_management.service import persist_generated
from app.schemas.api import GenerateRequest, GenerateResponse, QuestionOut
from app.schemas.question import GenerationRequest
from app.security.deps import get_current_user

logger = logging.getLogger("app.generation")
router = APIRouter(prefix="/api", tags=["generation"])


@router.post("/generate", response_model=GenerateResponse)
def generate_questions(
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current: User = Depends(get_current_user),
) -> GenerateResponse:
    document = _owned_document(db, payload.document_id, current)

    provider = get_provider(settings)
    req = GenerationRequest(
        document_id=document.id,
        question_type=payload.question_type,
        num_questions=payload.num_questions,
        difficulty=payload.difficulty,
        language=payload.language,
    )
    try:
        outcome = run_generation(
            provider=provider, source_text=document.text_content, request=req
        )
    except AIProviderError as exc:
        # Safe model-failure handling: a clear 502, no secret/stack leakage.
        logger.warning("AI provider failed for user=%s: %s", current.id, exc)
        raise HTTPException(status_code=502, detail=str(exc))

    created = persist_generated(db, owner=current, document=document, outcome=outcome)
    db.commit()
    for row in created:
        db.refresh(row)

    warnings = {
        row.id: item.validation.warnings
        for row, item in zip(created, outcome.reviewed)
        if item.validation.warnings
    }
    logger.info(
        "user=%s generated %d questions (provider=%s) from document=%s",
        current.id, len(created), outcome.provider, document.id,
    )
    return GenerateResponse(
        provider=outcome.provider,
        created=[QuestionOut.model_validate(r) for r in created],
        parse_errors=outcome.parse_errors,
        warnings=warnings,
    )
