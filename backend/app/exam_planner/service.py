"""Test planner: a fair, repetition-free question pool for a test.

The instructor wants every student to get different questions, and nobody
should get the same or a near-identical question twice. Moodle draws the
questions at random from a category when the quiz is taken, so what can be
guaranteed beforehand is the *pool* it draws from:

  * Only real, trustworthy questions go in: no description items (text only),
    no contradicting versions, no broken questions, optionally none that were
    used in an earlier export.
  * Near-duplicates are thinned out *across all chosen categories*, so a paper
    can never contain two almost identical questions.
  * The pool has to be large enough: with ``n`` questions in a category and
    ``k`` drawn per student, two students share ``k*k/n`` questions on average.

The planner builds that pool, simulates the draw for the given number of
students (the way Moodle does it, purely random, and as a balanced fixed
distribution) and reports overlap and identical papers, so problems show up
before the test does.
"""
from __future__ import annotations

import csv
import io
import math
import random
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Question, QuestionStatus, User
from app.question_bank.service import analysis_cached, export_map, similar_pairs

MAX_STUDENTS = 2000
STATS_SAMPLE = 400          # students compared pairwise (400 -> 79,800 pairs)
SIMILAR_LIMIT = 100_000

# Moodle types that are not gradable questions and cannot be drawn at random.
NOT_QUESTIONS = {"description"}


@dataclass(frozen=True)
class Slot:
    fach: str | None
    category: str
    count: int

    @property
    def label(self) -> str:
        return f"{self.fach} / {self.category}" if self.fach else self.category


def level_for(pool: int, per_student: int) -> str:
    """Same thresholds the overview page uses."""
    if pool < per_student:
        return "impossible"
    if pool <= 2 * per_student:
        return "small"
    if pool < 4 * per_student:
        return "tight"
    return "good"


def _candidates(db: Session, owner: User, slot: Slot) -> list[Question]:
    stmt = select(Question).where(
        Question.owner_id == owner.id,
        Question.status == QuestionStatus.approved.value,
        Question.category == slot.category,
    )
    stmt = stmt.where(Question.fach == slot.fach) if slot.fach else stmt.where(Question.fach.is_(None))
    return list(db.scalars(stmt.order_by(Question.id)))


MAX_REDRAWS = 40


def draw_papers(pools: list[list[int]], counts: list[int], students: int,
                rng: random.Random, balanced: bool) -> list[tuple[int, ...]]:
    """One paper per student: ``counts[i]`` distinct questions from ``pools[i]``.

    ``balanced=False`` is a plain random draw, which is what a Moodle quiz does.

    ``balanced=True`` is a fixed distribution: it always takes the least used
    questions first, so every question is used (almost) equally often, and it
    redraws a paper that another student already has, for as long as enough
    different question sets exist. The *average* overlap between two students
    is the same as with random draws (it only depends on pool size and number
    of questions); what improves is the evenness and the absence of identical
    papers.
    """
    variants = math.prod(math.comb(len(p), k) for p, k in zip(pools, counts))
    usage = [Counter() for _ in pools]
    seen: set[tuple[int, ...]] = set()
    papers: list[tuple[int, ...]] = []
    for _ in range(students):
        attempts = MAX_REDRAWS if balanced and len(seen) < variants else 1
        for attempt in range(attempts):
            jitter = min(attempt, 3)      # first try: strictly least used; later: allow slight detours
            picks = []
            for i, pool in enumerate(pools):
                if balanced:
                    picks.append(sorted(pool, key=lambda q: (usage[i][q] + rng.random() * jitter, rng.random()))[: counts[i]])
                else:
                    picks.append(rng.sample(pool, counts[i]))
            paper = tuple(sorted(q for picked in picks for q in picked))
            if paper not in seen:
                break
        for i, picked in enumerate(picks):
            usage[i].update(picked)
        seen.add(paper)
        papers.append(paper)
    return papers


def paper_stats(papers: list[tuple[int, ...]], all_ids: list[int]) -> dict:
    index = {qid: n for n, qid in enumerate(all_ids)}
    sample = papers[:STATS_SAMPLE]
    masks = [sum(1 << index[q] for q in p) for p in sample]
    overlaps = [(masks[i] & masks[j]).bit_count()
                for i in range(len(masks)) for j in range(i + 1, len(masks))]
    papers_seen = Counter(papers)
    usage = Counter(q for p in papers for q in p)
    return {
        "avg_overlap": round(sum(overlaps) / len(overlaps), 2) if overlaps else 0.0,
        "max_overlap": max(overlaps, default=0),
        "unique_papers": len(papers_seen),
        # students who hold exactly the same set of questions as someone else
        "students_with_identical_paper": sum(c for c in papers_seen.values() if c > 1),
        "usage_min": min((usage.get(q, 0) for q in all_ids), default=0),
        "usage_max": max((usage.get(q, 0) for q in all_ids), default=0),
    }


def build_plan(db: Session, owner: User, slots: list[Slot], students: int,
               seed: int | None, only_unused: bool) -> dict:
    seed = seed if seed is not None else random.SystemRandom().randrange(1, 2**31)
    analysis = analysis_cached(db, owner)
    conflicted = {q["id"] for g in analysis["conflicts"] for q in g["questions"]}
    broken = {i["question"]["id"]: i["problems"][0] for i in analysis["issues"]}
    used = set(export_map(db, owner)) if only_unused else set()

    # 1. pool per category, without untrustworthy questions
    pools: list[list[Question]] = []
    removed: list[dict[int, str]] = []
    pool_before: list[int] = []
    names: dict[int, str] = {}
    for slot in slots:
        candidates = _candidates(db, owner, slot)
        names.update({q.id: q.name or f"Frage {q.id}" for q in candidates})
        pool_before.append(len(candidates))
        keep, gone = [], {}
        for q in candidates:
            if q.question_type in NOT_QUESTIONS:
                gone[q.id] = "Beschreibung (nur Text, keine bewertbare Frage)"
            elif q.id in conflicted:
                gone[q.id] = "Widerspruch: gleicher Text, andere richtige Antwort"
            elif q.id in broken:
                gone[q.id] = f"Fehlerhaft: {broken[q.id]}"
            elif q.id in used:
                gone[q.id] = "Schon in einem früheren Export verwendet"
            else:
                keep.append(q)
        pools.append(keep)
        removed.append(gone)

    # 2. thin out near-duplicates across ALL categories of the test, so one
    #    paper never contains two almost identical questions
    everyone = [q for pool in pools for q in pool]
    slot_of = {q.id: i for i, pool in enumerate(pools) for q in pool}
    by_id = {q.id: q for q in everyone}
    alive = set(by_id)
    for a, b, _score in sorted(
        ((everyone[i].id, everyone[j].id, s) for i, j, s in similar_pairs(everyone, SIMILAR_LIMIT)),
        key=lambda t: (t[0], t[1]),
    ):
        if a not in alive or b not in alive:
            continue
        # drop the one from the category with more spare questions, then the newer one
        spare = lambda qid: sum(1 for x in pools[slot_of[qid]] if x.id in alive) - slots[slot_of[qid]].count
        victim, keeper = (a, b) if (spare(a), a) > (spare(b), b) else (b, a)
        alive.discard(victim)
        removed[slot_of[victim]][victim] = f"Zu ähnlich zu „{by_id[keeper].name}“"
    pools = [[q for q in pool if q.id in alive] for pool in pools]

    # 3. per-category report
    slot_reports, warnings = [], []
    for slot, pool, gone, before in zip(slots, pools, removed, pool_before):
        level = level_for(len(pool), slot.count)
        enough = len(pool) >= slot.count
        report = {
            "fach": slot.fach, "category": slot.category, "label": slot.label,
            "count": slot.count, "pool_before": before, "pool_size": len(pool),
            "enough": enough, "level": level,
            "shared_expected": round(slot.count * slot.count / len(pool), 1) if pool else None,
            "recommended_min": 4 * slot.count,
            "removed": [{"id": qid, "name": names[qid], "reason": why} for qid, why in gone.items()],
            "pool": [{"id": q.id, "name": q.name} for q in pool],
        }
        slot_reports.append(report)
        if not enough:
            warnings.append(f"„{slot.label}“: nur {len(pool)} brauchbare Fragen, aber {slot.count} pro Person nötig.")
        elif level == "small":
            warnings.append(f"„{slot.label}“: Pool zu klein. Zwei Studierende haben im Schnitt "
                            f"{report['shared_expected']} gleiche Fragen. Empfohlen: mindestens {4 * slot.count}.")
        elif level == "tight":
            warnings.append(f"„{slot.label}“: Pool knapp. Empfohlen: mindestens {4 * slot.count}.")

    result: dict = {
        "seed": seed, "students": students,
        "per_paper": sum(s.count for s in slots),
        "ok": all(r["enough"] for r in slot_reports),
        "slots": slot_reports,
        "pool_ids": [q.id for pool in pools for q in pool],
        "warnings": warnings,
        "variants_log10": None, "random": None, "balanced": None, "sample_papers": [],
    }
    if not result["ok"]:
        return result

    # 4. simulate
    pool_ids = [[q.id for q in pool] for pool in pools]
    counts = [s.count for s in slots]
    all_ids = result["pool_ids"]
    rnd = draw_papers(pool_ids, counts, students, random.Random(seed), balanced=False)
    bal = draw_papers(pool_ids, counts, students, random.Random(seed), balanced=True)
    result["variants_log10"] = round(sum(math.log10(math.comb(len(p), k)) for p, k in zip(pool_ids, counts)), 2)
    result["random"] = paper_stats(rnd, all_ids)
    result["balanced"] = paper_stats(bal, all_ids)
    info = {q.id: q for q in everyone}
    result["sample_papers"] = [
        {"student": n + 1, "questions": [{"id": qid, "name": info[qid].name, "category": info[qid].category}
                                         for qid in paper]}
        for n, paper in enumerate(bal[:5])
    ]
    if result["random"]["students_with_identical_paper"]:
        warnings.append(
            f"Bei zufälliger Auswahl (wie in Moodle) bekommen {result['random']['students_with_identical_paper']} "
            f"von {students} Studierenden exakt dieselben Fragen wie eine andere Person.")
    return result


def distribution_csv(db: Session, owner: User, slots: list[Slot], students: int,
                     seed: int, only_unused: bool) -> str:
    """Balanced fixed distribution: one row per student, one column per question."""
    plan = build_plan(db, owner, slots, students, seed, only_unused)
    if not plan["ok"]:
        raise ValueError("Der Pool ist zu klein für diesen Plan.")
    pool_ids = [[p["id"] for p in s["pool"]] for s in plan["slots"]]
    papers = draw_papers(pool_ids, [s.count for s in slots], students, random.Random(seed), balanced=True)
    names = {p["id"]: p["name"] for s in plan["slots"] for p in s["pool"]}
    slot_of = {qid: i for i, pool in enumerate(pool_ids) for qid in pool}

    header = ["Nr"] + [f"{s.category} {m + 1}" for s in slots for m in range(s.count)]
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(header)
    for n, paper in enumerate(papers, start=1):
        cells: list[str] = []
        for i, s in enumerate(slots):
            cells += [names[q] for q in paper if slot_of[q] == i]
        writer.writerow([n] + cells)
    return out.getvalue()
