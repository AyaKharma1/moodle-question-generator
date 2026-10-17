"""Core domain schemas for generated questions.

These Pydantic models are the single source of truth for the shape of a
question *inside* the application. The AI never produces Moodle XML directly;
it produces data that is parsed into these models, validated, and only then
converted to XML. Keeping one typed representation in the middle is what makes
the pipeline testable and the XML exporter independent of the AI model.

Pipeline:  Document -> Text -> AI -> (this schema) -> Validation -> Moodle XML
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class QuestionType(str, Enum):
    """Question types supported by the initial version."""

    multiple_choice = "multiple_choice"
    true_false = "true_false"
    short_answer = "short_answer"


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class Language(str, Enum):
    de = "de"
    en = "en"


class AnswerOption(BaseModel):
    """A single answer option.

    - multiple_choice: 2+ options, at least one with ``is_correct=True``.
    - true_false: exactly two options whose text is "true"/"false" (or the
      German "wahr"/"falsch"); exactly one correct.
    - short_answer: one or more accepted answers, all marked ``is_correct=True``.
    """

    text: str = Field(min_length=1, max_length=2000)
    is_correct: bool = False
    feedback: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("text", "feedback")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip()


class GeneratedQuestion(BaseModel):
    """One question as produced by the AI pipeline and stored by the app.

    Structural rules (types, counts, non-empty text) are enforced here so that
    malformed AI output is rejected as early as possible. Semantic checks
    (grounding in the source, duplicate detection) live in the
    ``question_validation`` module because they need the source material and
    the other questions as context.
    """

    question_type: QuestionType
    question_text: str = Field(min_length=3, max_length=5000)
    answers: list[AnswerOption] = Field(min_length=1)
    explanation: str = Field(min_length=1, max_length=5000)
    difficulty: Difficulty = Difficulty.medium
    language: Language = Language.de
    # Where in the source material this question is grounded. Used both as a
    # citation for the instructor and by the grounding check.
    source_reference: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("question_text", "explanation")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty or whitespace only")
        return v

    @model_validator(mode="after")
    def _check_type_rules(self) -> "GeneratedQuestion":
        n_correct = sum(1 for a in self.answers if a.is_correct)

        if self.question_type == QuestionType.multiple_choice:
            if len(self.answers) < 2:
                raise ValueError("multiple_choice needs at least 2 answer options")
            if n_correct < 1:
                raise ValueError("multiple_choice needs at least one correct answer")

        elif self.question_type == QuestionType.true_false:
            if len(self.answers) != 2:
                raise ValueError("true_false needs exactly 2 answer options")
            if n_correct != 1:
                raise ValueError("true_false needs exactly one correct answer")
            allowed = {"true", "false", "wahr", "falsch", "richtig"}
            for a in self.answers:
                if a.text.strip().lower() not in allowed:
                    raise ValueError(
                        "true_false options must be true/false (or wahr/falsch)"
                    )

        elif self.question_type == QuestionType.short_answer:
            if n_correct < 1:
                raise ValueError("short_answer needs at least one accepted answer")

        return self


class GenerationRequest(BaseModel):
    """Options an instructor chooses before generation."""

    document_id: Optional[int] = None
    question_type: QuestionType = QuestionType.multiple_choice
    num_questions: int = Field(default=5, ge=1, le=50)
    difficulty: Difficulty = Difficulty.medium
    language: Language = Language.de


class GenerationResult(BaseModel):
    """What the AI layer returns: parsed questions plus the raw provider name."""

    provider: str
    questions: list[GeneratedQuestion]
