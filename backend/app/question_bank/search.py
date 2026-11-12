"""Search over the question bank.

Search must feel instant and forgiving with thousands of questions in dozens
of files:

  * Every word of the query must match (AND), anywhere: question text,
    answers, sub-questions, feedback, name, Fach, Kategorie or file name.
  * Matching is case- and umlaut-insensitive for German ("übersetzen" finds
    "Übersetzen", "straße" finds "STRASSE"). SQLite only folds ASCII case, so
    text is case-folded in Python once (``search_text``) and the query is
    folded the same way; no database function is involved.
  * Fach, Kategorie and file names are matched in Python against the few
    distinct values and handed to SQL as ``IN`` lists, so renaming or removing
    a file never leaves stale search data behind.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import Select, distinct, func, or_, select
from sqlalchemy.orm import Session

from app.models import ImportFile, Question, QuestionOccurrence, User
from app.moodle_import import plain_text, search_text_from_xml

MAX_TERMS = 8
SORTS = ("newest", "name", "category", "files")
FLAGS = ("duplicate", "conflict", "similar", "issue", "any")


def fold(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold()).strip()


def build_search_text(q: Question) -> str:
    """Case-folded plain text of everything in ``q`` (see module docstring)."""
    if q.raw_xml:
        text = search_text_from_xml(q.raw_xml)
    else:
        parts = [q.name or "", plain_text(q.question_text), plain_text(q.explanation)]
        parts += [plain_text(a.text) for a in q.answers]
        parts += [plain_text(a.feedback or "") for a in q.answers]
        text = " ".join(p for p in parts if p)
    return fold(text)


def parse_terms(query: str | None) -> list[str]:
    return [fold(t) for t in (query or "").split()][:MAX_TERMS]


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@dataclass
class BankFilter:
    q: str | None = None
    fach: str | None = None
    category: str | None = None
    import_file_id: int | None = None
    source: str | None = None        # import | ai
    qtype: str | None = None
    flag: str | None = None          # see FLAGS
    exported: str | None = None      # yes | no
    # Resolved lazily by the caller (they need the whole bank):
    flagged_ids: set[int] | None = None
    exported_ids: set[int] | None = None
    terms: list[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.terms = parse_terms(self.q)


def apply_filters(stmt: Select, db: Session, owner: User, f: BankFilter,
                  skip: str | None = None) -> Select:
    """Add the WHERE clauses of ``f``; ``skip`` leaves one facet out."""
    stmt = stmt.where(Question.owner_id == owner.id)

    if f.terms:
        files = [(i, fold(n)) for i, n in db.execute(
            select(ImportFile.id, ImportFile.filename).where(ImportFile.owner_id == owner.id))]
        pairs = db.execute(
            select(distinct(Question.fach), Question.category).where(Question.owner_id == owner.id)
        ).all()
        for term in f.terms:
            file_ids = [i for i, name in files if term in name]
            fachs = {fa for fa, _ in pairs if fa and term in fold(fa)}
            cats = {c for _, c in pairs if c and term in fold(c)}
            clauses = [Question.search_text.like(_like(term), escape="\\")]
            if file_ids:
                clauses.append(Question.occurrences.any(QuestionOccurrence.import_file_id.in_(file_ids)))
            if fachs:
                clauses.append(Question.fach.in_(fachs))
            if cats:
                clauses.append(Question.category.in_(cats))
            stmt = stmt.where(or_(*clauses))

    if f.fach and skip != "fach":
        stmt = stmt.where(Question.fach == f.fach)
    if f.category and skip != "category":
        stmt = stmt.where(Question.category == f.category)
    if f.import_file_id and skip != "file":
        stmt = stmt.where(Question.occurrences.any(QuestionOccurrence.import_file_id == f.import_file_id))
    if f.qtype and skip != "type":
        stmt = stmt.where(Question.question_type == f.qtype)
    if f.source == "import":
        stmt = stmt.where(Question.ai_generated.is_(False))
    elif f.source == "ai":
        stmt = stmt.where(Question.ai_generated.is_(True))
    if f.flag and f.flagged_ids is not None:
        stmt = stmt.where(Question.id.in_(f.flagged_ids or {-1}))
    if f.exported == "yes" and f.exported_ids is not None:
        stmt = stmt.where(Question.id.in_(f.exported_ids or {-1}))
    elif f.exported == "no" and f.exported_ids:
        stmt = stmt.where(Question.id.not_in(f.exported_ids))
    return stmt


def order_by(stmt: Select, sort: str) -> Select:
    if sort == "name":
        return stmt.order_by(func.lower(Question.name), Question.id)
    if sort == "category":
        return stmt.order_by(Question.fach, Question.category, func.lower(Question.name), Question.id)
    if sort == "files":
        count = (select(func.count(QuestionOccurrence.id))
                 .where(QuestionOccurrence.question_id == Question.id).scalar_subquery())
        return stmt.order_by(count.desc(), Question.id.desc())
    return stmt.order_by(Question.id.desc())


def facets(db: Session, owner: User, f: BankFilter) -> dict:
    """Counts for the filter dropdowns.

    Each facet is counted with all *other* filters applied but not its own, so
    the numbers show what choosing a value would give.
    """
    def counts(column, skip: str) -> list[tuple]:
        stmt = apply_filters(select(column, func.count(distinct(Question.id))), db, owner, f, skip)
        return db.execute(stmt.group_by(column)).all()

    fach = sorted(((v, n) for v, n in counts(Question.fach, "fach") if v), key=lambda x: x[0].casefold())
    cat = sorted(((v, n) for v, n in counts(Question.category, "category") if v), key=lambda x: x[0].casefold())
    types = sorted(((v, n) for v, n in counts(Question.question_type, "type") if v), key=lambda x: -x[1])

    file_stmt = apply_filters(
        select(ImportFile.id, ImportFile.filename, func.count(distinct(Question.id)))
        .join(QuestionOccurrence, QuestionOccurrence.import_file_id == ImportFile.id)
        .join(Question, Question.id == QuestionOccurrence.question_id),
        db, owner, f, "file",
    )
    files = db.execute(file_stmt.group_by(ImportFile.id, ImportFile.filename)).all()
    files = sorted(files, key=lambda x: x[1].casefold())

    return {
        "fach": [{"value": v, "count": n} for v, n in fach],
        "category": [{"value": v, "count": n} for v, n in cat],
        "type": [{"value": v, "count": n} for v, n in types],
        "file": [{"id": i, "value": name, "count": n} for i, name, n in files],
    }


def flagged_question_ids(analysis: dict, flag: str) -> set[int]:
    ids: set[int] = set()
    if flag in ("duplicate",):
        ids |= {e["question"]["id"] for e in analysis["exact"]}
    if flag in ("conflict", "any"):
        ids |= {q["id"] for g in analysis["conflicts"] for q in g["questions"]}
    if flag in ("similar", "any"):
        ids |= {p["a"]["id"] for p in analysis["similar"]} | {p["b"]["id"] for p in analysis["similar"]}
    if flag in ("issue", "any"):
        ids |= {i["question"]["id"] for i in analysis["issues"]}
    return ids


def all_flagged_ids(analysis: dict) -> set[int]:
    """Questions that should not go into a test unchecked."""
    return flagged_question_ids(analysis, "any")


# kept for type checkers: re-exported names used by the API layer
__all__ = ["BankFilter", "apply_filters", "build_search_text", "facets", "fold",
           "flagged_question_ids", "all_flagged_ids", "order_by", "parse_terms", "SORTS", "FLAGS"]
