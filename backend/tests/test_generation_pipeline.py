"""End-to-end test of the model-independent pipeline using the mock provider:
   text -> AI (mock) -> JSON -> parse -> validation -> XML.
"""
from pathlib import Path

from app.ai_generation.factory import get_provider
from app.ai_generation.service import run_generation
from app.config import Settings
from app.moodle_export import export_questions
from app.schemas.question import (
    Difficulty,
    GenerationRequest,
    Language,
    QuestionType,
)

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def _settings():
    return Settings(ai_provider="mock")


def test_mock_generation_is_grounded_and_exports():
    text = (SAMPLES / "sample_lecture_de.txt").read_text(encoding="utf-8")
    provider = get_provider(_settings())
    req = GenerationRequest(
        question_type=QuestionType.multiple_choice,
        num_questions=3,
        difficulty=Difficulty.medium,
        language=Language.de,
    )
    outcome = run_generation(provider=provider, source_text=text, request=req)

    assert outcome.provider == "mock"
    assert outcome.parse_errors == []
    assert len(outcome.reviewed) == 3
    # Mock output is lifted from the material, so grounding must hold.
    for r in outcome.reviewed:
        assert r.validation.is_grounded, r.validation.warnings

    xml = export_questions([r.question for r in outcome.reviewed])
    assert xml.startswith(b"<?xml")


def test_true_false_and_short_answer_types():
    text = (SAMPLES / "sample_lecture_de.txt").read_text(encoding="utf-8")
    provider = get_provider(_settings())
    for qt in (QuestionType.true_false, QuestionType.short_answer):
        req = GenerationRequest(question_type=qt, num_questions=2, language=Language.de)
        outcome = run_generation(provider=provider, source_text=text, request=req)
        assert outcome.parse_errors == []
        assert outcome.reviewed
        export_questions([r.question for r in outcome.reviewed])


def test_num_questions_is_capped_against_injection():
    # A document that tries to force 999 questions still cannot exceed the cap,
    # and the mock is further bounded by the number of usable sentences.
    text = (SAMPLES / "sample_prompt_injection.txt").read_text(encoding="utf-8")
    provider = get_provider(_settings())
    req = GenerationRequest(question_type=QuestionType.true_false, num_questions=50)
    outcome = run_generation(provider=provider, source_text=text, request=req)
    assert len(outcome.reviewed) <= 50
