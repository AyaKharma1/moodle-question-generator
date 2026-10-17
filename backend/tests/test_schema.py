import pytest
from pydantic import ValidationError

from app.schemas.question import AnswerOption, GeneratedQuestion, QuestionType


def _mc(**over):
    base = dict(
        question_type=QuestionType.multiple_choice,
        question_text="Was ist ein Primärschlüssel?",
        answers=[
            AnswerOption(text="Eindeutiger Identifikator", is_correct=True),
            AnswerOption(text="Ein zufälliger Wert", is_correct=False),
        ],
        explanation="Der Primärschlüssel identifiziert einen Datensatz eindeutig.",
    )
    base.update(over)
    return GeneratedQuestion(**base)


def test_valid_multiple_choice():
    q = _mc()
    assert q.question_type == QuestionType.multiple_choice
    assert len(q.answers) == 2


def test_multiple_choice_requires_two_options():
    with pytest.raises(ValidationError):
        _mc(answers=[AnswerOption(text="nur eine", is_correct=True)])


def test_multiple_choice_requires_a_correct_answer():
    with pytest.raises(ValidationError):
        _mc(answers=[
            AnswerOption(text="a", is_correct=False),
            AnswerOption(text="b", is_correct=False),
        ])


def test_true_false_rules():
    q = GeneratedQuestion(
        question_type=QuestionType.true_false,
        question_text="ACID steht für Atomarität, Konsistenz, Isolation, Dauerhaftigkeit.",
        answers=[
            AnswerOption(text="wahr", is_correct=True),
            AnswerOption(text="falsch", is_correct=False),
        ],
        explanation="Korrekt.",
    )
    assert q.question_type == QuestionType.true_false

    with pytest.raises(ValidationError):
        GeneratedQuestion(
            question_type=QuestionType.true_false,
            question_text="x" * 10,
            answers=[AnswerOption(text="wahr", is_correct=True)],
            explanation="y",
        )


def test_empty_question_text_rejected():
    with pytest.raises(ValidationError):
        _mc(question_text="   ")
