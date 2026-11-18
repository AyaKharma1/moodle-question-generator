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
import threading
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import func, select
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
from app.question_bank.search import build_search_text
from app.moodle_import.report import build_report
from app.moodle_import import (
    NO_CATEGORY,
    MoodleImportError,
    ParsedQuestion,
    missing_files_in_xml,
    normalize,
    parse_moodle_xml,
    plain_text,
    split_fach_and_category,
)

# Two questions whose word sets overlap this much count as "similar".
SIMILARITY_THRESHOLD = 0.8
MAX_SIMILAR_PAIRS = 5000

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
    report: dict | None = None


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
    row.search_text = build_search_text(row)
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
    if not parsed_questions:
        raise MoodleImportError(
            "Die Datei enthält keine Fragen (nur Kategorien oder leer). "
            "Bitte beim Export in Moodle eine Kategorie mit Fragen wählen."
        )
    fach = (fach or "").strip() or None

    import_file = ImportFile(
        owner_id=owner.id, filename=filename, fach=fach,
        content_hash=content_hash, size_bytes=len(data),
    )
    db.add(import_file)
    db.flush()

    summary = ImportSummary(file_id=import_file.id, filename=filename, fach=fach)
    # Only three columns are needed to recognise questions that are already in the
    # bank. Loading whole Question objects (with answers and origins) for every
    # file made each import slower than the one before it.
    known_ids: dict[str, int] = {}
    text_fps: set[str | None] = set()
    for qid, fp, text_fp in db.execute(
        select(Question.id, Question.fingerprint, Question.text_fingerprint)
        .where(Question.owner_id == owner.id, Question.fingerprint.is_not(None))
    ):
        known_ids[fp] = qid
        text_fps.add(text_fp)
    new_rows: dict[str, Question] = {}      # questions created by this very file
    categories: list[str] = []

    for parsed in parsed_questions:
        q_fach, category = split_fach_and_category(parsed.category_segments, fach)
        q_fach = q_fach or _filename_stem(filename)
        if category not in categories:
            categories.append(category)

        occurrence = QuestionOccurrence(import_file=import_file, fach=q_fach, category=category)
        row = new_rows.get(parsed.fingerprint)
        if row is not None:
            summary.existing += 1
            row.occurrences.append(occurrence)
        elif parsed.fingerprint in known_ids:
            summary.existing += 1
            occurrence.question_id = known_ids[parsed.fingerprint]
            db.add(occurrence)
        else:
            if parsed.text_fingerprint in text_fps:
                summary.conflicts += 1
            row = _new_question(owner, parsed, q_fach, category)
            db.add(row)
            new_rows[parsed.fingerprint] = row
            text_fps.add(parsed.text_fingerprint)
            summary.new += 1
            row.occurrences.append(occurrence)
        summary.total += 1

    import_file.question_count = summary.total
    import_file.new_count = summary.new
    summary.report = import_file.report = build_report(parsed_questions)
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
    # Counting happens in the database: the dashboard must not load every
    # question (with answers and origins) just to show a few numbers.
    tree: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    total_questions = 0
    for fach, category, count in db.execute(
        select(Question.fach, Question.category, func.count(Question.id))
        .where(Question.owner_id == owner.id)
        .group_by(Question.fach, Question.category)
    ):
        tree[fach or "Ohne Fach"][category or NO_CATEGORY] += count
        total_questions += count
    file_count = db.scalar(
        select(func.count(ImportFile.id)).where(ImportFile.owner_id == owner.id)
    ) or 0

    from app.question_bank import findings as fx          # findings builds on this module
    analysis, found = _refresh(db, owner, with_findings=True)    # one load for both
    decisions = fx.decisions_of(db, owner)
    quality = fx.summarize(fx.with_state(found, decisions))
    return {
        "quality": {
            "open": quality["open"], "done": quality["done"],
            "reviewed": sum(1 for d in decisions.values() if d["state"] == "reviewed"),
            "excluded": sum(1 for d in decisions.values() if d["state"] == "excluded"),
            "open_conflicts": sum(1 for g in analysis["conflicts"]
                                  if not fx.group_resolved([q["id"] for q in g["questions"]], decisions)),
        },
        "totals": {
            "questions": total_questions,
            "files": file_count,
            "fachs": len(tree),
            "categories": sum(len(c) for c in tree.values()),
            "duplicates": len(analysis["exact"]),
            "conflicts": len(analysis["conflicts"]),
            "similar": len(analysis["similar"]),
            # the search stops at MAX_SIMILAR_PAIRS; the UI then shows "5.000+"
            "similar_capped": len(analysis["similar"]) >= MAX_SIMILAR_PAIRS,
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


def similar_pairs(questions: list[Question], limit: int = MAX_SIMILAR_PAIRS) -> list[tuple[int, int, float]]:
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
                if len(pairs) >= limit:
                    return pairs
        for tok in prefix:
            index[tok].append(j)
    return pairs


def _issues(q: Question) -> list[tuple[str, str]]:
    """Technical problems as ``(code, text)``; the codes are defined in ``findings``."""
    problems: list[tuple[str, str]] = []
    if not plain_text(q.question_text) and "<img" not in (q.question_text or ""):
        problems.append(("empty_text", "Fragetext ist leer."))
    graded = (q.moodle_type or q.question_type) in _GRADED_TYPES
    if graded and q.answers and not any(a.is_correct for a in q.answers):
        problems.append(("no_correct_answer", "Keine richtige Antwort markiert."))
    if q.question_type == "multiple_choice" and q.answers and all(a.is_correct for a in q.answers) \
            and len(q.answers) > 1:
        problems.append(("all_correct", "Alle Antworten sind als richtig markiert."))
    seen: set[str] = set()
    for a in q.answers:
        key = normalize(a.text)
        if key and key in seen:
            problems.append(("duplicate_answer", f"Antwort „{plain_text(a.text)}“ kommt doppelt vor."))
            break
        seen.add(key)
    missing = missing_files_in_xml(q.raw_xml) if q.raw_xml else []
    if missing:
        problems.append(("missing_media", "Bild fehlt in der Datei: " + ", ".join(missing)))
    return problems


# ------------------------------------------------------------ cached analysis
#
# The analysis looks at the whole bank, so it costs about a second with
# thousands of questions. It is needed by the overview, the problem filter,
# the hints on every question and the test planner, so it is computed once per
# state of the bank. The state is a cheap fingerprint of the bank's rows: any
# import, removal or edit changes it and the next request recomputes.

_cache: dict[int, tuple[tuple, dict]] = {}
_findings_cache: dict[int, tuple[tuple, list]] = {}
_cache_lock = threading.Lock()


def clear_analysis_cache() -> None:
    with _cache_lock:
        _cache.clear()
        _findings_cache.clear()


def bank_version(db: Session, owner: User) -> tuple:
    questions = db.execute(
        select(func.count(Question.id), func.coalesce(func.max(Question.id), 0),
               func.coalesce(func.sum(Question.id), 0), func.max(Question.updated_at))
        .where(Question.owner_id == owner.id)
    ).one()
    occurrences = db.execute(
        select(func.count(QuestionOccurrence.id), func.coalesce(func.max(QuestionOccurrence.id), 0))
        .join(Question, Question.id == QuestionOccurrence.question_id)
        .where(Question.owner_id == owner.id)
    ).one()
    files = db.execute(
        select(func.count(ImportFile.id), func.coalesce(func.max(ImportFile.id), 0))
        .where(ImportFile.owner_id == owner.id)
    ).one()
    return (*questions, *occurrences, *files)


def analysis_cached(db: Session, owner: User) -> dict:
    """``analyse`` for the current state of the bank, recomputed only after a change.

    The result is shared between requests: do not modify it.
    """
    return _refresh(db, owner, with_findings=False)[0]


def findings_cached(db: Session, owner: User) -> list[dict]:
    """All quality findings of the bank, recomputed only after a change.

    The lecturer's decisions are *not* part of this: they are applied on top
    with ``findings.with_state`` because they change more often than the questions.
    """
    return _refresh(db, owner, with_findings=True)[1]


def _refresh(db: Session, owner: User, *, with_findings: bool) -> tuple[dict, list[dict] | None]:
    """Analysis (and, if asked, findings) for the current bank state.

    The questions are loaded at most once per call, however many of the two
    results have to be recomputed.
    """
    from app.question_bank.findings import build_findings   # findings builds on this module

    version = bank_version(db, owner)
    with _cache_lock:
        a_hit, f_hit = _cache.get(owner.id), _findings_cache.get(owner.id)
    a_fresh = bool(a_hit and a_hit[0] == version)
    f_fresh = bool(f_hit and f_hit[0] == version)
    if a_fresh and (f_fresh or not with_findings):
        return a_hit[1], (f_hit[1] if f_fresh else None)

    questions = _bank_questions(db, owner)
    analysis = a_hit[1] if a_fresh else analyse(db, owner, questions=questions)
    findings = f_hit[1] if f_fresh else None
    if with_findings and findings is None:
        findings = build_findings(questions, analysis)
    with _cache_lock:
        _cache[owner.id] = (version, analysis)
        if findings is not None:
            _findings_cache[owner.id] = (version, findings)
    return analysis, findings


def analysis_counts(analysis: dict) -> dict:
    return {key: len(items) for key, items in analysis.items()}


def trimmed_analysis(analysis: dict, limit: int) -> dict:
    """The analysis with every list cut to ``limit`` entries, plus the real counts."""
    counts = analysis_counts(analysis)
    return {**{key: items[:limit] for key, items in analysis.items()},
            "counts": counts, "limit": limit,
            # the similar-question search stops at MAX_SIMILAR_PAIRS, so that count is a lower bound
            "similar_capped": counts["similar"] >= MAX_SIMILAR_PAIRS}


def check_selection(analysis: dict, ids: set[int]) -> dict:
    """Problems that arise from picking exactly these questions together."""
    similar = [(p["a"]["name"], p["b"]["name"]) for p in analysis["similar"]
               if p["a"]["id"] in ids and p["b"]["id"] in ids]
    conflicts = [g["questions"][0]["name"] for g in analysis["conflicts"]
                 if sum(1 for q in g["questions"] if q["id"] in ids) > 1]
    broken = [i["question"]["name"] for i in analysis["issues"] if i["question"]["id"] in ids]
    return {
        "similar_pairs": len(similar), "similar_examples": [f"{a} ↔ {b}" for a, b in similar[:3]],
        "conflict_groups": len(conflicts), "conflict_examples": conflicts[:3],
        "broken": len(broken), "broken_examples": broken[:3],
    }


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
        for i, j, score in similar_pairs(questions)
    ]

    # 4. Broken questions.
    issues = [
        {"question": brief(q), "problems": [text for _, text in found], "codes": [code for code, _ in found]}
        for q in questions if (found := _issues(q))
    ]

    return {"exact": exact, "conflicts": conflicts, "similar": similar, "issues": issues}
