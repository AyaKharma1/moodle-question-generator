from lxml import etree

from app.moodle_export import ExportValidationError, export_questions
from app.schemas.question import (
    AnswerOption,
    Difficulty,
    GeneratedQuestion,
    Language,
    QuestionType,
)
import pytest


def _mc():
    return GeneratedQuestion(
        question_type=QuestionType.multiple_choice,
        question_text="Was beschreibt die Normalisierung? <Sonderzeichen & \"Umlaut\" äöü>",
        answers=[
            AnswerOption(text="Reduktion von Redundanz äöüß", is_correct=True, feedback="Richtig"),
            AnswerOption(text="Erhöhung von Redundanz", is_correct=False),
        ],
        explanation="Normalisierung reduziert Redundanz.",
        language=Language.de,
    )


def _tf():
    return GeneratedQuestion(
        question_type=QuestionType.true_false,
        question_text="Ein Fremdschlüssel verweist auf einen Primärschlüssel.",
        answers=[
            AnswerOption(text="wahr", is_correct=True),
            AnswerOption(text="falsch", is_correct=False),
        ],
        explanation="Korrekt.",
    )


def _sa():
    return GeneratedQuestion(
        question_type=QuestionType.short_answer,
        question_text="Welche Sprache fragt relationale Datenbanken ab?",
        answers=[AnswerOption(text="SQL", is_correct=True)],
        explanation="SQL ist die Standardsprache.",
    )


def test_export_is_wellformed_utf8():
    xml = export_questions([_mc(), _tf(), _sa()])
    assert xml.startswith(b"<?xml")
    assert b"UTF-8" in xml
    root = etree.fromstring(xml)
    assert root.tag == "quiz"
    assert len(root.findall("question")) == 3


def test_umlauts_preserved():
    xml = export_questions([_mc()])
    assert "äöüß".encode("utf-8") in xml  # real UTF-8 bytes, not escaped entities


def test_special_characters_escaped_not_injected():
    # The angle brackets in the question text must NOT create real elements.
    xml = export_questions([_mc()])
    root = etree.fromstring(xml)
    q = root.find("question")
    qtext = q.find("questiontext/text").text
    assert "<Sonderzeichen" in qtext  # survived as literal text via CDATA
    # No stray element leaked from the content:
    assert q.find("questiontext").find("Sonderzeichen") is None


def test_multichoice_structure():
    root = etree.fromstring(export_questions([_mc()]))
    q = root.find("question[@type='multichoice']")
    assert q is not None
    assert q.find("single").text == "true"
    answers = q.findall("answer")
    fractions = sorted(a.get("fraction") for a in answers)
    assert fractions == ["0", "100"]


def test_truefalse_maps_to_english_tokens():
    root = etree.fromstring(export_questions([_tf()]))
    q = root.find("question[@type='truefalse']")
    texts = {a.find("text").text: a.get("fraction") for a in q.findall("answer")}
    assert texts == {"true": "100", "false": "0"}


def test_shortanswer_structure():
    root = etree.fromstring(export_questions([_sa()]))
    q = root.find("question[@type='shortanswer']")
    assert q.find("usecase").text == "0"
    assert q.find("answer/text").text == "SQL"


def test_empty_export_rejected():
    with pytest.raises(ExportValidationError):
        export_questions([])
