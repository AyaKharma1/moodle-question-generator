"""Question bank: import Moodle XML files, keep provenance, find problems.

The bank answers the questions an instructor with many exported files has:
  * Which questions do I have, per Fach and Kategorie?
  * Which file(s) does each question come from?
  * Which questions are duplicated, contradict each other, are suspiciously
    similar, or are broken (no correct answer, missing image, ...)?

A question that appears in several files is stored once; every appearance is
recorded as a ``QuestionOccurrence``.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Answer,
    ExportHistory,
    ImportFile,
    Question,
    QuestionOccurrence,
    QuestionStatus,
    User,
)
from app.moodle_import import (
    NO_CATEGORY,
    ParsedQuestion,
    missing_files_in_xml,
    normalize,
    parse_moodle_xml,
    plain_text,
    split_fach_and_category,
)

# Two questions whose word sets overlap this much count as "similar".
SIMILARITY_THRESHOLD = 0.8
MAX_SIMILAR_PAIRS = 200

_WORD_RE = re.compile(r"\w+", re.UNICODE)
# Types where "has a correct answer" is a meaningful check.
_GRADED_TYPES = {"multichoice", "truefalse", "shortanswer", "multiple_choice",
                 "true_false", "short_answer"}


class DuplicateFileError(ValueError):
    """The exact same file content was already imported."""


@dataclass
class ImportSummary:
    file_id: int
    filename: str
    fach: str | None
    total: int = 0
    new: int = 0
    existing: int = 0
    conflicts: int = 0
    categories: list[str] = field(default_factory=list)


def _filename_stem(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    return stem.strip() or filename


def _new_question(owner: User, parsed: ParsedQuestion, fach: str | None,
                  category: str) -> Question:
    row = Question(
        owner_id=owner.id,
        question_type=parsed.question_type,
        question_text=parsed.question_text,
        explanation=parsed.explanation,
        difficulty="medium",
        language="de",
        # Imported questions already live in the instructor's Moodle bank, so
        # they are trusted and exportable right away.
        status=QuestionStatus.approved.value,
        ai_generated=False,
        name=parsed.name,
        fach=fach,
        category=category,
        category_path=parsed.category_path,
        moodle_type=parsed.moodle_type,
        raw_xml=parsed.raw_xml,
        text_fingerprint=parsed.text_fingerprint,
        fingerprint=parsed.fingerprint,
    )
    for pos, a in enumerate(parsed.answers):
        row.answers.append(Answer(
            text=a.text, is_correct=a.is_correct, feedback=a.feedback, position=pos,
        ))
    return row


def import_moodle_file(db: Session, *, owner: User, filename: str,
                       data: bytes, fach: str | None) -> ImportSummary:
    """Import one Moodle XML file; questions already in the bank are linked."""
    content_hash = hashlib.sha256(data).hexdigest()
    already = db.scalar(select(ImportFile).where(
        ImportFile.owner_id == owner.id, ImportFile.content_hash == content_hash,
    ))
    if already is not None:
        raise DuplicateFileError(
            f"Diese Datei wurde bereits als „{already.filename}“ importiert."
        )

    parsed_questions = parse_moodle_xml(data)
    fach = (fach or "").strip() or None

    import_file = ImportFile(
        owner_id=owner.id, filename=filename, fach=fach,
        content_hash=content_hash, size_bytes=len(data),
    )
    db.add(import_file)
    db.flush()

    summary = ImportSummary(file_id=import_file.id, filename=filename, fach=fach)
    by_fp = {
        q.fingerprint: q for q in db.scalars(
            select(Question).where(Question.owner_id == owner.id, Question.fingerprint.is_not(None))
        )
    }
    text_fps = {q.text_fingerprint for q in by_fp.values()}
    categories: list[str] = []

    for parsed in parsed_questions:
        q_fach, category = split_fach_and_category(parsed.category_segments, fach)
        q_fach = q_fach or _filename_stem(filename)
        if category not in categories:
            categories.append(category)

        row = by_fp.get(parsed.fingerprint)
        if row is None:
            if parsed.text_fingerprint in text_fps:
                summary.conflicts += 1
            row = _new_question(owner, parsed, q_fach, category)
            db.add(row)
            by_fp[parsed.fingerprint] = row
            text_fps.add(parsed.text_fingerprint)
            summary.new += 1
        else:
            summary.existing += 1
        row.occurrences.append(QuestionOccurrence(
            import_file=import_file, fach=q_fach, category=category,
        ))
        summary.total += 1

    import_file.question_count = summary.total
    import_file.new_count = summary.new
    summary.categories = categories
    db.flush()
    return summary


def delete_import_file(db: Session, import_file: ImportFile) -> int:
    """Remove a file from the bank. Returns how many questions were deleted.

    Questions that only came from this file are deleted; questions also found
    in other files stay and take their Fach/Kategorie from the next file.
    """
    affected = {occ.question for occ in import_file.occurrences}
    db.delete(import_file)
    db.flush()
    deleted = 0
    for q in affected:
        db.refresh(q)
        if not q.occurrences and not q.ai_generated:
            db.delete(q)
            deleted += 1
        elif q.occurrences:
            first = q.occurrences[0]
            q.fach, q.category = first.fach, first.category
    db.flush()
    return deleted


# ---------------------------------------------------------------- read models

def export_map(db: Session, owner: User) -> dict[int, list[str]]:
    """question id -> names of the XML files it was exported to."""
    result: dict[int, list[str]] = defaultdict(list)
    for h in db.scalars(select(ExportHistory).where(ExportHistory.owner_id == owner.id)
                        .order_by(ExportHistory.id)):
        for qid in h.question_ids or []:
            if h.filename not in result[qid]:
                result[qid].append(h.filename)
    return result


def brief(q: Question) -> dict:
    text = plain_text(q.question_text)
    return {
        "id": q.id,
        "name": q.name,
        "text": text if len(text) <= 300 else text[:300] + "…",
        "question_type": q.question_type,
        "fach": q.fach,
        "category": q.category,
        "origins": q.origins,
        "answers": [
            {"text": plain_text(a.text), "is_correct": a.is_correct} for a in q.answers
        ],
    }


def _bank_questions(db: Session, owner: User) -> list[Question]:
    return list(db.scalars(
        select(Question).where(Question.owner_id == owner.id)
        .options(selectinload(Question.answers)).order_by(Question.id)
    ))


def overview(db: Session, owner: User) -> dict:
    questions = _bank_questions(db, owner)
    files = list(db.scalars(select(ImportFile).where(ImportFile.owner_id == owner.id)))

    tree: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for q in questions:
        tree[q.fach or "Ohne Fach"][q.category or NO_CATEGORY] += 1

    analysis = analyse(db, owner, questions=questions)
    return {
        "totals": {
            "questions": len(questions),
            "files": len(files),
            "fachs": len(tree),
            "categories": sum(len(c) for c in tree.values()),
            "duplicates": len(analysis["exact"]),
            "conflicts": len(analysis["conflicts"]),
            "similar": len(analysis["similar"]),
            "issues": len(analysis["issues"]),
        },
        "tree": [
            {
                "fach": fach,
                "count": sum(cats.values()),
                "categories": [
                    {"name": name, "count": count}
                    for name, count in sorted(cats.items())
                ],
            }
            for fach, cats in sorted(tree.items())
        ],
    }


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(plain_text(text))}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _similar_pairs(questions: list[Question]) -> list[tuple[int, int, float]]:
    """Pairs with Jaccard similarity >= SIMILARITY_THRESHOLD.

    Uses prefix filtering instead of comparing every pair: with tokens sorted
    rarest-first, two sets can only reach the threshold if they share a token
    within their first ``len - ceil(t * len) + 1`` tokens. That turns the
    all-pairs scan into a lookup in a small inverted index.
    """
    t = SIMILARITY_THRESHOLD
    token_sets = [_tokens(q.question_text) for q in questions]
    freq: dict[str, int] = defaultdict(int)
    for tokens in token_sets:
        for tok in tokens:
            freq[tok] += 1
    ordered = [sorted(tokens, key=lambda tok: (freq[tok], tok)) for tokens in token_sets]

    index: dict[str, list[int]] = defaultdict(list)
    pairs: list[tuple[int, int, float]] = []
    for j, tokens in enumerate(ordered):
        if not tokens:
            continue
        prefix = tokens[: len(tokens) - math.ceil(t * len(tokens)) + 1]
        candidates = {i for tok in prefix for i in index[tok]}
        for i in sorted(candidates):
            qa, qb = questions[i], questions[j]
            if qa.text_fingerprint and qa.text_fingerprint == qb.text_fingerprint:
                continue  # already reported as conflict
            score = _jaccard(token_sets[i], token_sets[j])
            if score >= t:
                pairs.append((i, j, score))
                if len(pairs) >= MAX_SIMILAR_PAIRS:
                    return pairs
        for tok in prefix:
            index[tok].append(j)
    return pairs


def _issues(q: Question) -> list[str]:
    problems: list[str] = []
    if not plain_text(q.question_text) and "<img" not in (q.question_text or ""):
        problems.append("Fragetext ist leer.")
    graded = (q.moodle_type or q.question_type) in _GRADED_TYPES
    if graded and q.answers and not any(a.is_correct for a in q.answers):
        problems.append("Keine richtige Antwort markiert.")
    if q.question_type == "multiple_choice" and q.answers and all(a.is_correct for a in q.answers) \
            and len(q.answers) > 1:
        problems.append("Alle Antworten sind als richtig markiert.")
    seen: set[str] = set()
    for a in q.answers:
        key = normalize(a.text)
        if key and key in seen:
            problems.append(f"Antwort „{plain_text(a.text)}“ kommt doppelt vor.")
            break
        seen.add(key)
    missing = missing_files_in_xml(q.raw_xml) if q.raw_xml else []
    if missing:
        problems.append("Bild fehlt in der Datei: " + ", ".join(missing))
    return problems


def analyse(db: Session, owner: User, *, questions: list[Question] | None = None) -> dict:
    questions = questions if questions is not None else _bank_questions(db, owner)

    # 1. Same question in several places (stored once, many occurrences).
    exact = [
        {"question": brief(q), "count": len(q.occurrences)}
        for q in questions if len(q.occurrences) > 1
    ]

    # 2. Same question text but different answers -> the files contradict.
    by_text: dict[str, list[Question]] = defaultdict(list)
    for q in questions:
        if q.text_fingerprint:
            by_text[q.text_fingerprint].append(q)
    conflicts = [
        {"questions": [brief(q) for q in group]}
        for group in by_text.values() if len(group) > 1
    ]

    # 3. Different wording, (almost) the same content.
    similar = [
        {"a": brief(questions[i]), "b": brief(questions[j]), "score": round(score, 2)}
        for i, j, score in _similar_pairs(questions)
    ]

    # 4. Broken questions.
    issues = [
        {"question": brief(q), "problems": problems}
        for q in questions if (problems := _issues(q))
    ]

    return {"exact": exact, "conflicts": conflicts, "similar": similar, "issues": issues}
