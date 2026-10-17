"""Pydantic schemas for the HTTP API (requests and responses).

Kept separate from the domain schema in ``question.py`` so the wire format can
evolve independently from the internal model and the exporter.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.question import Difficulty, Language, QuestionType


# ---------------- auth ----------------

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: Optional[str]
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------- documents ----------------

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    original_filename: str
    extension: str
    size_bytes: int
    created_at: datetime


# ---------------- questions ----------------

class AnswerIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    is_correct: bool = False
    feedback: Optional[str] = Field(default=None, max_length=2000)


class AnswerOut(AnswerIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int


class QuestionUpdate(BaseModel):
    """Instructor edits. All fields optional; answers replace the full set."""
    question_text: Optional[str] = Field(default=None, min_length=3, max_length=5000)
    explanation: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    difficulty: Optional[Difficulty] = None
    language: Optional[Language] = None
    answers: Optional[list[AnswerIn]] = None


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: Optional[int]
    question_type: QuestionType
    question_text: str
    explanation: str
    difficulty: Difficulty
    language: Language
    status: str
    grounding_score: float
    is_duplicate: bool
    ai_generated: bool
    answers: list[AnswerOut]
    created_at: datetime
    updated_at: datetime


class GenerateRequest(BaseModel):
    document_id: int
    question_type: QuestionType = QuestionType.multiple_choice
    num_questions: int = Field(default=5, ge=1, le=50)
    difficulty: Difficulty = Difficulty.medium
    language: Language = Language.de


class GenerateResponse(BaseModel):
    provider: str
    created: list[QuestionOut]
    parse_errors: list[str]
    warnings: dict[int, list[str]]  # question_id -> warnings


class ReviewAction(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    comment: Optional[str] = Field(default=None, max_length=1000)


class ExportRequest(BaseModel):
    question_ids: list[int] = Field(min_length=1)
    filename: Optional[str] = Field(default=None, max_length=100)
