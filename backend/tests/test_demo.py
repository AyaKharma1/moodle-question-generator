"""Demo mode: fictitious data, clearly labelled, removable, and it shows the intended story."""
from __future__ import annotations

from app.demo.data import FACH, FILES, Q, TOPICS, build_files


def _load(client):
    r = client.post("/api/demo/load")
    assert r.status_code == 200, r.text
    return r.json()


def test_demo_files_are_labelled_deterministic_and_parse():
    files = build_files()
    assert list(files) == list(FILES.values()) and files == build_files()
    for name, data in files.items():
        text = data.decode()
        assert name.startswith("DEMO_") and "DEMO-DATEN" in text and "Keine echten Hochschuldaten" in text


def test_demo_topic_shares_follow_the_design():
    counts = {t: sum(1 for r in Q if r[0] == t) for t in TOPICS}
    total = sum(counts.values())
    assert [round(100 * counts[t] / total) for t in TOPICS] == [40, 25, 20, 15]


def test_load_status_and_remove(auth_client):
    assert auth_client.get("/api/demo").json()["loaded"] is False
    res = _load(auth_client)
    assert "erfundene" in res["notice"] and len(res["files"]) == 3
    assert auth_client.get("/api/demo").json()["loaded"] is True
    assert auth_client.post("/api/demo/load").status_code == 409
    assert [t["fach"] for t in auth_client.get("/api/bank/overview").json()["tree"]] == [FACH]
    gone = auth_client.delete("/api/demo").json()
    assert gone["loaded"] is False and gone["questions_removed"] > 40
    assert auth_client.get("/api/bank/overview").json()["totals"]["questions"] == 0


def test_demo_does_not_touch_real_files(auth_client):
    from tests.test_quality import _import, DB24
    _import(auth_client, DB24)
    before = auth_client.get("/api/bank/overview").json()["totals"]["questions"]
    _load(auth_client)
    auth_client.delete("/api/demo")
    assert auth_client.get("/api/bank/overview").json()["totals"]["questions"] == before


def test_demo_tells_the_intended_story(auth_client):
    _load(auth_client)
    findings = auth_client.get("/api/bank/findings", params={"state": "all", "page_size": 200}).json()
    by_code = {}
    for f in findings["items"]:
        by_code.setdefault(f["code"], []).append(f["question"]["name"])
    assert sorted(by_code["conflict"]) == ["NULL und Null", "NULL und Null"]
    assert by_code["no_correct_answer"] == ["Sicht Begriff"]
    assert by_code["missing_media"] == ["Bestellung Diagramm"]
    assert {"Sperre Begriff", "Sperre Begriff kurz"} <= set(by_code["similar"])
    assert "ER-Modell erklären" in by_code["not_checked"]
    assert len(by_code["in_several_files"]) >= 10                      # same question in several semesters
    g = auth_client.get("/api/bank/conflicts").json()["items"][0]
    assert {o["filename"] for v in g["variants"] for o in v["origins"]} == {FILES["a"], FILES["c"]}
    cats = {c["name"]: c["count"] for c in auth_client.get("/api/bank/overview").json()["tree"][0]["categories"]}
    assert set(cats) == set(TOPICS) and cats["Transaktionen"] < cats["SQL"]


def test_demo_planner_percent_story(auth_client):
    _load(auth_client)
    slots = [{"fach": FACH, "category": t, "percent": p} for t, p in zip(TOPICS, (40, 25, 20, 15))]
    plan = auth_client.post("/api/planner/plan", json={"slots": slots, "total": 20, "students": 60, "seed": 11}).json()
    assert [s["count"] for s in plan["slots"]] == [8, 5, 4, 3]
    assert plan["ok"] is True
    by = {s["category"]: s for s in plan["slots"]}
    # the conflicting and the broken questions are out of the pool, with a reason
    assert any(r["reason"].startswith("Widerspruch") for r in by["SQL"]["removed"])
    assert any(r["reason"].startswith("Fehlerhaft") for r in by["SQL"]["removed"])
    assert any(r["reason"].startswith("Zu ähnlich") for r in by["Transaktionen"]["removed"])
    assert by["Transaktionen"]["level"] in ("small", "tight") and plan["warnings"]
    assert by["Transaktionen"]["missing_for_recommended"] > 0
    assert plan["fairness"]["disjoint_possible"] is False
