"""Test planner: clean pool, fairness numbers and distribution."""
from __future__ import annotations

import csv
import io
from pathlib import Path

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
WS24, SS25, DB24 = ("moodle_computersysteme_ws2024.xml", "moodle_computersysteme_ss2025.xml",
                    "moodle_datenbanken_ws2024.xml")
CS = "Computersysteme"


def _import(client, *names):
    files = [("files", (n, io.BytesIO((SAMPLES / n).read_bytes()), "text/xml")) for n in names]
    assert client.post("/api/bank/import", files=files).status_code == 200


def _plan(client, slots, **extra):
    r = client.post("/api/planner/plan", json={"slots": slots, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _slot(category, count, fach=CS):
    return {"fach": fach, "category": category, "count": count}


def _quiz(category, *questions, qtype="truefalse"):
    body = "".join(
        f'<question type="{qtype}"><name><text>{n}</text></name>'
        f'<questiontext format="html"><text>{t}</text></questiontext>'
        + ('<answer fraction="100"><text>true</text></answer><answer fraction="0"><text>false</text></answer>'
           if qtype == "truefalse" else "")
        + "</question>" for n, t in questions)
    return (f'<quiz><question type="category"><category><text>{category}</text></category></question>'
            f"{body}</quiz>").encode()


def _words(n):   # n clearly different questions
    topics = ["Prozessor", "Netzwerk", "Datenbank", "Compiler", "Speicher", "Router", "Kernel", "Cache",
              "Treiber", "Firewall", "Scheduler", "Protokoll", "Zeiger", "Rekursion", "Heap", "Stack"]
    return [(f"F{i}", f"Frage zum Thema {topics[i % len(topics)]} Nummer {i} Variante {chr(97 + i)}") for i in range(n)]


def _upload(client, name, data):
    assert client.post("/api/bank/import", files=[("files", (name, io.BytesIO(data), "text/xml"))]).status_code == 200


# ---------------- the pool ----------------

def test_pool_drops_contradicting_broken_and_similar_questions(auth_client):
    _import(auth_client, WS24, SS25, DB24)
    plan = _plan(auth_client, [_slot("PC-Hardware", 2), _slot("Betriebssysteme", 2)], students=9, seed=7)
    hw, os_ = plan["slots"]
    # PC-Hardware: 6 questions, minus the 2 contradicting "CPU Takt" and the broken "Netzwerkkarte"
    assert (hw["pool_before"], hw["pool_size"]) == (6, 3)
    assert {r["name"] for r in hw["removed"]} == {"CPU Takt", "Netzwerkkarte"}
    assert {r["reason"].split(":")[0] for r in hw["removed"]} == {"Widerspruch", "Fehlerhaft"}
    # Betriebssysteme: "Deadlock" and "Deadlock Bedingung" are near-identical, one of them goes
    assert (os_["pool_before"], os_["pool_size"]) == (4, 3)
    assert [r["name"] for r in os_["removed"]] == ["Deadlock Bedingung"]
    assert os_["removed"][0]["reason"].startswith("Zu ähnlich zu")
    assert plan["ok"] and plan["per_paper"] == 4
    assert len(plan["pool_ids"]) == 6 and len(set(plan["pool_ids"])) == 6


def test_description_items_are_not_counted_as_questions(auth_client):
    data = _quiz("$course$/top/C/Kap2", ("Text", "Lehrtext zum Kapitel"), qtype="description") \
        .replace(b"</quiz>", b"".join(
            f'<question type="cloze"><name><text>L{i}</text></name><questiontext format="html">'
            f"<text>Luecke {i} thema{i}</text></questiontext></question>".encode() for i in range(3)) + b"</quiz>")
    _upload(auth_client, "k2.xml", data)
    plan = _plan(auth_client, [_slot("Kap2", 2, fach="C")])
    s = plan["slots"][0]
    assert (s["pool_before"], s["pool_size"]) == (4, 3)
    assert s["removed"][0]["reason"].startswith("Beschreibung")


def test_questions_used_in_earlier_exports_can_be_left_out(auth_client):
    _upload(auth_client, "a.xml", _quiz("$course$/top/M/K", *_words(8)))
    ids = [q["id"] for q in auth_client.get("/api/bank/questions", params={"q": "F1"}).json()["items"]]
    assert auth_client.post("/api/export", json={"question_ids": ids, "filename": "klausur_alt"}).status_code == 200
    everything = _plan(auth_client, [_slot("K", 2, fach="M")])["slots"][0]
    fresh = _plan(auth_client, [_slot("K", 2, fach="M")], only_unused=True)["slots"][0]
    assert everything["pool_size"] == 8
    assert fresh["pool_size"] == 8 - len(ids)
    assert any("früheren Export" in r["reason"] for r in fresh["removed"])


# ---------------- fairness numbers ----------------

def test_too_small_pool_is_reported_instead_of_simulated(auth_client):
    _import(auth_client, WS24, SS25)
    plan = _plan(auth_client, [_slot("PC-Hardware", 4)], students=30, seed=3)
    assert plan["ok"] is False
    assert plan["slots"][0]["level"] == "impossible"
    assert plan["random"] is None and plan["sample_papers"] == []
    assert "nur 3 brauchbare Fragen" in plan["warnings"][0]


def test_overlap_estimate_and_levels(auth_client):
    _upload(auth_client, "big.xml", _quiz("$course$/top/M/Gross", *_words(16)))
    _upload(auth_client, "small.xml", _quiz("$course$/top/M/Klein", *[(f"S{i}", f"Klein {i} anders{i}x") for i in range(5)]))
    plan = _plan(auth_client, [_slot("Gross", 4, "M"), _slot("Klein", 4, "M")], students=50, seed=1)
    big, small = plan["slots"]
    assert (big["level"], big["shared_expected"]) == ("good", 1.0)        # 4*4/16
    assert (small["level"], small["shared_expected"]) == ("small", 3.2)   # 4*4/5
    assert any("Klein" in w and "zu klein" in w for w in plan["warnings"])


def test_simulation_is_valid_and_balanced_plan_overlaps_less(auth_client):
    _upload(auth_client, "p.xml", _quiz("$course$/top/M/Pool", *_words(12)))
    plan = _plan(auth_client, [_slot("Pool", 4, "M")], students=60, seed=11)
    rnd, bal = plan["random"], plan["balanced"]
    assert rnd["unique_papers"] >= 1 and bal["unique_papers"] >= 1
    # every question is used about equally often (60 papers * 4 / 12 questions = 20 each)
    assert bal["usage_max"] - bal["usage_min"] <= 2
    assert bal["usage_max"] - bal["usage_min"] < rnd["usage_max"] - rnd["usage_min"]
    # the average overlap only depends on pool size: both match k*k/n = 1.33
    assert abs(rnd["avg_overlap"] - 16 / 12) < 0.3 and abs(bal["avg_overlap"] - 16 / 12) < 0.3
    assert bal["students_with_identical_paper"] == 0                       # 495 different papers, 60 students
    assert plan["variants_log10"] == round(__import__("math").log10(495), 2)   # C(12,4) = 495
    # a paper has distinct questions only
    for paper in plan["sample_papers"]:
        ids = [q["id"] for q in paper["questions"]]
        assert len(ids) == len(set(ids)) == 4


def test_few_variants_mean_identical_papers_and_a_warning(auth_client):
    _upload(auth_client, "t.xml", _quiz("$course$/top/M/Tiny", *_words(5)))
    plan = _plan(auth_client, [_slot("Tiny", 4, "M")], students=40, seed=5)    # only C(5,4)=5 different papers
    assert plan["random"]["unique_papers"] <= 5
    assert plan["random"]["students_with_identical_paper"] >= 35
    assert any("exakt dieselben Fragen" in w for w in plan["warnings"])


# ---------------- distribution file ----------------

def _csv_rows(client, slots, **extra):
    r = client.post("/api/planner/plan.csv", json={"slots": slots, **extra})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert r.content.startswith(b"\xef\xbb\xbf")
    return list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))


def test_distribution_never_gives_a_student_the_same_or_similar_question_twice(auth_client):
    # three near-identical pairs spread over two categories, plus enough distinct questions
    _upload(auth_client, "a.xml", _quiz("$course$/top/M/A", *_words(10),
            ("Zwilling1", "Was ist ein Mikrocontroller genau und wofuer dient er"),
            ("Zwilling2", "Was ist ein Mikrocontroller genau und wofuer dient er?")))
    _upload(auth_client, "b.xml", _quiz("$course$/top/M/B", *[(f"G{i}", f"Anderes Gebiet {i} thema{i}y") for i in range(10)],
            ("Zwilling3", "Was ist ein Mikrocontroller genau und wofuer dient er!")))
    slots = [_slot("A", 4, "M"), _slot("B", 4, "M")]
    plan = _plan(auth_client, slots, students=120, seed=21)
    removed = {r["name"] for s in plan["slots"] for r in s["removed"]}
    assert len(removed & {"Zwilling1", "Zwilling2", "Zwilling3"}) == 2     # only one of the three twins stays
    rows = _csv_rows(auth_client, slots, students=120, seed=plan["seed"])
    assert rows[0][0] == "Nr" and len(rows) == 121 and len(rows[0]) == 9
    for row in rows[1:]:
        names = row[1:]
        assert len(names) == len(set(names)) == 8                              # no question twice
        assert sum(n.startswith("Zwilling") for n in names) <= 1               # never two twins


def test_same_seed_gives_the_same_distribution(auth_client):
    _upload(auth_client, "p.xml", _quiz("$course$/top/M/Pool", *_words(12)))
    slots = [_slot("Pool", 3, "M")]
    one = _csv_rows(auth_client, slots, students=20, seed=99)
    two = _csv_rows(auth_client, slots, students=20, seed=99)
    other = _csv_rows(auth_client, slots, students=20, seed=100)
    assert one == two and one != other


def test_csv_needs_a_seed_and_a_big_enough_pool(auth_client):
    _upload(auth_client, "p.xml", _quiz("$course$/top/M/Pool", *_words(3)))
    assert auth_client.post("/api/planner/plan.csv", json={"slots": [_slot("Pool", 2, "M")]}).status_code == 422
    assert auth_client.post("/api/planner/plan.csv",
                            json={"slots": [_slot("Pool", 5, "M")], "seed": 4}).status_code == 409


# ---------------- input and privacy ----------------

def test_input_is_validated(auth_client):
    bad = [{"slots": []}, {"slots": [_slot("X", 0)]}, {"slots": [_slot("X", 1)], "students": 0},
           {"slots": [_slot("X", 1)], "students": 5000}]
    for body in bad:
        assert auth_client.post("/api/planner/plan", json=body).status_code == 422
    twice = auth_client.post("/api/planner/plan", json={"slots": [_slot("X", 1), _slot("X", 2)]})
    assert twice.status_code == 422


def test_planner_only_sees_own_questions(auth_client, make_user_client):
    _upload(auth_client, "p.xml", _quiz("$course$/top/M/Pool", *_words(8)))
    other = make_user_client("other@example.com")
    plan = other.post("/api/planner/plan", json={"slots": [_slot("Pool", 2, "M")]}).json()
    assert plan["ok"] is False and plan["slots"][0]["pool_size"] == 0
    assert other.post("/api/planner/plan", json={"slots": [_slot("Pool", 2, "M")]}).status_code == 200


def test_planner_requires_login(client):
    assert client.post("/api/planner/plan", json={"slots": [_slot("X", 1)]}).status_code == 401


def test_similar_questions_are_thinned_out_without_overshooting(auth_client):
    # u is similar to both v and w, but v and w are not similar to each other:
    #   u = w1..w20, v = u without w1..w3, w = u without w18..w20
    words = [f"wort{i:02d}" for i in range(1, 21)]
    u, v, w = " ".join(words), " ".join(words[3:]), " ".join(words[:17])
    _upload(auth_client, "a.xml", _quiz("$course$/top/M/A", ("v", v), ("fillerA", "ganz anderer Text eins alpha"),
                                         ("fillerB", "noch ein Text zwei beta"), ("fillerC", "dritter Text drei gamma")))
    _upload(auth_client, "b.xml", _quiz("$course$/top/M/B", ("w", w), ("u", u)))
    plan = _plan(auth_client, [_slot("A", 1, "M"), _slot("B", 1, "M")], students=10, seed=1)
    a, b = plan["slots"]
    # v is only dropped when u is kept; u goes (it is similar to w too), so v comes back
    assert [p["name"] for p in a["pool"]] == ["v", "fillerA", "fillerB", "fillerC"] and a["removed"] == []
    assert [p["name"] for p in b["pool"]] == ["w"]
    assert [r["name"] for r in b["removed"]] == ["u"] and b["removed"][0]["reason"].startswith("Zu ähnlich zu")
    kept = {p["name"] for s in plan["slots"] for p in s["pool"]}
    assert not ({"u", "v"} <= kept or {"u", "w"} <= kept)                      # no two similar questions together
