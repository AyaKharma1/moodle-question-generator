"""Quality findings: what looks wrong, why it matters and what to do about it.

Every finding has a severity, so a lecturer with little time sees the important
things first:

  * critical ("Kritisch")      the question cannot work as it is
  * review   ("Überprüfen")    probably a problem, only a human can tell
  * info     ("Information")   good to know, nothing is wrong

The app never decides which of several contradicting variants is right. It
shows the differences side by side and records what the lecturer decides
(``Question.decision``): "reviewed" = looked at and accepted, "excluded" = do not
use it in tests or exports. Nothing is deleted.

Detection is cached per state of the bank (see ``service.findings_cached``);
the lecturer's decisions are applied on top at request time, because they
change much more often than the questions do.
"""
from __future__ import annotations

import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from lxml import etree
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ExportHistory, Question, User
from app.moodle_import.parser import normalize, plain_text, safe_parser
from app.moodle_import.report import CHECKED_TYPES, type_name

SEVERITIES = ("critical", "review", "info")
SEVERITY_LABELS = {"critical": "Kritisch", "review": "Überprüfen", "info": "Information"}
DECISIONS = ("open", "reviewed", "excluded")


@dataclass(frozen=True)
class Kind:
    severity: str
    title: str
    why: str
    action: str


CATALOG: dict[str, Kind] = {
    # ---- critical: the question cannot work as it is ----
    "conflict": Kind(
        "critical", "Widerspruch zwischen Varianten",
        "Dieselbe Frage kommt mit unterschiedlichen richtigen Antworten vor. Meist wurde sie in einer Datei korrigiert und in einer anderen nicht.",
        "Beide Varianten nebeneinander ansehen und selbst entscheiden, welche stimmt. Die App entscheidet das nicht. "
        "Die falsche Variante ausschließen und in Moodle korrigieren."),
    "no_correct_answer": Kind(
        "critical", "Keine richtige Antwort markiert",
        "Ohne richtige Antwort kann niemand Punkte bekommen. Die Frage ist so nicht lösbar.",
        "In Moodle eine Antwort als richtig markieren oder die Frage ausschließen."),
    "empty_text": Kind(
        "critical", "Fragetext fehlt",
        "Die Frage hat weder sichtbaren Text noch ein Bild.",
        "In Moodle den Fragetext ergänzen oder die Frage ausschließen."),
    "missing_media": Kind(
        "critical", "Bild oder Datei fehlt",
        "Die Frage verweist auf eine Datei, die nicht in der XML-Datei steht. Nach dem Import fehlt das Bild.",
        "Die Frage in Moodle mit eingebetteten Dateien neu exportieren oder sie ausschließen."),
    # ---- review: probably a problem, a human decides ----
    "similar": Kind(
        "review", "Sehr ähnliche Frage",
        "Zwei Fragen haben fast denselben Wortlaut (mindestens 80 % gemeinsame Wörter). Landen beide im selben Test, wirkt das wie eine Wiederholung. "
        "Die App vergleicht Wörter, nicht die Bedeutung.",
        "Beide ansehen. Ist es dieselbe Frage, eine ausschließen. Unterscheiden sie sich fachlich (z. B. andere Zahlen), als geprüft markieren."),
    "all_correct": Kind(
        "review", "Alle Antworten als richtig markiert",
        "Bei einer Multiple-Choice-Frage sind alle Antwortoptionen richtig. Das ist selten gewollt.",
        "Prüfen, ob eine Antwort falsch sein sollte. Sonst als geprüft markieren."),
    "duplicate_answer": Kind(
        "review", "Antwort doppelt vorhanden",
        "Zwei Antwortoptionen haben denselben Text. Studierende können sie nicht unterscheiden.",
        "In Moodle eine der beiden Antworten ändern oder entfernen."),
    "empty_answer": Kind(
        "review", "Antwortoption ohne Text",
        "Eine Antwortoption ist leer. Sie wird als leere Zeile angezeigt.",
        "In Moodle die Antwort ausfüllen oder entfernen."),
    "single_multi_correct": Kind(
        "review", "Einfachauswahl mit mehreren vollen Antworten",
        "Die Frage ist als Einfachauswahl eingestellt, aber mehrere Antworten geben die volle Punktzahl. Studierende können nur eine wählen.",
        "In Moodle prüfen, ob „Mehrere Antworten erlaubt“ gemeint war, oder die Gewichtung korrigieren."),
    "weights_not_100": Kind(
        "review", "Gewichtung ergibt nicht 100 %",
        "Bei mehreren richtigen Antworten sollen die positiven Gewichte zusammen 100 % ergeben. Sonst ist die volle Punktzahl nicht erreichbar oder wird überschritten.",
        "In Moodle die Gewichte der richtigen Antworten anpassen."),
    # ---- info: good to know ----
    "in_several_files": Kind(
        "info", "In mehreren Dateien vorhanden",
        "Dieselbe Frage steckt in mehreren Exporten. Die Fragenbank speichert sie nur einmal und merkt sich alle Dateien.",
        "Nichts zu tun. Beim Export entsteht kein Duplikat."),
    "answer_length_outlier": Kind(
        "info", "Richtige Antwort auffällig lang",
        "Die richtige Antwort ist deutlich länger als die falschen. Das verrät sie manchmal, weil man sie dann erraten kann. Es ist nur ein Hinweis, die Frage kann trotzdem gut sein.",
        "Prüfen, ob die falschen Antworten ähnlich ausführlich formuliert werden können."),
    "year_mention": Kind(
        "info", "Nennt eine ältere Jahreszahl",
        "Der Fragetext enthält ein Jahr, das mehr als fünf Jahre zurückliegt. Das kann auf veraltete Inhalte hinweisen, muss es aber nicht.",
        "Prüfen, ob die Aussage noch stimmt, und sie sonst in Moodle aktualisieren."),
    "not_checked": Kind(
        "info", "Fragetyp wird nicht geprüft",
        "Dieser Fragetyp wird unverändert übernommen und exportiert. Die App prüft seine Antworten aber nicht.",
        "Nichts nötig. Die Qualität dieser Frage bitte selbst prüfen."),
}


# ------------------------------------------------------------------ detection

def _multichoice_settings(raw_xml: str | None) -> tuple[bool | None, list[float]]:
    """``<single>`` flag and the answer fractions of a Moodle multichoice question."""
    if not raw_xml:
        return None, []
    try:
        el = etree.fromstring(raw_xml.encode("utf-8"), parser=safe_parser())
    except etree.XMLSyntaxError:
        return None, []
    single_el = el.findtext("single")
    single = None if single_el is None else single_el.strip().lower() == "true"
    fractions: list[float] = []
    for a in el.findall("answer"):
        try:
            fractions.append(float(a.get("fraction", "0")))
        except ValueError:
            fractions.append(0.0)
    return single, fractions


def extra_checks(q: Question, current_year: int) -> list[tuple[str, str]]:
    """Checks that only ever *warn*; none of them removes a question from a pool."""
    found: list[tuple[str, str]] = []
    moodle_type = q.moodle_type or q.question_type

    if moodle_type == "multichoice" and q.raw_xml:
        single, fractions = _multichoice_settings(q.raw_xml)
        if single is True and sum(1 for f in fractions if f >= 99.99) > 1:
            found.append(("single_multi_correct", f"{sum(1 for f in fractions if f >= 99.99)} Antworten mit 100 %, aber nur eine Auswahl erlaubt."))
        if single is False:
            positive = sum(f for f in fractions if f > 0)
            if positive and abs(positive - 100) > 0.5:
                found.append(("weights_not_100", f"Die positiven Gewichte ergeben zusammen {positive:g} %."))

    if moodle_type in ("multichoice", "multiple_choice", "shortanswer", "short_answer") and q.answers:
        if any(not plain_text(a.text) and "<img" not in (a.text or "") for a in q.answers):
            found.append(("empty_answer", "Mindestens eine Antwortoption hat keinen Text."))

    if moodle_type in ("multichoice", "multiple_choice") and len(q.answers) >= 3:
        lengths = [len(plain_text(a.text)) for a in q.answers]
        right = [n for n, a in zip(lengths, q.answers) if a.is_correct]
        wrong = [n for n, a in zip(lengths, q.answers) if not a.is_correct]
        if right and wrong:
            median_wrong = statistics.median(wrong)
            longest_right = max(right)
            if median_wrong > 0 and longest_right >= 30 and longest_right >= 2 * median_wrong and longest_right == max(lengths):
                found.append(("answer_length_outlier",
                              f"Die richtige Antwort hat {longest_right} Zeichen, die falschen im Mittel {median_wrong:g}."))

    if moodle_type not in CHECKED_TYPES and moodle_type not in ("multiple_choice", "true_false", "short_answer", "description"):
        found.append(("not_checked", f"Fragetyp: {type_name(moodle_type)}."))

    if moodle_type != "description":
        years = sorted({int(y) for y in re.findall(r"\b(?:19[89]\d|20[0-4]\d)\b", plain_text(q.question_text))})
        old = [y for y in years if y <= current_year - 5]
        if old:
            found.append(("year_mention", f"Nennt {', '.join(str(y) for y in old)}."))
    return found


def build_findings(questions: list[Question], analysis: dict, current_year: int | None = None) -> list[dict]:
    """All findings of a bank. Pure function of the questions and the analysis."""
    year = current_year or datetime.now(timezone.utc).year
    out: list[dict] = []

    def add(qid: int, code: str, detail: str = "", related: list[int] | None = None) -> None:
        out.append({"question_id": qid, "code": code, "severity": CATALOG[code].severity,
                    "detail": detail, "related": related or []})

    for e in analysis["exact"]:
        add(e["question"]["id"], "in_several_files", f"in {e['count']} Dateien")
    for g in analysis["conflicts"]:
        ids = [q["id"] for q in g["questions"]]
        for q in g["questions"]:
            others = [i for i in ids if i != q["id"]]
            add(q["id"], "conflict", f"Widerspricht {len(others)} weiteren Variante(n).", others)
    for p in analysis["similar"]:
        add(p["a"]["id"], "similar", f"Ähnlich zu „{p['b']['name']}“ ({p['score'] * 100:.0f} %).", [p["b"]["id"]])
        add(p["b"]["id"], "similar", f"Ähnlich zu „{p['a']['name']}“ ({p['score'] * 100:.0f} %).", [p["a"]["id"]])
    for i in analysis["issues"]:
        for code, text in zip(i["codes"], i["problems"]):
            add(i["question"]["id"], code, text)
    for q in questions:
        for code, detail in extra_checks(q, year):
            add(q.id, code, detail)

    rank = {s: n for n, s in enumerate(SEVERITIES)}
    out.sort(key=lambda f: (rank[f["severity"]], f["code"], f["question_id"]))
    return out


# ------------------------------------------------------------------ decisions

def decisions_of(db: Session, owner: User) -> dict[int, dict]:
    rows = db.execute(
        select(Question.id, Question.decision, Question.decision_note, Question.decided_at)
        .where(Question.owner_id == owner.id, Question.decision.is_not(None))
    ).all()
    return {qid: {"state": state, "note": note, "at": at} for qid, state, note, at in rows if state in DECISIONS and state != "open"}


def with_state(findings: list[dict], decisions: dict[int, dict]) -> list[dict]:
    """Mark findings as done when the lecturer has decided about the question."""
    out = []
    for f in findings:
        d = decisions.get(f["question_id"])
        out.append({**f, "done": d is not None, "decision": d["state"] if d else None})
    return out


def summarize(findings: list[dict]) -> dict:
    """Counts for the dashboard and the quality page (questions, not findings, per severity)."""
    def blank():
        return {s: set() for s in SEVERITIES}
    open_q, done_q = blank(), blank()
    by_code: dict[str, dict] = defaultdict(lambda: {"open": 0, "done": 0})
    for f in findings:
        (done_q if f["done"] else open_q)[f["severity"]].add(f["question_id"])
        by_code[f["code"]]["done" if f["done"] else "open"] += 1
    return {
        "open": {**{s: len(open_q[s]) for s in SEVERITIES}},
        "done": {**{s: len(done_q[s]) for s in SEVERITIES}},
        "by_code": {code: {**counts, "severity": CATALOG[code].severity} for code, counts in by_code.items()},
    }


class DecisionError(ValueError):
    """The decision cannot be applied (unknown question, not a conflict, ...)."""


def set_decision(db: Session, owner: User, question_id: int, state: str, note: str | None) -> Question:
    if state not in DECISIONS:
        raise DecisionError("Unbekannte Entscheidung.")
    q = db.get(Question, question_id)
    if q is None or q.owner_id != owner.id:
        raise DecisionError("Frage nicht gefunden")
    _apply(q, state, note)
    return q


def _apply(q: Question, state: str, note: str | None) -> None:
    if state == "open":
        q.decision = q.decision_note = q.decided_at = None
    else:
        q.decision, q.decision_note = state, (note or "").strip() or None
        q.decided_at = datetime.now(timezone.utc)


def conflict_members(db: Session, owner: User, text_fingerprint: str) -> list[Question]:
    members = list(db.scalars(
        select(Question).where(Question.owner_id == owner.id, Question.text_fingerprint == text_fingerprint)
        .options(selectinload(Question.answers)).order_by(Question.id)
    ))
    if len({m.fingerprint for m in members}) < 2:
        raise DecisionError("Zu dieser Frage gibt es keinen Widerspruch.")
    return members


def group_resolved(ids: list[int], decisions: dict[int, dict]) -> bool:
    """A conflict is settled when at most one variant is still in use, or all remaining ones were reviewed."""
    in_use = [i for i in ids if decisions.get(i, {}).get("state") != "excluded"]
    return len(in_use) <= 1 or all(decisions.get(i, {}).get("state") == "reviewed" for i in in_use)


def decide_conflict(db: Session, owner: User, text_fingerprint: str, keep: int | None, note: str | None) -> list[Question]:
    """Record the lecturer's decision. ``keep`` = the variant that stays; ``None`` = all variants stay."""
    members = conflict_members(db, owner, text_fingerprint)
    ids = [m.id for m in members]
    if keep is not None and keep not in ids:
        raise DecisionError("Die gewählte Variante gehört nicht zu diesem Widerspruch.")
    extra = f" {note.strip()}" if note and note.strip() else ""
    for m in members:
        if keep is None:
            _apply(m, "reviewed", f"Widerspruch geprüft: alle Varianten bleiben.{extra}")
        elif m.id == keep:
            _apply(m, "reviewed", f"Widerspruch geprüft: diese Variante ist maßgeblich.{extra}")
        else:
            _apply(m, "excluded", f"Widerspruch geprüft: ausgeschlossen zugunsten von Frage {keep}.{extra}")
    return members


def reopen_conflict(db: Session, owner: User, text_fingerprint: str) -> list[Question]:
    members = conflict_members(db, owner, text_fingerprint)
    for m in members:
        _apply(m, "open", None)
    return members


# ------------------------------------------------------------------ history

def _origins(q: Question) -> list[dict]:
    return [{"file_id": o.import_file_id, "filename": o.import_file.filename,
             "imported_at": o.import_file.created_at.isoformat() if o.import_file.created_at else None,
             "fach": o.fach, "category": o.category} for o in q.occurrences]


def variant_view(members: list[Question]) -> list[dict]:
    """Variants side by side. An answer ``differs`` when it is right in one variant and
    wrong, or missing, in another."""
    seen: dict[str, set] = defaultdict(set)
    for m in members:
        present = {normalize(a.text): a.is_correct for a in m.answers}
        for key in {normalize(a.text) for x in members for a in x.answers}:
            seen[key].add(present.get(key, "fehlt"))
    return [{
        "id": m.id, "name": m.name, "label": f"Variante {n}", "fach": m.fach, "category": m.category,
        "decision": m.decision, "decision_note": m.decision_note,
        "origins": _origins(m),
        "answers": [{"text": plain_text(a.text), "is_correct": a.is_correct,
                     "differs": len(seen[normalize(a.text)]) > 1} for a in m.answers],
    } for n, m in enumerate(members, start=1)]


def conflict_groups(db: Session, owner: User, analysis: dict, state: str, page: int, page_size: int) -> dict:
    decisions = decisions_of(db, owner)
    groups = []
    for g in analysis["conflicts"]:
        ids = [q["id"] for q in g["questions"]]
        resolved = group_resolved(ids, decisions)
        if state == "open" and resolved or state == "done" and not resolved:
            continue
        groups.append((ids, resolved))
    total = len(groups)
    chunk = groups[(page - 1) * page_size: page * page_size]
    out = []
    for ids, resolved in chunk:
        members = list(db.scalars(select(Question).where(Question.id.in_(ids))
                                  .options(selectinload(Question.answers)).order_by(Question.id)))
        out.append({
            "key": members[0].text_fingerprint,
            "text": plain_text(members[0].question_text)[:400],
            "resolved": resolved,
            "variants": variant_view(members),
        })
    return {"items": out, "total": total, "page": page, "page_size": page_size}


def question_history(db: Session, owner: User, qid: int, findings: list[dict], analysis: dict) -> dict | None:
    q = db.scalar(select(Question).where(Question.id == qid, Question.owner_id == owner.id)
                  .options(selectinload(Question.answers)))
    if q is None:
        return None
    variants_rows = list(db.scalars(
        select(Question).where(Question.owner_id == owner.id, Question.text_fingerprint == q.text_fingerprint)
        .options(selectinload(Question.answers)).order_by(Question.id)
    )) if q.text_fingerprint else [q]
    conflict = len({m.fingerprint for m in variants_rows}) > 1

    similar = []
    for p in analysis["similar"]:
        other = p["b"] if p["a"]["id"] == qid else p["a"] if p["b"]["id"] == qid else None
        if other:
            similar.append({"id": other["id"], "name": other["name"], "text": other["text"], "score": p["score"],
                            "fach": other["fach"], "category": other["category"], "origins": other["origins"]})
    similar.sort(key=lambda s: -s["score"])

    exports = [{"id": h.id, "filename": h.filename, "created_at": h.created_at.isoformat() if h.created_at else None,
                "note": h.note}
               for h in db.scalars(select(ExportHistory).where(ExportHistory.owner_id == owner.id).order_by(ExportHistory.id.desc()))
               if qid in (h.question_ids or [])]

    return {
        "question": {
            "id": q.id, "name": q.name, "question_type": q.question_type, "type_name": type_name(q.moodle_type or q.question_type),
            "fach": q.fach, "category": q.category, "status": q.status, "ai_generated": q.ai_generated,
            "text": plain_text(q.question_text), "explanation": plain_text(q.explanation),
            "answers": [{"text": plain_text(a.text), "is_correct": a.is_correct, "feedback": plain_text(a.feedback or "")} for a in q.answers],
            "decision": q.decision, "decision_note": q.decision_note,
            "decided_at": q.decided_at.isoformat() if q.decided_at else None,
            "created_at": q.created_at.isoformat() if q.created_at else None,
            "text_fingerprint": q.text_fingerprint,
        },
        "origins": _origins(q),
        "conflict": conflict,
        "variants": variant_view(variants_rows) if conflict else [],
        "similar": similar[:10],
        "exports": exports,
        "findings": [{**f, "title": CATALOG[f["code"]].title, "why": CATALOG[f["code"]].why,
                      "action": CATALOG[f["code"]].action}
                     for f in findings if f["question_id"] == qid],
    }


# ------------------------------------------------------------------ card hints

_CARD_KIND = {"critical": "danger", "review": "warn", "info": "info"}


def hint_map(findings: list[dict], decisions: dict[int, dict]) -> dict[int, list[dict]]:
    """Short badges for the question cards. Only what needs attention is shown on
    the card (critical, review, and "in several files"); the rest is on the detail
    page. A question the lecturer already decided about shows no hints."""
    hints: dict[int, list[dict]] = defaultdict(list)
    for f in findings:
        if f["question_id"] in decisions:
            continue
        code = f["code"]
        if code == "conflict":
            hints[f["question_id"]].append({"label": "Widerspruch", "kind": "danger"})
        elif code == "similar":
            hints[f["question_id"]].append({"label": "ähnliche Frage", "kind": "violet"})
        elif code == "in_several_files":
            hints[f["question_id"]].append({"label": f["detail"], "kind": "info"})
        elif f["severity"] in ("critical", "review"):
            # the problem texts of the technical checks are specific ("Bild fehlt in der Datei: x.png")
            label = f["detail"] if code in ("no_correct_answer", "empty_text", "missing_media", "all_correct", "duplicate_answer") else CATALOG[code].title
            hints[f["question_id"]].append({"label": label, "kind": _CARD_KIND[f["severity"]]})
    return hints
