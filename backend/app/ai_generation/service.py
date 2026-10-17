"""Generation service: the model-independent orchestration step.

It takes raw dicts from whichever provider is active, parses each into the
typed :class:`GeneratedQuestion` (rejecting malformed ones), then runs the
semantic validation (grounding + duplicate detection). It returns the
questions that parsed, each paired with its validation report, plus the list
of provider-level parse errors. Nothing here depends on a specific AI vendor.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import ValidationError

from app.ai_generation.base import AIProvider
from app.question_validation.validator import (
    QuestionValidation,
    validate_batch,
)
from app.schemas.question import GeneratedQuestion, GenerationRequest


@dataclass
class ReviewedQuestion:
    question: GeneratedQuestion
    validation: QuestionValidation


@dataclass
class GenerationOutcome:
    provider: str
    reviewed: list[ReviewedQuestion] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)


def run_generation(
    *,
    provider: AIProvider,
    source_text: str,
    request: GenerationRequest,
) -> GenerationOutcome:
    # Hard cap regardless of what the request or a prompt-injected document asks.
    capped = request.model_copy(update={"num_questions": min(request.num_questions, 50)})

    raw = provider.generate(source_text=source_text, request=capped)

    parsed: list[GeneratedQuestion] = []
    errors: list[str] = []
    for idx, item in enumerate(raw):
        try:
            parsed.append(GeneratedQuestion.model_validate(item))
        except ValidationError as exc:
            errors.append(f"question #{idx + 1}: {exc.error_count()} schema error(s)")

    reports = validate_batch(parsed, source_text=source_text)
    reviewed = [ReviewedQuestion(q, r) for q, r in zip(parsed, reports)]
    return GenerationOutcome(provider=provider.name, reviewed=reviewed, parse_errors=errors)
