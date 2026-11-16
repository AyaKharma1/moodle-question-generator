"""Findings with severity, the lecturer's decisions, conflicts and the history of a question."""
from __future__ import annotations

import io
from pathlib import Path

from lxml import etree

from app.question_bank.findings import CATALOG, SEVERITIES, extra_checks

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
WS24, SS25, DB24 = ("moodle_computersysteme_ws2024.xml", "moodle_computersysteme_ss2025.xml", "moodle_datenbanken_ws2024.xml")


def _import(client, *names):
    files = [("files", (n, io.BytesIO((SAMPLES / n).read_bytes()), "text/xml")) for n in names]
    assert client.post("/api/bank/import", files=files).status_code == 200


def _upload(client, name, xml: str):
    r = client.post("/api/bank/import", files=[("files", (name, io.BytesIO(xml.encode()), "text/xml"))])
    assert r.status_code == 200 and r.json()[0]["error"] is None, r.text


def _findings(client, **params):
    r = client.get("/api/bank/findings", params={"page_size": 200, **params})
    assert r.status_code == 200, r.text
    return r.json()


def _ids(client, **params):
    return {q["name"]: q["id"] for q in client.get("/api/bank/questions", params={"page_size": 200, **params}).json()["items"]}


def _mc(name, text, answers, single="true", cat="$course$/top/T/K"):
    body = "".join(f'<answer fraction="{f}" format="html"><text><![CDATA[{t}]]></text></answer>' for f, t in answers)
    return (f'<quiz><question type="category"><category><text>{cat}</text></category></question>'
            f'<question type="multichoice"><name><text>{name}</text></name>'
            f'<questiontext format="html"><text><![CDATA[{text}]]></text></questiontext>'
            f'<single>{single}</single>{body}</question></quiz>')


def _codes(client, name):
    return {f["code"] for f in _findings(client, state="all")["items"] if f["question"]["name"] == name}


# ---------------- severity, explanation, advice ----------------

def test_every_finding_kind_has_severity_reason_and_advice():
    assert set(SEVERITIES) == {k.severity for k in CATALOG.values()}
    for code, kind in CATALOG.items():
        assert kind.title and len(kind.why) > 40 and len(kind.action) > 20, code


def test_findings_are_grouped_by_severity_and_explained(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    res = _findings(auth_client, state="all")
    assert res["summary"]["open"] == {"critical": 4, "review": 3, "info": 3}
    assert [f["severity"] for f in res["items"]] == sorted((f["severity"] for f in res["items"]), key=SEVERITIES.index)
    assert {f["code"] for f in res["items"]} == {"conflict", "missing_media", "no_correct_answer", "duplicate_answer",
                                                   "similar", "in_several_files", "not_checked"}
    for code in {f["code"] for f in res["items"]}:
        entry = res["catalog"][code]
        assert entry["why"] and entry["action"] and entry["severity_label"] in ("Kritisch", "Überprüfen", "Information")
    only_critical = _findings(auth_client, severity="critical")
    assert {f["code"] for f in only_critical["items"]} == {"conflict", "missing_media", "no_correct_answer"}
    assert _findings(auth_client, code="similar")["total"] == 2
    assert auth_client.get("/api/bank/findings", params={"code": "unsinn"}).status_code == 422


def test_nothing_is_decided_by_the_app(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    assert all(q["decision"] is None for q in auth_client.get("/api/bank/questions", params={"page_size": 200}).json()["items"])


# ---------------- the new checks warn only when they are sure ----------------

def test_single_choice_with_two_full_answers_is_flagged_but_partial_credit_is_not(auth_client):
    _upload(auth_client, "a.xml", _mc("Doppelt", "Welche zwei Aussagen sind richtig zum Thema alpha?", [(100, "Eins"), (100, "Zwei"), (0, "Drei")]))
    _upload(auth_client, "b.xml", _mc("Teilpunkte", "Welche Aussage passt am besten zum Thema beta?", [(100, "Beste"), (50, "Teilweise"), (0, "Falsch")],
                                      cat="$course$/top/T/K2"))
    assert "single_multi_correct" in _codes(auth_client, "Doppelt")
    assert "single_multi_correct" not in _codes(auth_client, "Teilpunkte")          # partial credit is legitimate


def test_weights_must_add_up_to_100_with_rounding_tolerance(auth_client):
    _upload(auth_client, "a.xml", _mc("Falsch80", "Welche Aussagen gelten für das Thema gamma?", [(50, "A"), (30, "B"), (0, "C")], single="false"))
    _upload(auth_client, "b.xml", _mc("Drittel", "Welche Aussagen gelten für das Thema delta?", [(33.33333, "A"), (33.33333, "B"), (33.33333, "C"), (-100, "D")], single="false",
                                      cat="$course$/top/T/K2"))
    assert "weights_not_100" in _codes(auth_client, "Falsch80")
    detail = [f["detail"] for f in _findings(auth_client, code="weights_not_100")["items"]][0]
    assert "80 %" in detail
    assert "weights_not_100" not in _codes(auth_client, "Drittel")                  # 99.99999 is fine


def test_long_correct_answer_and_old_years_are_only_information(auth_client):
    long_right = "Die Normalisierung zerlegt Relationen so, dass Redundanz und Anomalien vermieden werden"
    _upload(auth_client, "a.xml", _mc("Lang", "Was bewirkt die Normalisierung genau?", [(100, long_right), (0, "Sortieren"), (0, "Löschen"), (0, "Kopieren")]))
    _upload(auth_client, "b.xml", _mc("Alt", "Welche Version erschien im Jahr 2014 und im Jahr 2026?", [(100, "Eins"), (0, "Zwei")], cat="$course$/top/T/K2"))
    _upload(auth_client, "c.xml", _mc("Ausgewogen", "Was bewirkt der Index bei Abfragen genau?", [(100, "Schnellere Suche möglich"), (0, "Weniger Speicher nötig"), (0, "Mehr Redundanz erzeugt")],
                                      cat="$course$/top/T/K3"))
    assert "answer_length_outlier" in _codes(auth_client, "Lang")
    assert "answer_length_outlier" not in _codes(auth_client, "Ausgewogen")
    old = [f for f in _findings(auth_client, code="year_mention")["items"]]
    assert len(old) == 1 and "2014" in old[0]["detail"] and "2026" not in old[0]["detail"]
    for f in _findings(auth_client, state="all")["items"]:
        if f["code"] in ("answer_length_outlier", "year_mention"):
            assert f["severity"] == "info"


def test_year_check_depends_on_the_current_year_and_ignores_descriptions():
    from app.models import Question
    q = Question(name="x", question_text="<p>Seit 2019 gilt die Regel, ab 2024 eine neue.</p>", explanation="",
                 question_type="multiple_choice", moodle_type="multichoice", owner_id=1)
    assert extra_checks(q, 2026) == [("year_mention", "Nennt 2019.")]
    assert extra_checks(q, 2030) == [("year_mention", "Nennt 2019, 2024.")]
    assert extra_checks(q, 2020) == []
    q.moodle_type = "description"
    assert extra_checks(q, 2030) == []


# ---------------- decisions: reviewed / excluded / open ----------------

def test_decision_moves_findings_to_done_and_back(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    ids = _ids(auth_client)
    r = auth_client.post(f"/api/bank/questions/{ids['Fremdschlüssel']}/decision", json={"state": "reviewed", "note": "Absicht: Distraktor-Frage"})
    assert r.status_code == 200 and r.json()["decision"] == "reviewed"
    res = _findings(auth_client, state="all")
    assert res["summary"]["open"]["critical"] == 3 and res["summary"]["done"]["critical"] == 1
    done = _findings(auth_client, state="done")["items"]
    assert [f["question"]["name"] for f in done] == ["Fremdschlüssel"] and done[0]["question"]["decision_note"] == "Absicht: Distraktor-Frage"
    assert _findings(auth_client)["summary"]["open"]["critical"] == 3 and all(f["question"]["name"] != "Fremdschlüssel" for f in _findings(auth_client)["items"])
    auth_client.post(f"/api/bank/questions/{ids['Fremdschlüssel']}/decision", json={"state": "open"})
    assert _findings(auth_client)["summary"]["open"]["critical"] == 4
    assert auth_client.post(f"/api/bank/questions/{ids['Fremdschlüssel']}/decision", json={"state": "geloescht"}).status_code == 422


def test_excluded_questions_are_not_offered_exported_or_planned(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    ids = _ids(auth_client)
    auth_client.post(f"/api/bank/questions/{ids['SSD Vorteil']}/decision", json={"state": "excluded", "note": "veraltet"})

    assert ids["SSD Vorteil"] not in auth_client.get("/api/bank/selectable-ids").json()["ids"]
    assert ids["SSD Vorteil"] in auth_client.get("/api/bank/selectable-ids", params={"include_excluded": True}).json()["ids"]
    still_there = auth_client.get("/api/bank/questions", params={"decision": "excluded"}).json()
    assert [q["name"] for q in still_there["items"]] == ["SSD Vorteil"]                  # nothing is deleted

    blocked = auth_client.post("/api/export", json={"question_ids": [ids["SSD Vorteil"], ids["SELECT"]]})
    assert blocked.status_code == 409 and "SSD Vorteil" in blocked.json()["detail"] and "ausgeschlossen" in blocked.json()["detail"]

    plan = auth_client.post("/api/planner/plan", json={"slots": [{"fach": "Computersysteme", "category": "PC-Hardware", "count": 1}], "students": 5, "seed": 1}).json()
    removed = {r["name"]: r["reason"] for r in plan["slots"][0]["removed"]}
    assert removed["SSD Vorteil"] == "Von Ihnen ausgeschlossen"
    assert "SSD Vorteil" not in {p["name"] for p in plan["slots"][0]["pool"]}

    auth_client.post(f"/api/bank/questions/{ids['SSD Vorteil']}/decision", json={"state": "open"})
    assert auth_client.post("/api/export", json={"question_ids": [ids["SSD Vorteil"]]}).status_code == 200


# ---------------- contradictions: side by side, decided only by the lecturer ----------------

def test_conflict_shows_variants_with_their_differences(auth_client):
    _import(auth_client, WS24, SS25)
    groups = auth_client.get("/api/bank/conflicts").json()
    assert groups["total"] == 1
    g = groups["items"][0]
    assert "Taktfrequenz" in g["text"] and g["resolved"] is False and len(g["variants"]) == 2
    first, second = g["variants"]
    assert {o["filename"] for o in first["origins"]} == {WS24} and {o["filename"] for o in second["origins"]} == {SS25}
    assert first["origins"][0]["imported_at"] and first["origins"][0]["category"] == "PC-Hardware"
    right = lambda v: [a["text"] for a in v["answers"] if a["is_correct"]]
    assert right(first) == ["Wahr"] or right(first) == ["true"]
    assert right(first) != right(second)
    assert all(a["differs"] for v in g["variants"] for a in v["answers"])              # both answers flip between the variants


def test_lecturer_decides_which_variant_stays(auth_client):
    _import(auth_client, WS24, SS25)
    g = auth_client.get("/api/bank/conflicts").json()["items"][0]
    keep, other = g["variants"][1]["id"], g["variants"][0]["id"]
    r = auth_client.post(f"/api/bank/conflicts/{g['key']}/decide", json={"keep": keep, "note": "Aktuelle Fassung"})
    assert r.status_code == 200
    assert auth_client.get("/api/bank/conflicts").json()["total"] == 0                     # settled
    settled = auth_client.get("/api/bank/conflicts", params={"state": "done"}).json()["items"][0]
    states = {v["id"]: v["decision"] for v in settled["variants"]}
    assert states == {keep: "reviewed", other: "excluded"}
    notes = {v["id"]: v["decision_note"] for v in settled["variants"]}
    assert "Aktuelle Fassung" in notes[keep] and f"zugunsten von Frage {keep}" in notes[other]
    assert auth_client.get("/api/bank/overview").json()["quality"]["open_conflicts"] == 0

    names = [p["name"] for s in auth_client.post("/api/planner/plan", json={"slots": [{"fach": "Computersysteme", "category": "PC-Hardware", "count": 1}], "students": 3, "seed": 1}).json()["slots"] for p in s["pool"]]
    assert names.count("CPU Takt") == 1                                                    # only the kept variant is used

    auth_client.post(f"/api/bank/conflicts/{g['key']}/reopen")
    assert auth_client.get("/api/bank/conflicts").json()["total"] == 1                     # can be taken back


def test_keeping_all_variants_is_possible_but_they_never_share_a_test(auth_client):
    _import(auth_client, WS24, SS25)
    g = auth_client.get("/api/bank/conflicts").json()["items"][0]
    assert auth_client.post(f"/api/bank/conflicts/{g['key']}/decide", json={"keep": None}).status_code == 200
    assert {v["decision"] for v in auth_client.get("/api/bank/conflicts", params={"state": "done"}).json()["items"][0]["variants"]} == {"reviewed"}
    plan = auth_client.post("/api/planner/plan", json={"slots": [{"fach": "Computersysteme", "category": "PC-Hardware", "count": 2}], "students": 20, "seed": 3}).json()
    pool = [p["name"] for p in plan["slots"][0]["pool"]]
    assert pool.count("CPU Takt") == 1                                                      # same wording: one is thinned out
    assert any(r["name"] == "CPU Takt" and r["reason"].startswith("Zu ähnlich") for r in plan["slots"][0]["removed"])


def test_invalid_conflict_decisions_are_refused(auth_client, make_user_client):
    _import(auth_client, WS24, SS25)
    g = auth_client.get("/api/bank/conflicts").json()["items"][0]
    assert auth_client.post(f"/api/bank/conflicts/{g['key']}/decide", json={"keep": 999999}).status_code == 422
    assert auth_client.post("/api/bank/conflicts/ohnebezug/decide", json={"keep": None}).status_code == 422
    other = make_user_client("other@example.com")
    assert other.post(f"/api/bank/conflicts/{g['key']}/decide", json={"keep": None}).status_code == 422    # not their conflict
    qid = g["variants"][0]["id"]
    assert other.post(f"/api/bank/questions/{qid}/decision", json={"state": "excluded"}).status_code == 404
    assert other.get(f"/api/bank/questions/{qid}/history").status_code == 404
    assert auth_client.get("/api/bank/conflicts").json()["total"] == 1                        # untouched


# ---------------- history of a question ----------------

def test_history_collects_sources_variants_similar_questions_exports_and_findings(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    ids = _ids(auth_client)
    auth_client.post("/api/export", json={"question_ids": [ids["Deadlock"]], "filename": "klausur_ws25", "category_prefix": "Prüfung"})

    deadlock = auth_client.get(f"/api/bank/questions/{ids['Deadlock']}/history").json()
    assert deadlock["question"]["name"] == "Deadlock" and deadlock["question"]["fach"] == "Computersysteme"
    assert [o["filename"] for o in deadlock["origins"]] == [WS24] and deadlock["origins"][0]["imported_at"]
    assert [s["name"] for s in deadlock["similar"]] == ["Deadlock Bedingung"] and deadlock["similar"][0]["score"] >= 0.8
    assert [e["filename"] for e in deadlock["exports"]] == ["klausur_ws25.xml"]
    assert deadlock["conflict"] is False and deadlock["variants"] == []
    assert {f["code"] for f in deadlock["findings"]} == {"similar"}
    assert all(f["why"] and f["action"] and f["title"] for f in deadlock["findings"])

    ram = auth_client.get(f"/api/bank/questions/{ids['RAM Definition']}/history").json()
    assert sorted(o["filename"] for o in ram["origins"]) == sorted([WS24, SS25])                 # one question, two source files
    assert ram["exports"] == []

    cpu = auth_client.get(f"/api/bank/questions/{ids['CPU Takt']}/history").json()
    assert cpu["conflict"] is True and len(cpu["variants"]) == 2 and {f["code"] for f in cpu["findings"]} == {"conflict"}
    assert auth_client.get("/api/bank/questions/99999/history").status_code == 404


# ---------------- overview and hints ----------------

def test_overview_reports_open_findings_and_decisions(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    ids = _ids(auth_client)
    q = auth_client.get("/api/bank/overview").json()["quality"]
    assert q["open"] == {"critical": 4, "review": 3, "info": 3} and q["reviewed"] == 0 and q["excluded"] == 0 and q["open_conflicts"] == 1
    auth_client.post(f"/api/bank/questions/{ids['Netzwerkkarte']}/decision", json={"state": "excluded"})
    auth_client.post(f"/api/bank/questions/{ids['Normalformen']}/decision", json={"state": "reviewed"})
    q = auth_client.get("/api/bank/overview").json()["quality"]
    assert q["open"] == {"critical": 3, "review": 2, "info": 3} and (q["reviewed"], q["excluded"]) == (1, 1)


def test_cards_show_hints_until_the_lecturer_decided(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    ids = _ids(auth_client)
    by_name = lambda: {q["name"]: q for q in auth_client.get("/api/bank/questions", params={"page_size": 200}).json()["items"]}
    assert [f["label"] for f in by_name()["Deadlock"]["flags"]] == ["ähnliche Frage"]
    auth_client.post(f"/api/bank/questions/{ids['Deadlock']}/decision", json={"state": "reviewed"})
    card = by_name()["Deadlock"]
    assert card["flags"] == [] and card["decision"] == "reviewed"


# ---------------- export preview and traceable history ----------------

def test_preview_reports_contents_exclusions_and_warnings_without_side_effects(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    ids = _ids(auth_client)
    auth_client.post(f"/api/bank/questions/{ids['SSD Vorteil']}/decision", json={"state": "excluded", "note": "veraltet"})
    pick = [ids[n] for n in ("SSD Vorteil", "Fremdschlüssel", "Netzwerkkarte", "SELECT")]
    pre = auth_client.post("/api/export/preview", json={"question_ids": pick, "category_prefix": "Klausur", "filename": "k 1"}).json()
    assert pre["count"] == 3 and pre["filename"] == "k_1.xml"
    assert pre["excluded"] == [{"id": ids["SSD Vorteil"], "name": "SSD Vorteil", "reason": "Von Ihnen ausgeschlossen: veraltet"}]
    assert pre["can_export"] is False and "ausgeschlossen" in pre["blocked_reason"].lower() or "Ausgeschlossene" in pre["blocked_reason"]
    assert all(c["path"].startswith("$course$/top/Klausur") for c in pre["categories"]) and sum(c["count"] for c in pre["categories"]) == 3
    assert pre["warnings"]["counts"]["critical"] == 2 and {e["code"] for e in pre["warnings"]["examples"]} == {"missing_media", "no_correct_answer"}
    assert pre["unchanged_originals"] == 3 and pre["generated"] == 0
    assert "Garantie" in pre["disclaimer"] and len(pre["checklist"]) >= 4
    assert auth_client.get("/api/export/history").json() == []                      # preview leaves no trace

    clean = auth_client.post("/api/export/preview", json={"question_ids": [ids["SELECT"]]}).json()
    assert clean["can_export"] is True and clean["excluded"] == [] and clean["warnings"]["counts"] == {"critical": 0, "review": 0, "info": 0}
    assert auth_client.post("/api/export/preview", json={"question_ids": [999999]}).status_code == 404


def test_export_history_keeps_note_summary_and_marks_repeats(auth_client, make_user_client):
    _import(auth_client, WS24, SS25, DB24)
    ids = _ids(auth_client)
    body = {"question_ids": [ids["Fremdschlüssel"], ids["SELECT"]], "filename": "klausur", "note": "Klausur WS 25/26"}
    assert auth_client.post("/api/export", json=body).status_code == 200
    first = auth_client.get("/api/export/history").json()[0]
    assert first["note"] == "Klausur WS 25/26" and first["summary"]["count"] == 2
    assert first["summary"]["warnings"]["counts"]["critical"] == 1                   # recorded as it was at export time
    pre = auth_client.post("/api/export/preview", json={"question_ids": [ids["SELECT"]]}).json()
    assert pre["previously_exported"] == 1 and pre["previous_files"] == ["klausur.xml"]
    other = make_user_client("o@example.com")
    assert other.post("/api/export/preview", json={"question_ids": [ids["SELECT"]]}).status_code == 404
