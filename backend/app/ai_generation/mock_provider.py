"""Deterministic mock AI provider.

This lets the whole application be developed, tested and demoed with no paid API
access and no network. It is also the provider used in automated tests, so the
pipeline is exercised end to end deterministically.

It does NOT call any model. It extracts sentences from the source material and
builds well-formed questions whose ``source_reference`` is a real substring of
the material, so the grounding check in ``question_validation`` passes for
genuine input and the demo is honest about where each question comes from.
"""
from __future__ import annotations

import re

from app.ai_generation.base import AIProvider, AIProviderError
from app.schemas.question import GenerationRequest, Language, QuestionType

_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?")


def _sentences(text: str, min_len: int = 25) -> list[str]:
    out: list[str] = []
    for raw in _SENTENCE_RE.findall(text):
        s = raw.strip()
        if len(s) >= min_len:
            out.append(s)
    return out


def _t(language: Language, de: str, en: str) -> str:
    return de if language == Language.de else en


class MockAIProvider(AIProvider):
    name = "mock"

    def generate(self, *, source_text: str, request: GenerationRequest) -> list[dict]:
        sentences = _sentences(source_text)
        if not sentences:
            raise AIProviderError(
                "The document contains too little extractable text to generate "
                "questions from."
            )

        lang = request.language
        n = min(request.num_questions, len(sentences))
        questions: list[dict] = []

        for i in range(n):
            sentence = sentences[i]
            qt = request.question_type
            if qt == QuestionType.multiple_choice:
                questions.append(self._mc(sentence, sentences, i, lang, request))
            elif qt == QuestionType.true_false:
                questions.append(self._tf(sentence, lang, request))
            else:
                questions.append(self._sa(sentence, lang, request))

        return questions

    # --- builders -------------------------------------------------------

    def _mc(self, sentence, sentences, i, lang, request) -> dict:
        distractors = [s for j, s in enumerate(sentences) if j != i][:3]
        # Guarantee at least two options even for very short material.
        if not distractors:
            distractors = [
                _t(lang, "Keine der genannten Aussagen.", "None of the statements.")
            ]
        answers = [{"text": sentence, "is_correct": True,
                    "feedback": _t(lang, "Steht so im Material.",
                                   "Stated directly in the material.")}]
        for d in distractors:
            answers.append({"text": d, "is_correct": False, "feedback": ""})
        return {
            "question_type": "multiple_choice",
            "question_text": _t(
                lang,
                "Welche Aussage entspricht dem Lernmaterial?",
                "Which statement matches the lecture material?",
            ),
            "answers": answers,
            "explanation": _t(
                lang,
                "Die richtige Aussage stammt wörtlich aus dem Material.",
                "The correct statement is taken directly from the material.",
            ),
            "difficulty": request.difficulty.value,
            "language": lang.value,
            "source_reference": sentence,
        }

    def _tf(self, sentence, lang, request) -> dict:
        return {
            "question_type": "true_false",
            "question_text": _t(
                lang, f"Aussage: {sentence}", f"Statement: {sentence}"
            ),
            "answers": [
                {"text": _t(lang, "wahr", "true"), "is_correct": True,
                 "feedback": _t(lang, "Korrekt, steht im Material.",
                                "Correct, it is in the material.")},
                {"text": _t(lang, "falsch", "false"), "is_correct": False,
                 "feedback": ""},
            ],
            "explanation": _t(
                lang,
                "Die Aussage ist dem Material direkt entnommen und daher wahr.",
                "The statement is taken directly from the material and is true.",
            ),
            "difficulty": request.difficulty.value,
            "language": lang.value,
            "source_reference": sentence,
        }

    def _sa(self, sentence, lang, request) -> dict:
        words = re.findall(r"\w{5,}", sentence)
        keyword = words[0] if words else sentence.split()[0]
        return {
            "question_type": "short_answer",
            "question_text": _t(
                lang,
                f"Nennen Sie einen zentralen Begriff aus: \"{sentence}\"",
                f"Name a key term from: \"{sentence}\"",
            ),
            "answers": [
                {"text": keyword, "is_correct": True,
                 "feedback": _t(lang, "Ein akzeptierter Begriff.",
                                "An accepted term.")},
            ],
            "explanation": _t(
                lang,
                f"Der Begriff \"{keyword}\" kommt im Material vor.",
                f"The term \"{keyword}\" appears in the material.",
            ),
            "difficulty": request.difficulty.value,
            "language": lang.value,
            "source_reference": sentence,
        }
