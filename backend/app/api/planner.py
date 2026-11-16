from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.exam_planner.service import MAX_STUDENTS, Slot, allocate_percent, build_plan, distribution_csv
from app.models import User
from app.security.deps import get_current_user

logger = logging.getLogger("app.planner")
router = APIRouter(prefix="/api/planner", tags=["test planner"])


class SlotIn(BaseModel):
    fach: str | None = Field(default=None, max_length=255)
    category: str = Field(min_length=1, max_length=1000)
    count: int | None = Field(default=None, ge=1, le=50)
    percent: float | None = Field(default=None, gt=0, le=100)


class PlanIn(BaseModel):
    slots: list[SlotIn] = Field(min_length=1, max_length=20)
    students: int = Field(default=100, ge=1, le=MAX_STUDENTS)
    seed: int | None = Field(default=None, ge=1, lt=2**31)
    only_unused: bool = False
    total: int | None = Field(default=None, ge=1, le=100, description="Fragen pro Person im Prozentmodus")

    def to_slots(self) -> list[Slot]:
        by_percent = [s.percent is not None for s in self.slots]
        if any(by_percent):
            if not all(by_percent) or any(s.count is not None for s in self.slots):
                raise HTTPException(status_code=422, detail="Bitte entweder überall Prozent oder überall Anzahl angeben.")
            if self.total is None:
                raise HTTPException(status_code=422, detail="Für die Prozentverteilung fehlt die Gesamtzahl der Fragen pro Person.")
            if abs(sum(s.percent for s in self.slots) - 100) > 0.01:
                raise HTTPException(status_code=422, detail="Die Prozentwerte müssen zusammen 100 ergeben.")
            if self.total < len(self.slots):
                raise HTTPException(status_code=422, detail="Die Gesamtzahl ist kleiner als die Zahl der Kategorien.")
            counts = allocate_percent([s.percent for s in self.slots], self.total)
            if 0 in counts:
                raise HTTPException(status_code=422, detail="Bei dieser Gesamtzahl bekäme eine Kategorie 0 Fragen. Bitte Gesamtzahl oder Prozente anpassen.")
        else:
            if any(s.count is None for s in self.slots):
                raise HTTPException(status_code=422, detail="Bitte für jede Kategorie die Anzahl oder den Prozentwert angeben.")
            counts = [s.count for s in self.slots]
        slots = [Slot(s.fach, s.category, c) for s, c in zip(self.slots, counts)]
        if len(set((s.fach, s.category) for s in slots)) != len(slots):
            raise HTTPException(status_code=422, detail="Jede Kategorie darf nur einmal im Plan vorkommen.")
        return slots


@router.post("/plan")
def plan(payload: PlanIn, db: Session = Depends(get_db), current: User = Depends(get_current_user)) -> dict:
    """Clean pool, fairness check and simulation for a test."""
    result = build_plan(db, current, payload.to_slots(), payload.students, payload.seed, payload.only_unused)
    logger.info("user=%s planned test: %d categories, %d students, ok=%s",
                current.id, len(payload.slots), payload.students, result["ok"])
    return result


@router.post("/plan.csv")
def plan_csv(payload: PlanIn, db: Session = Depends(get_db), current: User = Depends(get_current_user)) -> Response:
    """Balanced distribution as CSV (one row per student). Send the ``seed`` of
    a previous plan to get exactly that distribution again."""
    if payload.seed is None:
        raise HTTPException(status_code=422, detail="seed fehlt: zuerst einen Plan erstellen.")
    try:
        text = distribution_csv(db, current, payload.to_slots(), payload.students, payload.seed, payload.only_unused)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return Response(
        content="﻿" + text,   # BOM so Excel reads the umlauts correctly
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="verteilungsplan.csv"'},
    )
