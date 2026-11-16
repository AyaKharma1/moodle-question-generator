"""The import report says openly what was and was not checked."""
from __future__ import annotations

import io


def _q(qtype, name, text, answers=None):
    body = "".join(f'<answer fraction="{f}"><text>{t}</text></answer>' for f, t in (answers or []))
    return (f'<question type="{qtype}"><name><text>{name}</text></name>'
            f'<questiontext format="html"><text><![CDATA[{text}]]></text></questiontext>{body}</question>')


def _cat(path):
    return f'<question type="category"><category><text>{path}</text></category></question>'


def _import(client, xml, name="datei.xml"):
    r = client.post("/api/bank/import", files=[("files", (name, io.BytesIO(xml.encode()), "text/xml"))])
    assert r.status_code == 200, r.text
    return r.json()[0]


MIXED = (
    "<quiz>"
    + _q("truefalse", "Ohne Kategorie", "Diese Frage steht vor jeder Kategorie.", [(100, "true"), (0, "false")])
    + _cat("$course$/top/Info/Kapitel 1")
    + _q("multichoice", "MC", "Welche Aussage stimmt zum ersten Thema?", [(100, "Richtig"), (0, "Falsch")])
    + _q("cloze", "Lücke", "Setzen Sie {1:MC:=a~b} ein.")
    + _q("essay", "Aufsatz", "Erklären Sie das zweite Thema ausführlich.")
    + _q("description", "Hinweis", "Nur ein Lehrtext ohne Aufgabe.")
    + _q("multichoice", "Bild", '<img src="@@PLUGINFILE@@/diagramm.png">Was zeigt das dritte Diagramm?', [(100, "Eins"), (0, "Zwei")])
    + _q("multichoice", "MC", "Welche Aussage stimmt zum ersten Thema?", [(100, "Richtig"), (0, "Falsch")])   # same question twice
    + "</quiz>"
)


def test_report_lists_types_categories_and_openly_names_what_is_not_checked(auth_client):
    res = _import(auth_client, MIXED)
    report = res["report"]
    types = {t["type"]: t["count"] for t in report["types"]}
    assert types == {"multichoice": 3, "truefalse": 1, "cloze": 1, "essay": 1, "description": 1}
    assert {c["name"]: c["count"] for c in report["categories"]} == {"Ohne Kategorie": 1, "Info / Kapitel 1": 6}

    by_code = {}
    for w in report["warnings"]:
        by_code.setdefault(w["code"], []).append(w)
    assert by_code["missing_media"][0]["severity"] == "critical" and by_code["missing_media"][0]["count"] == 1
    assert by_code["uncategorized"][0]["severity"] == "review" and by_code["uncategorized"][0]["count"] == 1
    unchecked = {w["text"].split(" vom Typ ")[1].split(" werden")[0] for w in by_code["not_checked"]}
    assert unchecked == {"Lückentext (Cloze)", "Freitext"}                   # named, not hidden
    assert all(w["severity"] == "info" for w in by_code["not_checked"])
    assert by_code["description"][0]["count"] == 1 and "keine Fragen" in by_code["description"][0]["text"]
    assert by_code["repeated_in_file"][0]["count"] == 1
    assert report["media"] == {"with_files": 1, "missing": 1}


def test_report_is_kept_with_the_file(auth_client):
    _import(auth_client, MIXED, "gemischt.xml")
    files = auth_client.get("/api/bank/files").json()
    assert files[0]["report"]["media"]["missing"] == 1
    assert any(w["code"] == "not_checked" for w in files[0]["report"]["warnings"])


def test_clean_file_has_no_warnings(auth_client):
    xml = ("<quiz>" + _cat("$course$/top/Info/Sauber")
           + _q("multichoice", "A", "Was ist ein Primärschlüssel genau?", [(100, "Eindeutig"), (0, "Mehrdeutig")])
           + _q("truefalse", "B", "Ein Index beschleunigt Abfragen immer.", [(0, "true"), (100, "false")]) + "</quiz>")
    res = _import(auth_client, xml)
    assert res["report"]["warnings"] == []
    assert {t["name"] for t in res["report"]["types"]} == {"Multiple Choice", "Wahr/Falsch"}


def test_file_without_questions_is_refused_with_advice(auth_client):
    res = _import(auth_client, "<quiz>" + _cat("$course$/top/Leer") + "</quiz>", "leer.xml")
    assert res["error"] and "keine Fragen" in res["error"] and "Kategorie mit Fragen" in res["error"]
    assert auth_client.get("/api/bank/files").json() == []


def test_unknown_question_types_are_carried_over_and_named(auth_client):
    xml = "<quiz>" + _cat("$course$/top/X") + _q("seltsamertyp", "S", "Eine Frage eines Plugin-Typs.") + "</quiz>"
    res = _import(auth_client, xml)
    assert res["error"] is None and res["new"] == 1
    assert "Fragetyp „seltsamertyp“" in res["report"]["warnings"][0]["text"]
    q = auth_client.get("/api/questions").json()[0]
    assert q["question_type"] == "seltsamertyp"
