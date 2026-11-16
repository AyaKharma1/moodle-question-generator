from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ExportHistory, Question, QuestionStatus, User
from app.moodle_export import ExportItem, ExportValidationError, category_path_for, export_bank, with_prefix
from app.question_bank import findings as fx
from app.question_bank.service import export_map, findings_cached
from app.question_management.service import row_to_domain
from app.schemas.api import ExportRequest
from app.security.deps import get_current_user

logger = logging.getLogger("app.export")
router = APIRouter(prefix="/api/export", tags=["export"])

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def _safe_filename(name: str | None) -> str:
    base = _SAFE_NAME.sub("_", (name or "moodle_questions").strip()) or "moodle_questions"
    if not base.endswith(".xml"):
        base += ".xml"
    return base[:100]


def _export_item(q: Question, prefix: str | None = None) -> ExportItem:
    # Imported questions go back exactly as Moodle exported them; their
    # original category path is kept so Moodle restores the same structure.
    if q.raw_xml:
        return ExportItem(
            category_path=with_prefix(q.category_path or category_path_for(q.fach, q.category), prefix),
            raw_xml=q.raw_xml,
        )
    return ExportItem(
        category_path=with_prefix(category_path_for(q.fach, q.category), prefix),
        question=row_to_domain(q),
        name=q.name,
    )


# Said on the preview and in the history: a preview describes the file, it
# cannot promise what Moodle will do with it.
DISCLAIMER = ("Die Vorschau beschreibt die Datei, die erzeugt würde. Sie ist keine Garantie, dass Moodle sie "
              "fehlerfrei importiert. Bitte zuerst in einem Testkurs importieren.")

CHECKLIST = [
    "Datei zuerst in einem Testkurs importieren, nicht im echten Kurs.",
    "In Moodle: Fragensammlung → Importieren → Format „Moodle-XML“ und die Datei wählen.",
    "Moodle erkennt Duplikate beim Import nicht. Dieselbe Datei nicht zweimal importieren.",
    "Nach dem Import die Kategorien und einige Fragen stichprobenartig ansehen (Bilder, Antworten).",
    "Erst danach den Test mit zufälligen Fragen aus diesen Kategorien anlegen.",
]


def _summary(rows: list[Question], prefix: str | None, warnings: dict, previously: dict[int, list[str]]) -> dict:
    types: dict[str, int] = {}
    cats: dict[str, int] = {}
    for r in rows:
        types[r.moodle_type or r.question_type] = types.get(r.moodle_type or r.question_type, 0) + 1
        path = _export_item(r, prefix).category_path
        cats[path] = cats.get(path, 0) + 1
    return {
        "count": len(rows),
        "types": [{"type": t, "count": c} for t, c in sorted(types.items())],
        "categories": [{"path": p, "count": c} for p, c in sorted(cats.items())],
        "warnings": warnings,
        "previously_exported": sum(1 for r in rows if r.id in previously),
    }


def _open_warnings(db: Session, current: User, ids: set[int]) -> dict:
    """Open findings (not yet decided by the lecturer) for exactly these questions."""
    decisions = fx.decisions_of(db, current)
    counts = {s: 0 for s in fx.SEVERITIES}
    examples: list[dict] = []
    for f in fx.with_state(findings_cached(db, current), decisions):
        if f["question_id"] in ids and not f["done"]:
            counts[f["severity"]] += 1
            if len(examples) < 10 and f["severity"] != "info":
                examples.append({"question_id": f["question_id"], "code": f["code"],
                                 "title": fx.CATALOG[f["code"]].title, "detail": f["detail"]})
    return {"counts": counts, "examples": examples}


@router.post("/preview")
def preview(payload: ExportRequest, db: Session = Depends(get_db), current: User = Depends(get_current_user)) -> dict:
    """What an export would contain, without creating a file or a history entry."""
    wanted = list(dict.fromkeys(payload.question_ids))
    rows = {r.id: r for r in db.scalars(select(Question).where(Question.id.in_(wanted), Question.owner_id == current.id))}
    unknown = [q for q in wanted if q not in rows]
    if unknown:
        raise HTTPException(status_code=404, detail="Einige ausgewählte Fragen gibt es nicht mehr. Bitte Auswahl neu aufbauen.")
    excluded, ready = [], []
    for qid in wanted:
        r = rows[qid]
        if r.status != QuestionStatus.approved.value:
            excluded.append({"id": r.id, "name": r.name, "reason": "Nicht freigegeben"})
        elif r.decision == "excluded":
            excluded.append({"id": r.id, "name": r.name, "reason": "Von Ihnen ausgeschlossen"
                             + (f": {r.decision_note}" if r.decision_note else "")})
        else:
            ready.append(r)
    previously = export_map(db, current)
    summary = _summary(ready, payload.category_prefix, _open_warnings(db, current, {r.id for r in ready}), previously)
    raw = sum(1 for r in ready if r.raw_xml)
    return {
        **summary,
        "excluded": excluded,
        "can_export": bool(ready) and not excluded,
        "blocked_reason": ("Ausgeschlossene Fragen müssen aus der Auswahl entfernt werden." if excluded else
                           None if ready else "Die Auswahl ist leer."),
        "unchanged_originals": raw,
        "generated": len(ready) - raw,
        "previous_files": sorted({f for r in ready for f in previously.get(r.id, [])}),
        "filename": _safe_filename(payload.filename),
        "disclaimer": DISCLAIMER,
        "checklist": CHECKLIST,
    }


@router.post("")
def export_xml(
    payload: ExportRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Response:
    rows = list(
        db.scalars(
            select(Question).where(
                Question.id.in_(payload.question_ids),
                Question.owner_id == current.id,
            )
        )
    )
    found_ids = {r.id for r in rows}
    missing = [qid for qid in payload.question_ids if qid not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"Questions not found: {missing}")

    # HARD RULE: only instructor-approved questions may be exported. The AI
    # never publishes anything on its own.
    not_approved = [r.id for r in rows if r.status != QuestionStatus.approved.value]
    if not_approved:
        raise HTTPException(
            status_code=409,
            detail=f"These questions are not approved and cannot be exported: {not_approved}",
        )

    excluded = [r for r in rows if r.decision == "excluded"]
    if excluded:
        names = ", ".join(f"„{r.name or r.id}“" for r in excluded[:5]) + (" …" if len(excluded) > 5 else "")
        raise HTTPException(
            status_code=409,
            detail=f"Diese Fragen haben Sie ausgeschlossen und sie werden nicht exportiert: {names}. "
                   "Zum Exportieren zuerst die Entscheidung auf der Detailseite der Frage zurücknehmen.",
        )

    # Preserve the requested order; a question selected twice is written once.
    by_id = {r.id: r for r in rows}
    ordered = [by_id[qid] for qid in dict.fromkeys(payload.question_ids)]

    try:
        xml = export_bank([_export_item(r, payload.category_prefix) for r in ordered])
    except ExportValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    filename = _safe_filename(payload.filename)
    db.add(ExportHistory(
        owner_id=current.id,
        filename=filename,
        question_count=len(ordered),
        question_ids=[r.id for r in ordered],
        note=(payload.note or "").strip() or None,
        summary=_summary(ordered, payload.category_prefix,
                         _open_warnings(db, current, {r.id for r in ordered}), export_map(db, current)),
    ))
    db.commit()
    logger.info("user=%s exported %d questions to %s", current.id, len(ordered), filename)

    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/history")
def export_history(
    db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> list[dict]:
    rows = list(db.scalars(
        select(ExportHistory).where(ExportHistory.owner_id == current.id).order_by(ExportHistory.id.desc())
    ))
    wanted = {qid for r in rows for qid in r.question_ids or []}
    names = dict(db.execute(
        select(Question.id, Question.name).where(Question.owner_id == current.id, Question.id.in_(wanted or {-1}))
    ).all())
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "question_count": r.question_count,
            "question_ids": r.question_ids,
            # names let the history be searched by question without loading the bank
            "question_names": [names.get(qid) or "gelöschte Frage" for qid in r.question_ids or []],
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "note": r.note,
            "summary": r.summary,
        }
        for r in rows
    ]
