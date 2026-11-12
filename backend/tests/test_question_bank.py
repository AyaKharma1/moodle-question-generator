"""Question bank: Moodle XML import, provenance, duplicates and export."""
from __future__ import annotations

import io
from pathlib import Path

from lxml import etree

from app.moodle_import import (
    MoodleImportError,
    parse_moodle_xml,
    split_category_path,
    split_fach_and_category,
)

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
WS24 = "moodle_computersysteme_ws2024.xml"
SS25 = "moodle_computersysteme_ss2025.xml"
DB24 = "moodle_datenbanken_ws2024.xml"


def _import(client, *names, fach=None, data=None):
    files = [
        ("files", (n, io.BytesIO(data if data is not None else (SAMPLES / n).read_bytes()), "text/xml"))
        for n in names
    ]
    r = client.post("/api/bank/import", files=files, data={"fach": fach} if fach else None)
    assert r.status_code == 200, r.text
    return r.json()


def _by_name(client, **params):
    return {q["name"]: q for q in client.get("/api/questions", params=params).json()}


# ---------------- parser ----------------

def test_category_path_is_split_into_readable_segments():
    assert split_category_path("$course$/top/Computersysteme/PC-Hardware") == [
        "Computersysteme", "PC-Hardware",
    ]
    # Moodle escapes a slash inside a name as "//".
    assert split_category_path("$course$/top/Ein//Ausgabe") == ["Ein/Ausgabe"]
    assert split_fach_and_category(["Computersysteme", "PC-Hardware"], None) == (
        "Computersysteme", "PC-Hardware",
    )
    assert split_fach_and_category(["Kapitel 1"], "Mathe") == ("Mathe", "Kapitel 1")


def test_parser_applies_category_markers_and_keeps_raw_xml():
    questions = parse_moodle_xml((SAMPLES / WS24).read_bytes())
    assert len(questions) == 6
    ram = questions[0]
    assert ram.name == "RAM Definition"
    assert ram.category_segments == ["Computersysteme", "PC-Hardware"]
    assert questions[-1].category_segments == ["Computersysteme", "Betriebssysteme"]
    assert "<![CDATA[" in ram.raw_xml


def test_answer_order_does_not_change_the_fingerprint():
    ws = {q.name: q for q in parse_moodle_xml((SAMPLES / WS24).read_bytes())}
    ss = {q.name: q for q in parse_moodle_xml((SAMPLES / SS25).read_bytes())}
    assert ws["RAM Definition"].fingerprint == ss["RAM Definition"].fingerprint
    # Same text, different correct answer: same text fingerprint, different full one.
    assert ws["CPU Takt"].text_fingerprint == ss["CPU Takt"].text_fingerprint
    assert ws["CPU Takt"].fingerprint != ss["CPU Takt"].fingerprint


def test_parser_rejects_non_moodle_files_and_external_entities():
    for bad in (b"", b"not xml", b"<html></html>"):
        try:
            parse_moodle_xml(bad)
        except MoodleImportError:
            pass
        else:  # pragma: no cover
            raise AssertionError(f"accepted {bad!r}")

    xxe = (
        b'<?xml version="1.0"?><!DOCTYPE quiz [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        b'<quiz><question type="truefalse"><name><text>&x;</text></name>'
        b'<questiontext format="html"><text>t</text></questiontext></question></quiz>'
    )
    parsed = parse_moodle_xml(xxe)
    assert "root:" not in parsed[0].name
    assert "root:" not in parsed[0].raw_xml


# ---------------- import + provenance ----------------

def test_import_several_files_from_different_subjects(auth_client):
    results = _import(auth_client, WS24, SS25, DB24)
    assert [r["error"] for r in results] == [None, None, None]
    assert [r["total"] for r in results] == [6, 6, 5]
    # The second Computersysteme file repeats two questions.
    assert results[1]["existing"] == 2
    assert results[1]["conflicts"] == 1

    overview = auth_client.get("/api/bank/overview").json()
    assert overview["totals"]["files"] == 3
    assert overview["totals"]["questions"] == 15
    tree = {f["fach"]: {c["name"]: c["count"] for c in f["categories"]} for f in overview["tree"]}
    assert tree == {
        "Computersysteme": {"PC-Hardware": 6, "Betriebssysteme": 4},
        "Datenbanken": {"SQL": 3, "ER-Modell": 2},
    }


def test_each_question_knows_every_file_it_came_from(auth_client):
    _import(auth_client, WS24, SS25)
    ram = _by_name(auth_client)["RAM Definition"]
    assert [o["filename"] for o in ram["origins"]] == [WS24, SS25]
    assert ram["fach"] == "Computersysteme"
    assert ram["category"] == "PC-Hardware"
    assert ram["status"] == "approved"
    assert ram["ai_generated"] is False


def test_explicit_fach_overrides_the_category_tree(auth_client):
    _import(auth_client, DB24, fach="Informatik 2")
    q = _by_name(auth_client)["SELECT"]
    assert q["fach"] == "Informatik 2"
    assert q["category"] == "Datenbanken / SQL"


def test_same_file_twice_is_refused(auth_client):
    _import(auth_client, DB24)
    again = _import(auth_client, DB24)
    assert again[0]["error"] and "bereits" in again[0]["error"]
    assert auth_client.get("/api/bank/overview").json()["totals"]["files"] == 1


def test_bad_file_does_not_stop_the_others(auth_client):
    results = auth_client.post("/api/bank/import", files=[
        ("files", ("kaputt.xml", io.BytesIO(b"<quiz"), "text/xml")),
        ("files", ("notiz.txt", io.BytesIO(b"hallo"), "text/plain")),
        ("files", (DB24, io.BytesIO((SAMPLES / DB24).read_bytes()), "text/xml")),
    ]).json()
    assert results[0]["error"] and results[1]["error"]
    assert results[2]["error"] is None and results[2]["new"] == 5


def test_filters_by_fach_category_file_and_text(auth_client):
    results = _import(auth_client, WS24, DB24)
    assert set(_by_name(auth_client, fach="Datenbanken")) == {
        "SELECT", "Fremdschlüssel", "Aggregatfunktion", "Normalformen", "ER-Modell erklären",
    }
    assert set(_by_name(auth_client, category="Betriebssysteme")) == {"Deadlock", "Scheduler"}
    assert len(_by_name(auth_client, import_file_id=results[0]["file_id"])) == 6
    assert set(_by_name(auth_client, q="deadlock")) == {"Deadlock"}


# ---------------- analysis ----------------

def test_analysis_finds_duplicates_conflicts_similar_and_broken_questions(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    a = auth_client.get("/api/bank/analysis").json()
    assert {e["question"]["name"] for e in a["exact"]} == {"RAM Definition", "Scheduler"}
    assert [[q["name"] for q in g["questions"]] for g in a["conflicts"]] == [["CPU Takt", "CPU Takt"]]
    assert [(p["a"]["name"], p["b"]["name"]) for p in a["similar"]] == [("Deadlock", "Deadlock Bedingung")]
    issues = {i["question"]["name"]: i["problems"] for i in a["issues"]}
    assert set(issues) == {"Netzwerkkarte", "Fremdschlüssel", "Normalformen"}
    assert "netzwerkkarte.png" in issues["Netzwerkkarte"][0]


# ---------------- export ----------------

def test_export_keeps_categories_and_original_questions(auth_client):
    _import(auth_client, WS24, DB24)
    questions = auth_client.get("/api/questions").json()
    ids = [q["id"] for q in questions]
    # Selecting a question twice must not duplicate it in the file.
    r = auth_client.post("/api/export", json={"question_ids": ids + ids[:3], "filename": "pruefung"})
    assert r.status_code == 200, r.text
    root = etree.fromstring(r.content)
    real = [q for q in root.findall("question") if q.get("type") != "category"]
    assert len(real) == len(ids)
    paths = [q.findtext("category/text") for q in root.findall("question") if q.get("type") == "category"]
    assert sorted(paths) == sorted([
        "$course$/top/Computersysteme/PC-Hardware", "$course$/top/Computersysteme/Betriebssysteme",
        "$course$/top/Datenbanken/SQL", "$course$/top/Datenbanken/ER-Modell",
    ])
    # Unsupported types (essay) round-trip unchanged.
    essay = [q for q in real if q.get("type") == "essay"]
    assert essay and essay[0].findtext("responsefieldlines") == "10"
    assert b"<![CDATA[" in r.content

    exported = _by_name(auth_client)["SELECT"]
    assert exported["exported_in"] == ["pruefung.xml"]


def test_imported_questions_are_edited_in_moodle_not_here(auth_client):
    _import(auth_client, DB24)
    qid = _by_name(auth_client)["SELECT"]["id"]
    r = auth_client.put(f"/api/questions/{qid}", json={"question_text": "Neu?"})
    assert r.status_code == 409


def test_removing_a_file_keeps_questions_found_elsewhere(auth_client):
    results = _import(auth_client, WS24, SS25)
    assert auth_client.delete(f"/api/bank/files/{results[1]['file_id']}").status_code == 204
    names = _by_name(auth_client)
    # Questions only in SS 2025 are gone, shared ones stay with one origin.
    assert "Prozess vs Thread" not in names
    assert [o["filename"] for o in names["RAM Definition"]["origins"]] == [WS24]
    assert len(auth_client.get("/api/bank/files").json()) == 1


def test_bank_is_private_per_user(auth_client, make_user_client):
    results = _import(auth_client, DB24)
    other = make_user_client("other@example.com")
    assert other.get("/api/questions").json() == []
    assert other.get("/api/bank/overview").json()["totals"]["questions"] == 0
    assert other.delete(f"/api/bank/files/{results[0]['file_id']}").status_code == 404


def test_category_prefix_puts_the_export_in_its_own_categories(auth_client):
    from app.moodle_export import with_prefix
    assert with_prefix("$module$/top/Praktikum/Kapitel 2", "Prüfung WS 25/26") == \
        "$module$/top/Prüfung WS 25//26/Praktikum/Kapitel 2"
    assert with_prefix("$course$/top/A", None) == "$course$/top/A" and with_prefix(None, "X") is None

    _import(auth_client, DB24)
    ids = [q["id"] for q in auth_client.get("/api/questions").json()]
    plain = auth_client.post("/api/export", json={"question_ids": ids})
    prefixed = auth_client.post("/api/export", json={"question_ids": ids, "category_prefix": "Prüfung 1"})
    def paths(r):
        root = etree.fromstring(r.content)
        return sorted(q.findtext("category/text") for q in root.findall("question") if q.get("type") == "category")
    assert paths(plain) == ["$course$/top/Datenbanken/ER-Modell", "$course$/top/Datenbanken/SQL"]
    assert paths(prefixed) == ["$course$/top/Prüfung 1/Datenbanken/ER-Modell", "$course$/top/Prüfung 1/Datenbanken/SQL"]
    # the questions themselves are untouched
    def questions(r):
        return sorted(etree.tostring(q, method="c14n") for q in etree.fromstring(r.content).findall("question")
                      if q.get("type") != "category")
    assert questions(plain) == questions(prefixed)
