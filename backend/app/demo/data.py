"""Fictitious demo question bank "Datenbanksysteme (DEMO)".

Everything here is invented for demonstration. It is NOT real university data
and no question comes from a real exam. The three files imitate Moodle exports
of three semesters and contain realistic imperfections on purpose:

  * the same question in several files (duplicates across semesters),
  * one contradiction (same wording, different correct answer),
  * two almost identical questions,
  * a question without a correct answer, one with a missing image,
  * a free-text question that the app only carries along,
  * categories of very different size (Transaktionen is small).

Topic shares of the pool: SQL 40 %, Normalisierung 25 %, ER-Modellierung 20 %,
Transaktionen 15 % (by design, see ``expected_shares``).
"""
from __future__ import annotations

from xml.sax.saxutils import escape

FACH = "Datenbanksysteme (DEMO)"
PREFIX = "DEMO_"
FILES = {
    "a": f"{PREFIX}Datenbanksysteme_WS2023.xml",
    "b": f"{PREFIX}Datenbanksysteme_SS2024.xml",
    "c": f"{PREFIX}Datenbanksysteme_WS2024.xml",
}
TOPICS = ["SQL", "Normalisierung", "ER-Modellierung", "Transaktionen"]

# (topic, name, text, [(fraction, answer)], files-it-appears-in)   single choice unless marked
R, W = 100, 0
Q: list[tuple] = [
    # ---- SQL (16) ----
    ("SQL", "SELECT Grundform", "Mit welchem Befehl liest man Zeilen aus einer Tabelle?", [(R, "SELECT"), (W, "INSERT"), (W, "ALTER"), (W, "GRANT")], "abc"),
    ("SQL", "WHERE Klausel", "Wofür wird die WHERE-Klausel verwendet?", [(R, "Zum Filtern von Zeilen"), (W, "Zum Sortieren"), (W, "Zum Gruppieren"), (W, "Zum Löschen der Tabelle")], "ab"),
    ("SQL", "ORDER BY", "Welche Klausel sortiert das Ergebnis einer Abfrage?", [(R, "ORDER BY"), (W, "GROUP BY"), (W, "HAVING"), (W, "LIMIT")], "abc"),
    ("SQL", "GROUP BY Zweck", "Was bewirkt GROUP BY zusammen mit COUNT(*)?", [(R, "Es zählt die Zeilen je Gruppe"), (W, "Es löscht doppelte Zeilen"), (W, "Es sortiert absteigend"), (W, "Es verbindet zwei Tabellen")], "bc"),
    ("SQL", "HAVING", "Welche Klausel filtert Gruppen nach der Aggregation?", [(R, "HAVING"), (W, "WHERE"), (W, "DISTINCT"), (W, "UNION")], "a"),
    ("SQL", "INNER JOIN", "Was liefert ein INNER JOIN zweier Tabellen?", [(R, "Nur Zeilen mit passendem Partner in beiden Tabellen"), (W, "Alle Zeilen der linken Tabelle"), (W, "Das Kreuzprodukt ohne Bedingung"), (W, "Nur Zeilen ohne Partner")], "abc"),
    ("SQL", "LEFT JOIN", "Welche Zeilen enthält ein LEFT JOIN zusätzlich zum INNER JOIN?", [(R, "Zeilen der linken Tabelle ohne Partner"), (W, "Zeilen der rechten Tabelle ohne Partner"), (W, "Keine weiteren Zeilen"), (W, "Nur doppelte Zeilen")], "bc"),
    ("SQL", "NULL Vergleich", "Wie prüft man in SQL, ob ein Wert NULL ist?", [(R, "Mit IS NULL"), (W, "Mit = NULL"), (W, "Mit == NULL"), (W, "Mit LIKE NULL")], "ac"),
    ("SQL", "DISTINCT", "Was macht SELECT DISTINCT?", [(R, "Es entfernt doppelte Ergebniszeilen"), (W, "Es sortiert das Ergebnis"), (W, "Es zählt alle Zeilen"), (W, "Es löscht Duplikate in der Tabelle")], "b"),
    ("SQL", "Primärschlüssel Eindeutigkeit", "Welche Eigenschaft hat ein Primärschlüssel?", [(R, "Er identifiziert jede Zeile eindeutig"), (W, "Er darf mehrfach vorkommen"), (W, "Er darf NULL enthalten"), (W, "Er ist immer ein Text")], "abc"),
    ("SQL", "Fremdschlüssel Zweck", "Wozu dient ein Fremdschlüssel?", [(R, "Er verweist auf den Primärschlüssel einer anderen Tabelle"), (W, "Er verschlüsselt Daten"), (W, "Er beschleunigt jede Abfrage"), (W, "Er sortiert die Tabelle")], "ab"),
    ("SQL", "UPDATE ohne WHERE", "Was geschieht bei UPDATE ohne WHERE-Klausel?", [(R, "Alle Zeilen der Tabelle werden geändert"), (W, "Es wird nichts geändert"), (W, "Nur die erste Zeile wird geändert"), (W, "Die Tabelle wird gelöscht")], "c"),
    ("SQL", "DELETE und DROP", "Worin unterscheidet sich DELETE von DROP TABLE?", [(R, "DELETE entfernt Zeilen, DROP TABLE die ganze Tabelle"), (W, "Beide entfernen nur Zeilen"), (W, "DROP TABLE entfernt nur Zeilen"), (W, "Es gibt keinen Unterschied")], "bc"),
    ("SQL", "Aggregatfunktionen", "Welche Funktionen sind Aggregatfunktionen?", [(50, "SUM"), (50, "AVG"), (-100, "ORDER"), (-100, "FROM")], "c"),
    ("SQL", "Index Wirkung", "Welchen Zweck hat ein Index auf einer Spalte?", [(R, "Er beschleunigt Suchen in dieser Spalte"), (W, "Er verhindert alle Änderungen"), (W, "Er ersetzt den Primärschlüssel"), (W, "Er verkleinert die Tabelle immer")], "ab"),
    ("SQL", "Unterabfrage", "Was ist eine Unterabfrage?", [(R, "Eine SELECT-Abfrage innerhalb einer anderen Abfrage"), (W, "Eine gelöschte Abfrage"), (W, "Eine Abfrage ohne Tabelle"), (W, "Ein Index auf zwei Spalten")], "bc"),
    # ---- Normalisierung (10) ----
    ("Normalisierung", "Ziel der Normalisierung", "Was ist das Hauptziel der Normalisierung?", [(R, "Redundanz und Anomalien vermeiden"), (W, "Mehr Speicher verbrauchen"), (W, "Abfragen immer verlangsamen"), (W, "Fremdschlüssel entfernen")], "abc"),
    ("Normalisierung", "Erste Normalform", "Was verlangt die erste Normalform?", [(R, "Nur atomare Attributwerte"), (W, "Keine Fremdschlüssel"), (W, "Mindestens drei Tabellen"), (W, "Keine Primärschlüssel")], "ab"),
    ("Normalisierung", "Zweite Normalform", "Was verlangt die zweite Normalform zusätzlich zur ersten?", [(R, "Keine Abhängigkeit von nur einem Teil des Schlüssels"), (W, "Keine atomaren Werte"), (W, "Keine Tabellen mit Schlüssel"), (W, "Nur eine Spalte pro Tabelle")], "bc"),
    ("Normalisierung", "Dritte Normalform", "Welche Abhängigkeiten schließt die dritte Normalform aus?", [(R, "Transitive Abhängigkeiten von Nichtschlüsselattributen"), (W, "Alle Abhängigkeiten"), (W, "Abhängigkeiten vom Primärschlüssel"), (W, "Fremdschlüsselbeziehungen")], "abc"),
    ("Normalisierung", "Update Anomalie", "Was ist eine Änderungsanomalie?", [(R, "Eine Änderung muss an mehreren Stellen erfolgen, sonst entstehen Widersprüche"), (W, "Ein Fehler beim Anmelden"), (W, "Ein gelöschter Index"), (W, "Eine zu große Tabelle")], "a"),
    ("Normalisierung", "Funktionale Abhängigkeit", "Wann gilt A → B als funktionale Abhängigkeit?", [(R, "Wenn jeder Wert von A genau einen Wert von B bestimmt"), (W, "Wenn B immer größer als A ist"), (W, "Wenn A und B gleich heißen"), (W, "Wenn B ein Fremdschlüssel ist")], "bc"),
    ("Normalisierung", "Denormalisierung", "Warum denormalisiert man manchmal bewusst?", [(R, "Um Lesezugriffe zu beschleunigen"), (W, "Um Redundanz zu erzwingen ohne Grund"), (W, "Um Schlüssel zu entfernen"), (W, "Um SQL zu vermeiden")], "c"),
    ("Normalisierung", "Boyce-Codd", "Wann ist eine Relation in Boyce-Codd-Normalform?", [(R, "Wenn jede Determinante ein Superschlüssel ist"), (W, "Wenn sie keine Spalten hat"), (W, "Wenn sie nur einen Datensatz enthält"), (W, "Wenn sie keine Fremdschlüssel hat")], "bc"),
    ("Normalisierung", "Mehrwertige Attribute", "Wie behandelt man ein mehrwertiges Attribut für die erste Normalform?", [(R, "Man lagert es in eine eigene Tabelle aus"), (W, "Man speichert Werte kommagetrennt"), (W, "Man löscht das Attribut"), (W, "Man macht es zum Primärschlüssel")], "a"),
    ("Normalisierung", "Redundanz Beispiel", "Welches Beispiel zeigt unerwünschte Redundanz?", [(R, "Der Name eines Kunden steht in jeder seiner Bestellzeilen"), (W, "Jede Bestellung hat eine eigene Nummer"), (W, "Kunden haben einen Primärschlüssel"), (W, "Eine Tabelle hat einen Index")], "bc"),
    # ---- ER-Modellierung (8) ----
    ("ER-Modellierung", "Entität Begriff", "Was beschreibt eine Entität im ER-Modell?", [(R, "Ein unterscheidbares Objekt der realen Welt"), (W, "Eine SQL-Abfrage"), (W, "Einen Index"), (W, "Eine Zeile im Log")], "abc"),
    ("ER-Modellierung", "Kardinalität", "Was gibt die Kardinalität einer Beziehung an?", [(R, "Wie viele Instanzen einer Entität zu einer anderen gehören können"), (W, "Wie schnell eine Abfrage ist"), (W, "Wie groß die Datei ist"), (W, "Wie viele Nutzer es gibt")], "ab"),
    ("ER-Modellierung", "n zu m Beziehung", "Wie setzt man eine n:m-Beziehung im relationalen Modell um?", [(R, "Mit einer eigenen Verbindungstabelle"), (W, "Mit einem einzelnen Fremdschlüssel"), (W, "Gar nicht"), (W, "Mit einer Sicht")], "abc"),
    ("ER-Modellierung", "Schwache Entität", "Was kennzeichnet eine schwache Entität?", [(R, "Sie ist nur zusammen mit einer anderen Entität identifizierbar"), (W, "Sie hat keine Attribute"), (W, "Sie wird nie gespeichert"), (W, "Sie hat zwei Primärschlüssel")], "c"),
    ("ER-Modellierung", "Attribute Arten", "Welche Art von Attribut kann aus anderen berechnet werden?", [(R, "Abgeleitetes Attribut"), (W, "Schlüsselattribut"), (W, "Atomares Attribut"), (W, "Fremdes Attribut")], "ab"),
    ("ER-Modellierung", "Generalisierung", "Wofür steht Generalisierung im erweiterten ER-Modell?", [(R, "Gemeinsame Eigenschaften mehrerer Entitätstypen in einem Obertyp"), (W, "Das Löschen von Entitäten"), (W, "Das Verschlüsseln von Daten"), (W, "Das Sortieren von Tabellen")], "bc"),
    ("ER-Modellierung", "ER-Modell erklären", "Erklären Sie in eigenen Worten, wofür ein ER-Modell beim Datenbankentwurf eingesetzt wird.", "essay", "bc"),
    ("ER-Modellierung", "Bestellung Diagramm", "Welche Beziehung zeigt das Diagramm zwischen Kunde und Bestellung?", [(R, "Ein Kunde kann mehrere Bestellungen haben"), (W, "Eine Bestellung hat mehrere Kunden"), (W, "Beide sind identisch"), (W, "Es gibt keine Beziehung")], "c", "bestellung_er.png"),
    # ---- Transaktionen (6) ----
    ("Transaktionen", "ACID Begriff", "Wofür steht das A in ACID?", [(R, "Atomarität"), (W, "Aktualität"), (W, "Auswahl"), (W, "Adressierung")], "abc"),
    ("Transaktionen", "COMMIT", "Was bewirkt COMMIT?", [(R, "Die Änderungen der Transaktion werden dauerhaft übernommen"), (W, "Die Änderungen werden verworfen"), (W, "Die Tabelle wird gesperrt"), (W, "Der Benutzer wird abgemeldet")], "ab"),
    ("Transaktionen", "ROLLBACK", "Was bewirkt ROLLBACK?", [(R, "Die Änderungen der Transaktion werden zurückgenommen"), (W, "Die Änderungen werden gespeichert"), (W, "Die Datenbank wird gelöscht"), (W, "Ein Index wird angelegt")], "bc"),
    ("Transaktionen", "Isolation", "Was bedeutet Isolation bei Transaktionen?", [(R, "Parallele Transaktionen beeinflussen sich nicht gegenseitig"), (W, "Die Datenbank ist offline"), (W, "Nur ein Nutzer darf lesen"), (W, "Daten werden verschlüsselt")], "a"),
    ("Transaktionen", "Deadlock Definition", "Was ist ein Deadlock?", [(R, "Transaktionen warten gegenseitig auf Sperren und blockieren sich"), (W, "Eine Tabelle ist leer"), (W, "Ein Index ist beschädigt"), (W, "Ein Nutzer hat das Passwort vergessen")], "bc"),
    ("Transaktionen", "Dauerhaftigkeit", "Was garantiert die Dauerhaftigkeit (Durability)?", [(R, "Bestätigte Änderungen bleiben auch nach einem Absturz erhalten"), (W, "Daten sind für immer unveränderbar"), (W, "Abfragen sind immer schnell"), (W, "Nur lesender Zugriff ist erlaubt")], "c"),
]

# Deliberate imperfections, each in a different semester, to show the quality view and the review of a contradiction.
EXTRA: list[tuple] = [
    # contradiction: identical wording, different correct answer (file a vs file c)
    ("SQL", "NULL und Null", "Ein NULL-Wert in SQL entspricht dem Zahlenwert 0.", "tf-false", "a"),
    ("SQL", "NULL und Null", "Ein NULL-Wert in SQL entspricht dem Zahlenwert 0.", "tf-true", "c"),
    # similar pair
    ("Transaktionen", "Sperre Begriff", "Was versteht man bei Datenbanken unter einer Sperre (Lock)?", [(R, "Ein Mechanismus, der gleichzeitigen Zugriff auf Daten regelt"), (W, "Ein defekter Index"), (W, "Ein gelöschter Benutzer"), (W, "Eine leere Tabelle")], "b"),
    ("Transaktionen", "Sperre Begriff kurz", "Was versteht man bei Datenbanken unter einer Sperre?", [(R, "Ein Mechanismus, der gleichzeitigen Zugriff auf Daten regelt"), (W, "Ein defekter Index"), (W, "Ein gelöschter Benutzer"), (W, "Eine leere Tabelle")], "c"),
    # broken: no correct answer
    ("SQL", "Sicht Begriff", "Was ist eine Sicht (View) in SQL?", [(W, "Eine gespeicherte Abfrage"), (W, "Eine Sicherung"), (W, "Ein Index")], "b"),
]


def _answers(items: list[tuple[int, str]]) -> str:
    return "".join(
        f'    <answer fraction="{f}" format="html"><text><![CDATA[{t}]]></text>'
        f'<feedback format="html"><text></text></feedback></answer>\n' for f, t in items)


def _question(row: tuple) -> str:
    topic, name, text, answers = row[:4]
    image = row[5] if len(row) > 5 else None
    body = f"<p>{escape(text)}</p>" + (f'<p><img src="@@PLUGINFILE@@/{image}" alt="Diagramm"/></p>' if image else "")
    head = (f'  <question type="{{type}}">\n    <name><text>{escape(name)}</text></name>\n'
            f'    <questiontext format="html"><text><![CDATA[{body}]]></text></questiontext>\n'
            '    <generalfeedback format="html"><text></text></generalfeedback>\n'
            '    <defaultgrade>1.0000000</defaultgrade>\n    <penalty>0.3333333</penalty>\n    <hidden>0</hidden>\n')
    if answers == "essay":
        return (head.format(type="essay") + '    <responseformat>editor</responseformat>\n    <responserequired>1</responserequired>\n'
                '    <responsefieldlines>10</responsefieldlines>\n  </question>\n')
    if answers in ("tf-true", "tf-false"):
        right, wrong = ("true", "false") if answers == "tf-true" else ("false", "true")
        return (head.format(type="truefalse")
                + f'    <answer fraction="100" format="moodle_auto_format"><text>{right}</text><feedback format="html"><text></text></feedback></answer>\n'
                + f'    <answer fraction="0" format="moodle_auto_format"><text>{wrong}</text><feedback format="html"><text></text></feedback></answer>\n  </question>\n')
    multi = sum(1 for f, _ in answers if f > 0) > 1
    return (head.format(type="multichoice") + f'    <single>{"false" if multi else "true"}</single>\n    <shuffleanswers>true</shuffleanswers>\n'
            '    <answernumbering>abc</answernumbering>\n' + _answers(answers) + "  </question>\n")


def build_files() -> dict[str, bytes]:
    """filename -> Moodle XML bytes, deterministic."""
    out = {}
    for key, filename in FILES.items():
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>\n<!--\n  DEMO-DATEN: vollständig erfundene Fragen zur Demonstration.\n'
            "  Keine echten Hochschuldaten, keine echten Prüfungsfragen.\n-->\n<quiz>\n"
        ]
        rows = [r for r in Q + EXTRA if key in r[4]]
        for topic in TOPICS:
            chosen = [r for r in rows if r[0] == topic]
            if not chosen:
                continue
            parts.append(f'  <question type="category">\n    <category><text>$course$/top/{escape(FACH)}/{escape(topic)}</text></category>\n'
                         '    <info format="moodle_auto_format"><text></text></info>\n  </question>\n\n')
            parts += [_question(r) + "\n" for r in chosen]
        parts.append("</quiz>\n")
        out[filename] = "".join(parts).encode("utf-8")
    return out
