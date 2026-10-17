"""Semantic validation of AI output.

Structural validity (field types, option counts) is already guaranteed by the
Pydantic schema. This module adds the checks that need *context*:

  * grounding - is the question actually supported by the source material, or
    did the model hallucinate it?
  * duplicate detection - is this question a near-copy of another in the batch?

These produce warnings and scores, not hard rejections, because the human
instructor makes the final call in the review step. The one thing the app
enforces hard is that nothing is exported without explicit approval.

The techniques here are deliberately simple and dependency-free (token overlap,
Jaccard similarity) so a student can read and reason about them. They are a
*basic* hallucination heuristic, not a guarantee.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.question import GeneratedQuestion

_WORD_RE = re.compile(r"\w+", re.UNICODE)

# A reference that is this fraction (or more) of its words present in the
# source counts as grounded.
GROUNDING_THRESHOLD = 0.6
# Two questions whose word sets overlap this much are treated as duplicates.
DUPLICATE_THRESHOLD = 0.8


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text or "")}


def _normalize(text: str) -> str:
    return " ".join(_WORD_RE.findall((text or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class QuestionValidation:
    grounding_score: float = 0.0
    is_grounded: bool = False
    is_duplicate: bool = False
    duplicate_of: int | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when there is nothing that should block approval by default.

        A question can still be approved by an instructor despite warnings;
        ``ok`` just drives the default UI state.
        """
        return self.is_grounded and not self.is_duplicate


def check_grounding(question: GeneratedQuestion, source_text: str) -> tuple[float, bool]:
    """Fraction of the source_reference's words found in the source material.

    Falls back to the question text when no explicit reference was supplied.
    A normalized substring match short-circuits to a perfect score.
    """
    source_norm = _normalize(source_text)
    reference = question.source_reference or question.question_text
    ref_norm = _normalize(reference)

    if ref_norm and ref_norm in source_norm:
        return 1.0, True

    source_tokens = _tokens(source_text)
    ref_tokens = _tokens(reference)
    if not ref_tokens:
        return 0.0, False
    score = len(ref_tokens & source_tokens) / len(ref_tokens)
    return score, score >= GROUNDING_THRESHOLD


def validate_batch(
    questions: list[GeneratedQuestion], *, source_text: str
) -> list[QuestionValidation]:
    reports = [QuestionValidation() for _ in questions]
    seen: list[tuple[int, set[str]]] = []

    for i, q in enumerate(questions):
        report = reports[i]

        score, grounded = check_grounding(q, source_text)
        report.grounding_score = round(score, 3)
        report.is_grounded = grounded
        if not grounded:
            report.warnings.append(
                "Low grounding: this question may not be supported by the "
                "material. Review carefully (possible hallucination)."
            )

        q_tokens = _tokens(q.question_text)
        for j, prev_tokens in seen:
            if _jaccard(q_tokens, prev_tokens) >= DUPLICATE_THRESHOLD:
                report.is_duplicate = True
                report.duplicate_of = j
                report.warnings.append(f"Near-duplicate of question #{j + 1}.")
                break
        seen.append((i, q_tokens))

    return reports
