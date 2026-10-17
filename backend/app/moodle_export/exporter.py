"""Moodle XML exporter.

Builds Moodle's "quiz" XML question format with lxml. We build an element tree
and let lxml handle escaping and encoding instead of concatenating strings,
which is both safer (no XML injection, correct escaping of <, >, &, umlauts)
and more maintainable.

Supported types: multichoice, truefalse, shortanswer.

Honesty note (see MOODLE_IMPORT_GUIDE.md): producing well-formed XML that
follows the documented format is necessary but NOT proof of Moodle
compatibility. The only proof is a successful manual import into a real Moodle
test instance, which the guide describes step by step.
"""
from __future__ import annotations

import html
from typing import Iterable, Optional

from lxml import etree

from app.schemas.question import GeneratedQuestion, QuestionType

# Moodle only accepts specific fraction values. These are the exact strings
# Moodle uses for "n correct answers share the credit equally".
_EQUAL_FRACTIONS = {1: "100", 2: "50", 3: "33.33333", 4: "25", 5: "20"}


class ExportValidationError(ValueError):
    """Raised when a question cannot be represented as valid Moodle XML."""


def _true_false_meaning(text: str) -> Optional[bool]:
    t = text.strip().lower()
    if t in {"true", "wahr", "richtig"}:
        return True
    if t in {"false", "falsch"}:
        return False
    return None


def _add_text_child(parent, tag: str, content: str, *, fmt: str = "html") -> None:
    """Append ``<tag format="..."><text><![CDATA[content]]></text></tag>``."""
    el = etree.SubElement(parent, tag)
    if fmt:
        el.set("format", fmt)
    text_el = etree.SubElement(el, "text")
    text_el.text = etree.CDATA(content or "")


def _add_answer(parent, *, fraction: str, text: str, feedback: str = "",
                fmt: str = "html", plain_text: bool = False) -> None:
    answer = etree.SubElement(parent, "answer")
    answer.set("fraction", fraction)
    answer.set("format", "moodle_auto_format" if plain_text else fmt)
    text_el = etree.SubElement(answer, "text")
    if plain_text:
        text_el.text = text  # lxml escapes this; "true"/"false" need no CDATA
    else:
        text_el.text = etree.CDATA(text or "")
    fb = etree.SubElement(answer, "feedback")
    fb.set("format", "html")
    fb_text = etree.SubElement(fb, "text")
    fb_text.text = etree.CDATA(feedback or "")


def _default_name(question_text: str) -> str:
    # Moodle shows the question name in the bank; keep it short and plain.
    plain = html.unescape(question_text).strip().replace("\n", " ")
    return (plain[:60] + "...") if len(plain) > 60 else plain or "Question"


def question_to_element(q: GeneratedQuestion, name: Optional[str] = None):
    """Convert one domain question into a Moodle ``<question>`` element."""
    name = name or _default_name(q.question_text)

    if q.question_type == QuestionType.multiple_choice:
        return _multichoice(q, name)
    if q.question_type == QuestionType.true_false:
        return _truefalse(q, name)
    if q.question_type == QuestionType.short_answer:
        return _shortanswer(q, name)
    raise ExportValidationError(f"Unsupported question type: {q.question_type}")


def _common_head(q: GeneratedQuestion, moodle_type: str, name: str):
    question = etree.Element("question")
    question.set("type", moodle_type)
    name_el = etree.SubElement(question, "name")
    name_text = etree.SubElement(name_el, "text")
    name_text.text = name  # plain, lxml-escaped
    _add_text_child(question, "questiontext", q.question_text)
    _add_text_child(question, "generalfeedback", q.explanation)
    etree.SubElement(question, "defaultgrade").text = "1.0000000"
    etree.SubElement(question, "penalty").text = "0.3333333"
    etree.SubElement(question, "hidden").text = "0"
    return question


def _multichoice(q: GeneratedQuestion, name: str):
    correct = [a for a in q.answers if a.is_correct]
    if not correct:
        raise ExportValidationError("multiple_choice question has no correct answer")
    single = len(correct) == 1
    if not single and len(correct) not in _EQUAL_FRACTIONS:
        raise ExportValidationError(
            "multiple_choice with multiple correct answers is only supported "
            "for 2-5 equally-weighted correct answers"
        )

    question = _common_head(q, "multichoice", name)
    etree.SubElement(question, "single").text = "true" if single else "false"
    etree.SubElement(question, "shuffleanswers").text = "true"
    etree.SubElement(question, "answernumbering").text = "abc"

    correct_fraction = "100" if single else _EQUAL_FRACTIONS[len(correct)]
    for a in q.answers:
        _add_answer(
            question,
            fraction=correct_fraction if a.is_correct else "0",
            text=a.text,
            feedback=a.feedback or "",
        )
    return question


def _truefalse(q: GeneratedQuestion, name: str):
    if len(q.answers) != 2:
        raise ExportValidationError("true_false must have exactly two answers")
    question = _common_head(q, "truefalse", name)
    for a in q.answers:
        meaning = _true_false_meaning(a.text)
        if meaning is None:
            raise ExportValidationError(
                f"true_false option {a.text!r} is not true/false (or wahr/falsch)"
            )
        _add_answer(
            question,
            fraction="100" if a.is_correct else "0",
            text="true" if meaning else "false",
            feedback=a.feedback or "",
            plain_text=True,
        )
    return question


def _shortanswer(q: GeneratedQuestion, name: str):
    accepted = [a for a in q.answers if a.is_correct]
    if not accepted:
        raise ExportValidationError("short_answer has no accepted answer")
    question = _common_head(q, "shortanswer", name)
    # usecase=0: answer matching is case-insensitive.
    etree.SubElement(question, "usecase").text = "0"
    for a in accepted:
        _add_answer(
            question,
            fraction="100",
            text=a.text,
            feedback=a.feedback or "",
            plain_text=True,
        )
    return question


def export_questions(
    questions: Iterable[GeneratedQuestion],
    names: Optional[list[Optional[str]]] = None,
) -> bytes:
    """Serialize questions to a well-formed, UTF-8 Moodle XML document (bytes).

    Raises :class:`ExportValidationError` with a meaningful message if any
    question cannot be represented. German umlauts are preserved because the
    output is encoded as UTF-8.
    """
    questions = list(questions)
    if not questions:
        raise ExportValidationError("Cannot export an empty question set.")

    root = etree.Element("quiz")
    for i, q in enumerate(questions):
        name = names[i] if names and i < len(names) else None
        root.append(question_to_element(q, name))

    xml_bytes = etree.tostring(
        etree.ElementTree(root),
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )

    # Defensive re-parse: guarantee we only ever hand out well-formed XML.
    try:
        etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:  # pragma: no cover - should never happen
        raise ExportValidationError(f"Generated XML is not well-formed: {exc}") from exc
    return xml_bytes
