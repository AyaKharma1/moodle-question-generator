from app.question_validation.validator import validate_batch
from app.schemas.question import (
    AnswerOption,
    GeneratedQuestion,
    QuestionType,
)

SOURCE = (
    "Ein Primärschlüssel identifiziert jeden Datensatz einer Tabelle eindeutig. "
    "Die Normalisierung reduziert Redundanz in einer Datenbank."
)


def _q(text, ref=None):
    return GeneratedQuestion(
        question_type=QuestionType.multiple_choice,
        question_text=text,
        answers=[
            AnswerOption(text="a", is_correct=True),
            AnswerOption(text="b", is_correct=False),
        ],
        explanation="e",
        source_reference=ref,
    )


def test_grounded_question_flagged_grounded():
    q = _q("Frage", ref="Ein Primärschlüssel identifiziert jeden Datensatz einer Tabelle eindeutig.")
    report = validate_batch([q], source_text=SOURCE)[0]
    assert report.is_grounded
    assert report.grounding_score == 1.0


def test_hallucinated_question_flagged():
    q = _q("Frage", ref="Quantenverschränkung in der Astrophysik der Galaxien")
    report = validate_batch([q], source_text=SOURCE)[0]
    assert not report.is_grounded
    assert any("grounding" in w.lower() for w in report.warnings)


def test_duplicate_detection():
    q1 = _q("Was ist ein Primärschlüssel in einer Tabelle", ref="Primärschlüssel")
    q2 = _q("Was ist ein Primärschlüssel in einer Tabelle", ref="Primärschlüssel")
    reports = validate_batch([q1, q2], source_text=SOURCE)
    assert not reports[0].is_duplicate
    assert reports[1].is_duplicate
    assert reports[1].duplicate_of == 0
