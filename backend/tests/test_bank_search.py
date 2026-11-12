"""Bank search: full-text, filters, facets, paging and selection."""
from __future__ import annotations

import io
from pathlib import Path

from app.question_bank.search import build_search_text, fold, parse_terms

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
WS24 = "moodle_computersysteme_ws2024.xml"
SS25 = "moodle_computersysteme_ss2025.xml"
DB24 = "moodle_datenbanken_ws2024.xml"


def _import(client, *names):
    files = [("files", (n, io.BytesIO((SAMPLES / n).read_bytes()), "text/xml")) for n in names]
    r = client.post("/api/bank/import", files=files)
    assert r.status_code == 200, r.text
    return r.json()


def _search(client, **params):
    r = client.get("/api/bank/questions", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _names(page):
    return sorted(q["name"] for q in page["items"])


def _xml(category, *questions):
    body = "".join(
        f'<question type="truefalse"><name><text>{n}</text></name>'
        f'<questiontext format="html"><text>{t}</text></questiontext>'
        '<answer fraction="100"><text>true</text></answer><answer fraction="0"><text>false</text></answer>'
        "</question>" for n, t in questions)
    return (f'<quiz><question type="category"><category><text>{category}</text></category></question>'
            f"{body}</quiz>").encode()


# ---------------- helpers ----------------

def test_fold_handles_german_case_and_eszett():
    assert fold("Übersetzen") == fold("ÜBERSETZEN") == "übersetzen"
    assert fold("Straße") == fold("STRASSE")
    assert parse_terms("  RAM   Speicher ") == ["ram", "speicher"]
    assert len(parse_terms("a b c d e f g h i j")) == 8


# ---------------- what the search looks at ----------------

def test_search_finds_answers_categories_and_file_names(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    assert "RAM Definition" in _names(_search(auth_client, q="Flüchtiger Arbeitsspeicher"))
    assert _names(_search(auth_client, q="zyklisches"))[0] == "Deadlock"       # answer text
    assert _names(_search(auth_client, q="er-modell")) == ["ER-Modell erklären", "Normalformen"]  # category
    in_file = _search(auth_client, q="ss2025")                                   # file name
    assert in_file["total"] == 6
    assert {o["filename"] for q in in_file["items"] for o in q["origins"]} >= {SS25}
    assert _names(_search(auth_client, q="datenbanken sql"))[0] == "Aggregatfunktion"  # fach + category


def test_every_word_must_match_and_case_does_not_matter(auth_client):
    _import(auth_client, WS24, SS25)
    both = _search(auth_client, q="deadlock voraussetzung")
    assert _names(both) == ["Deadlock", "Deadlock Bedingung"]
    assert _names(_search(auth_client, q="DEADLOCK zyklisches")) == ["Deadlock"]
    assert _search(auth_client, q="deadlock gibtsnicht")["total"] == 0
    assert _names(_search(auth_client, q="FLÜCHTIGER")) == ["RAM Definition"]


def test_umlauts_and_eszett_are_matched_regardless_of_case(auth_client):
    data = _xml("$course$/top/Mathe/Basis", ("Straße", "Wie breit ist die STRASSE?"),
                ("Übung", "Die ÜBERSETZUNG ist korrekt."))
    auth_client.post("/api/bank/import", files=[("files", ("m.xml", io.BytesIO(data), "text/xml"))])
    assert _names(_search(auth_client, q="straße")) == ["Straße"]
    assert _names(_search(auth_client, q="STRASSE")) == ["Straße"]
    assert _names(_search(auth_client, q="übersetzung")) == ["Übung"]
    assert _names(_search(auth_client, q="ÜBERSETZUNG")) == ["Übung"]


def test_wildcards_in_the_query_are_taken_literally(auth_client):
    data = _xml("$course$/top/F/K", ("A", "Rabatt 100% sicher"), ("B", "snake_case Name"), ("C", "ganz normal"))
    auth_client.post("/api/bank/import", files=[("files", ("w.xml", io.BytesIO(data), "text/xml"))])
    assert _names(_search(auth_client, q="100%")) == ["A"]
    assert _names(_search(auth_client, q="e_c")) == ["B"]
    assert _search(auth_client, q="%")["total"] == 1
    assert _search(auth_client, q="_")["total"] == 1


def test_matching_questions_are_searchable_by_their_sub_questions(auth_client):
    xml = (
        '<quiz><question type="category"><category><text>$course$/top/C/Basics</text></category></question>'
        '<question type="matching"><name><text>Begriffe</text></name>'
        '<questiontext format="html"><text>Ordnen Sie zu</text></questiontext>'
        '<subquestion format="html"><text>deklarieren</text><answer><text>Benennung</text></answer></subquestion>'
        '<subquestion format="html"><text>initialisieren</text><answer><text>Wertzuweisung</text></answer></subquestion>'
        "</question></quiz>"
    ).encode()
    auth_client.post("/api/bank/import", files=[("files", ("z.xml", io.BytesIO(xml), "text/xml"))])
    assert _names(_search(auth_client, q="wertzuweisung")) == ["Begriffe"]
    assert _names(_search(auth_client, q="deklarieren")) == ["Begriffe"]


# ---------------- filters, sort, paging ----------------

def test_filters_combine_and_facets_show_what_a_choice_would_give(auth_client):
    results = _import(auth_client, WS24, SS25, DB24)
    page = _search(auth_client, fach="Computersysteme")
    assert page["total"] == 10
    fach = {f["value"]: f["count"] for f in page["facets"]["fach"]}
    # a facet ignores its own filter, so the other subject is still listed
    assert fach == {"Computersysteme": 10, "Datenbanken": 5}
    cat = {c["value"]: c["count"] for c in page["facets"]["category"]}
    assert cat == {"Betriebssysteme": 4, "PC-Hardware": 6}
    types = {t["value"]: t["count"] for t in _search(auth_client, q="deadlock")["facets"]["type"]}
    assert types == {"multiple_choice": 2}
    files = {f["id"]: f["count"] for f in _search(auth_client, category="PC-Hardware")["facets"]["file"]}
    # shared questions count in both files: ws2024 has 4 PC-Hardware questions, ss2025 has 3
    assert files == {results[0]["file_id"]: 4, results[1]["file_id"]: 3}
    assert _search(auth_client, type="essay")["total"] == 1
    assert _search(auth_client, file=results[2]["file_id"], q="sql")["total"] == 3


def test_paging_and_sorting(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    first = _search(auth_client, page_size=6, sort="name")
    assert (first["total"], first["pages"], len(first["items"])) == (15, 3, 6)
    names = [q["name"].casefold() for q in first["items"]]
    assert names == sorted(names)
    last = _search(auth_client, page_size=6, page=3, sort="name")
    assert len(last["items"]) == 3
    beyond = _search(auth_client, page_size=6, page=99, sort="name")
    assert beyond["page"] == 3                                  # clamped to the last page
    seen = {q["id"] for p in (1, 2, 3) for q in _search(auth_client, page_size=6, page=p, sort="name")["items"]}
    assert len(seen) == 15                                      # nothing lost or doubled between pages
    by_files = _search(auth_client, sort="files")["items"]
    assert len(by_files[0]["origins"]) == 2                     # questions in several files first
    keys = [(q["fach"], q["category"]) for q in _search(auth_client, sort="category")["items"]]
    assert keys == sorted(keys)


def test_flag_filter_finds_problem_questions(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    assert _names(_search(auth_client, flag="conflict")) == ["CPU Takt", "CPU Takt"]
    assert _names(_search(auth_client, flag="similar")) == ["Deadlock", "Deadlock Bedingung"]
    assert _names(_search(auth_client, flag="issue")) == ["Fremdschlüssel", "Netzwerkkarte", "Normalformen"]
    assert _names(_search(auth_client, flag="duplicate")) == ["RAM Definition", "Scheduler"]
    assert _search(auth_client, flag="any")["total"] == 7
    assert auth_client.get("/api/bank/questions", params={"flag": "nonsense"}).status_code == 422
    assert auth_client.get("/api/bank/questions", params={"sort": "nonsense"}).status_code == 422


def test_exported_filter_finds_questions_never_used(auth_client):
    _import(auth_client, WS24, DB24)
    ids = [q["id"] for q in _search(auth_client, q="sql")["items"]]
    assert auth_client.post("/api/export", json={"question_ids": ids, "filename": "test1"}).status_code == 200
    used = _search(auth_client, exported="yes")
    assert sorted(q["id"] for q in used["items"]) == sorted(ids)
    assert used["items"][0]["exported_in"] == ["test1.xml"]
    assert _search(auth_client, exported="no")["total"] == 11 - len(ids)


# ---------------- selecting across pages ----------------

def test_selectable_ids_cover_all_results_and_can_skip_problem_questions(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    every = auth_client.get("/api/bank/selectable-ids").json()
    assert every["total"] == 15 and every["truncated"] is False
    clean = auth_client.get("/api/bank/selectable-ids", params={"exclude_flagged": True}).json()
    assert clean["total"] == 8                                  # 15 - (2 conflict + 2 similar + 3 broken)
    only_cs = auth_client.get("/api/bank/selectable-ids", params={"fach": "Computersysteme"}).json()
    assert only_cs["total"] == 10
    searched = auth_client.get("/api/bank/selectable-ids", params={"q": "deadlock"}).json()
    assert searched["total"] == 2


# ---------------- files, AI questions, privacy ----------------

def test_file_list_names_the_categories_of_each_file(auth_client):
    _import(auth_client, SS25, DB24)
    files = {f["filename"]: f["categories"] for f in auth_client.get("/api/bank/files").json()}
    assert files[SS25] == ["Betriebssysteme", "PC-Hardware"]
    assert files[DB24] == ["ER-Modell", "SQL"]


def test_ai_questions_are_searchable_and_edits_update_the_index(auth_client):
    doc = auth_client.post("/api/documents", files={"file": ("l.txt", io.BytesIO(
        "Ein Primärschlüssel identifiziert jeden Datensatz einer Tabelle eindeutig. "
        "Die Normalisierung reduziert Redundanz.".encode()), "text/plain")}).json()
    gen = auth_client.post("/api/generate", json={"document_id": doc["id"], "num_questions": 1,
                                                    "fach": "Datenbanken", "category": "Grundlagen"}).json()
    qid = gen["created"][0]["id"]
    assert _search(auth_client, q="primärschlüssel", source="ai")["total"] >= 1
    assert _search(auth_client, q="grundlagen")["total"] == 1                        # category given at generation
    auth_client.put(f"/api/questions/{qid}", json={"question_text": "Was bedeutet Kardinalität genau?"})
    assert _search(auth_client, q="kardinalität")["total"] == 1


def test_search_text_is_built_from_all_parts_of_a_question():
    from app.models import Answer, Question
    q = Question(name="Titel", question_text="<p>Frage <b>Text</b></p>", explanation="<i>Erklärung</i>",
                 question_type="multiple_choice", owner_id=1)
    q.answers = [Answer(text="<p>Antwort A</p>", is_correct=True, feedback="Gut so"), Answer(text="B", is_correct=False)]
    text = build_search_text(q)
    for part in ("titel", "frage text", "erklärung", "antwort a", "gut so"):
        assert part in text
    assert "<" not in text


def test_search_is_private_per_user(auth_client, make_user_client):
    _import(auth_client, DB24)
    other = make_user_client("other@example.com")
    page = other.get("/api/bank/questions", params={"q": "select"}).json()
    assert page["total"] == 0 and page["facets"]["fach"] == []
    assert other.get("/api/bank/selectable-ids").json()["total"] == 0
