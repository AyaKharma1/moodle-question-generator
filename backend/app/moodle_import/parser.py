"""Moodle XML importer (the reverse of ``moodle_export``).

Reads files exported from a Moodle question bank ("Fragensammlung") and turns
every ``<question>`` into a :class:`ParsedQuestion`. Moodle writes a
``<question type="category">`` marker before the questions of each category;
every following question belongs to that category until the next marker.

Security: the XML comes from a user upload, so the parser never resolves
entities, never loads a DTD and never touches the network (blocks XXE and
"billion laughs" style payloads).

Duplicate detection relies on two fingerprints:
  * ``text_fingerprint``: question type + normalized question text.
  * ``fingerprint``: the text fingerprint + the set of answers and which of
    them are correct. Answer order is ignored, so a reshuffled copy is still
    recognised as the same question.
Same text but a different fingerprint means the files disagree about the
answers - that is reported as a conflict.
"""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import unquote

from lxml import etree

# Moodle type -> internal question_type. Other Moodle types (essay, matching,
# numerical, cloze, ...) are kept under their Moodle name and round-trip via
# the stored raw XML.
_TYPE_MAP = {
    "multichoice": "multiple_choice",
    "truefalse": "true_false",
    "shortanswer": "short_answer",
}

NO_CATEGORY = "Ohne Kategorie"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class MoodleImportError(ValueError):
    """Raised when a file is not a readable Moodle XML question export."""


@dataclass
class ParsedAnswer:
    text: str
    is_correct: bool
    feedback: Optional[str] = None


@dataclass
class ParsedQuestion:
    moodle_type: str
    question_type: str
    name: str
    question_text: str
    explanation: str
    answers: list[ParsedAnswer]
    category_path: Optional[str]
    category_segments: list[str]
    raw_xml: str
    text_fingerprint: str = ""
    fingerprint: str = ""


def safe_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
        remove_blank_text=False,
        strip_cdata=False,  # keep Moodle's <![CDATA[...]]> HTML as written
    )


def plain_text(value: str) -> str:
    """HTML -> comparable plain text (tags removed, entities decoded)."""
    text = _TAG_RE.sub(" ", value or "")
    return _WS_RE.sub(" ", html.unescape(text)).strip()


def normalize(value: str) -> str:
    return plain_text(value).lower()


def split_category_path(path: str) -> list[str]:
    """Split a Moodle category path into readable segments.

    ``$course$/top/Computersysteme/PC-Hardware`` -> ``["Computersysteme",
    "PC-Hardware"]``. Moodle escapes a literal slash inside a name as ``//``.
    Context prefixes (``$course$``, ``$system$``, ...) and the implicit
    ``top`` level are dropped.
    """
    placeholder = "\x00"
    parts = (path or "").replace("//", placeholder).split("/")
    segments = [p.replace(placeholder, "/").strip() for p in parts]
    segments = [s for s in segments if s]
    while segments and segments[0].startswith("$") and segments[0].endswith("$"):
        segments.pop(0)
    if segments and segments[0].lower() == "top":
        segments.pop(0)
    return segments


def fingerprints(moodle_type: str, question_text: str,
                 answers: list[ParsedAnswer]) -> tuple[str, str]:
    text_key = f"{moodle_type}\n{normalize(question_text)}"
    text_fp = hashlib.sha256(text_key.encode("utf-8")).hexdigest()
    answer_keys = sorted(f"{normalize(a.text)}|{int(a.is_correct)}" for a in answers)
    full_key = text_fp + "\n" + "\n".join(answer_keys)
    return text_fp, hashlib.sha256(full_key.encode("utf-8")).hexdigest()


def _text_of(parent, tag: str) -> str:
    el = parent.find(tag)
    if el is None:
        return ""
    text_el = el.find("text")
    return (text_el.text if text_el is not None else el.text) or ""


def _fraction(answer) -> float:
    try:
        return float(answer.get("fraction", "0"))
    except ValueError:
        return 0.0


def _missing_files(question) -> list[str]:
    """Images referenced as @@PLUGINFILE@@ that are not embedded in the XML."""
    xml = etree.tostring(question, encoding="unicode")
    referenced = set(re.findall(r"@@PLUGINFILE@@/([^\"'<>\s?]+)", xml))
    embedded = {f.get("name", "") for f in question.iter("file")}
    return sorted(unquote(r) for r in referenced if unquote(r) not in embedded)


def search_text_from_xml(raw_xml: str) -> str:
    """All human-readable text of one ``<question>`` element, as plain text.

    Covers the name, question text, answers, sub-questions of matching
    questions and all feedback, i.e. everything an instructor might remember
    about a question.
    """
    try:
        el = etree.fromstring(raw_xml.encode("utf-8"), parser=safe_parser())
    except etree.XMLSyntaxError:
        return ""
    parts = [plain_text(t.text or "") for t in el.iter("text")]
    return " ".join(p for p in parts if p)


def missing_files_in_xml(raw_xml: str) -> list[str]:
    try:
        return _missing_files(etree.fromstring(raw_xml.encode("utf-8"), parser=safe_parser()))
    except etree.XMLSyntaxError:
        return []


def _parse_question(el, category_path: Optional[str]) -> ParsedQuestion:
    moodle_type = (el.get("type") or "").strip().lower()
    answers = [
        ParsedAnswer(
            text=ans.findtext("text") or "",
            is_correct=_fraction(ans) > 0,
            feedback=_text_of(ans, "feedback") or None,
        )
        for ans in el.findall("answer")
    ]
    question_text = _text_of(el, "questiontext")
    name = plain_text(_text_of(el, "name")) or plain_text(question_text)[:60] or "Frage"
    segments = split_category_path(category_path) if category_path else []
    parsed = ParsedQuestion(
        moodle_type=moodle_type,
        question_type=_TYPE_MAP.get(moodle_type, moodle_type),
        name=name[:255],
        question_text=question_text,
        explanation=_text_of(el, "generalfeedback"),
        answers=answers,
        category_path=category_path,
        category_segments=segments,
        raw_xml=etree.tostring(el, encoding="unicode"),
    )
    parsed.text_fingerprint, parsed.fingerprint = fingerprints(
        moodle_type, question_text, answers
    )
    return parsed


def parse_moodle_xml(data: bytes) -> list[ParsedQuestion]:
    """Parse one Moodle XML export into questions (category markers applied)."""
    if not data or not data.strip():
        raise MoodleImportError("Die Datei ist leer.")
    try:
        root = etree.fromstring(data, parser=safe_parser())
    except etree.XMLSyntaxError as exc:
        raise MoodleImportError(f"Keine gültige XML-Datei: {exc}") from exc
    if root.tag != "quiz":
        raise MoodleImportError(
            "Keine Moodle-XML-Datei (erwartet wird ein <quiz>-Element)."
        )

    questions: list[ParsedQuestion] = []
    category_path: Optional[str] = None
    for el in root.findall("question"):
        qtype = (el.get("type") or "").strip().lower()
        if qtype == "category":
            category_path = _text_of(el, "category").strip() or None
            continue
        if not qtype:
            continue
        questions.append(_parse_question(el, category_path))
    return questions


def split_fach_and_category(segments: list[str], fach: Optional[str]) -> tuple[str | None, str]:
    """Derive (Fach, Kategorie) for display.

    With an explicit Fach the whole category path is the Kategorie. Without
    one, the top-level category is taken as the Fach.
    """
    if fach:
        return fach, " / ".join(segments) or NO_CATEGORY
    if not segments:
        return None, NO_CATEGORY
    if len(segments) == 1:
        return segments[0], segments[0]
    return segments[0], " / ".join(segments[1:])
