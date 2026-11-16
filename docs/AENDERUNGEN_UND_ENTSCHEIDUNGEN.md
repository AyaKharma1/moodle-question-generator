# Änderungen, Entscheidungen und offene Punkte

Stand: Überarbeitung der Fragenbank mit Qualitätsansicht, Entscheidungen, Export-Vorschau, Testplanung und Demo-Modus.
Alles hier Beschriebene ist im Code umgesetzt und durch automatische Tests (130 Backend-, 21 Frontend-Tests) und einen
Durchlauf im Browser (Demo-Daten, Chromium) geprüft. **Nicht geprüft** ist der Re-Import der erzeugten XML-Dateien in einer
echten Moodle-Instanz (siehe „Offene Punkte“).

## 1. Bestandsaufnahme (vor den Änderungen)

| Bereich | Einschätzung |
|---|---|
| Gut | Mehrere Moodle-XML-Dateien importieren; Duplikate werden erkannt und nur einmal gespeichert; Herkunft (Datei, Fach, Kategorie) bleibt; Volltextsuche; Export unverändert aus dem Original-XML; Testplaner mit Simulation. |
| Prototyp-haft | Fehlermeldungen teils englisch; fehlender/abgelaufener Login zeigte rohe Meldung; keine Größenbegrenzung der gesamten Anfrage; Standard-Geheimschlüssel in Produktion möglich. |
| Für Dozenten nützlich | Suche über alle Dateien, Widerspruchserkennung, Pool-Bereinigung, Fairness-Simulation. |
| Komplizierte Abläufe | Widersprüche konnten nur angesehen, nicht entschieden werden; Export ohne Vorschau; keine Spur, wofür ein Export gedacht war. |
| Technische Risiken | Upload-Größen, Produktions-Konfiguration, XML-Angriffe (XXE; bereits durch sicheren Parser abgedeckt), Mehrbenutzer-Trennung (per Test abgedeckt). |

## 2. Umgesetzt

### P0 – Robustheit
* Upload gestreamt mit Grenzen (Datei, Gesamtmenge je Import, ganze Anfrage → 413 mit deutscher Meldung).
* Produktion startet nicht mit Standard-/kurzem `SECRET_KEY`.
* Alle API-Meldungen deutsch; abgelaufene Sitzung leitet zur Anmeldung mit Hinweis; verständliche Validierungsfehler.
* Barrierefreiheit: Sprunglink, Fokus-Rahmen, Tastatur-Dropzone, `role=alert/status`, Seitentitel.
* Import-Bericht je Datei: Fragetypen, Kategorien, Bilder, Warnungen (fehlende Bilder, nicht prüfbare Typen, Kategorielose Fragen). Dateien ohne Fragen werden mit Handlungshinweis abgelehnt.

### P1 – Neue Funktionen
**A) Fragenhistorie** (`/frage/:id`): Quelldateien mit Importdatum, Varianten nebeneinander (abweichende Antworten markiert), ähnliche Fragen, Exporte mit Verwendungszweck, Hinweise mit Begründung.
**B) Qualitätsansicht** (`/pruefung`): Kritisch / Überprüfen / Information, jeweils mit „Warum?“ und „Was tun?“. Entscheidungen „Geprüft“ / „Ausschließen“ / zurücknehmen, bei Widersprüchen „Diese Variante bleibt“ / „Alle bleiben“. **Die Anwendung entscheidet nie selbst, welche Antwort richtig ist.** Ausgeschlossene Fragen werden nicht gelöscht, aber nicht ausgewählt, exportiert oder im Test geplant.
**C/D) Testplanung:** Anzahl oder Prozent je Kategorie (größter-Rest-Rundung), Abdeckung je Kategorie (wie viele Fragen fehlen bis zur Empfehlung 4 × Fragen pro Person), Startwert für Reproduzierbarkeit, Überschneidungs-Histogramm, Aussagen getrennt nach *berechnet / simuliert / nicht garantierbar*.
**E) Export-Vorschau:** Anzahl, endgültige Moodle-Kategorien, ausgeschlossene Fragen mit Grund, offene Hinweise nach Schweregrad, Checkliste, Verwendungszweck; Verlauf speichert Notiz und Zusammenfassung zum Exportzeitpunkt. Originale werden nie verändert (Export aus dem gespeicherten Original-XML).
**Demo-Modus:** erfundener Datenbestand „Datenbanksysteme (DEMO)“, deutlich gekennzeichnet, mit einem Klick ladbar und entfernbar (siehe `DEMO_ABLAUF.md`).

### Eigene Ideen – Bewertung
Kriterien: Nutzen / Aufwand / Risiko / Verständlichkeit / Realismus für eine Studentin / Wirkung in der Präsentation (1 = schlecht, 3 = gut).

| Idee | Nutzen | Aufwand | Risiko | Verständl. | Realismus | Präsentation | Entscheidung |
|---|---|---|---|---|---|---|---|
| Import-Bericht | 3 | 3 | 3 | 3 | 3 | 3 | **umgesetzt** |
| Entscheidungen (geprüft/ausgeschlossen) statt Löschen | 3 | 2 | 3 | 3 | 3 | 3 | **umgesetzt** |
| Verwendungszweck + Zusammenfassung im Export-Verlauf | 3 | 3 | 3 | 3 | 3 | 2 | **umgesetzt** |
| Hinweis „Richtige Antwort auffällig lang“ | 2 | 3 | 2 | 3 | 3 | 2 | umgesetzt, bewusst nur *Information* und mit strengen Schwellen (≥ 60 Zeichen und ≥ 3 × Median der falschen) |
| Demo-Modus | 3 | 2 | 3 | 3 | 3 | 3 | **umgesetzt** |
| „In neuerer Datei nicht mehr vorhanden“ (veraltet?) | 2 | 2 | 1 | 1 | 2 | 2 | **nicht umgesetzt**: Fehlen in einer Datei sagt nichts darüber, ob eine Frage veraltet ist; unzuverlässig |
| Vergleich zweier Exporte | 2 | 1 | 2 | 2 | 2 | 2 | P2, später |
| Datenlöschung (DSGVO) pro Benutzer | 2 | 2 | 3 | 3 | 2 | 1 | später, falls ein Mehrbenutzerbetrieb geplant ist |

## 3. Wichtigste Entwurfsentscheidungen (Problem – Warum so – Alternativen – Grenzen)

**Entscheidungen statt Löschen.** Problem: Bei Widersprüchen weiß nur die Lehrperson, was stimmt. Warum: Ein automatisches Löschen wäre eine fachliche Behauptung. Alternative: „neueste Datei gewinnt“ – verworfen, weil unzuverlässig. Grenze: Die Entscheidung gilt für die Fragenbank dieser App; Moodle selbst bleibt unverändert.

**Hinweise mit Schweregrad aus einem Katalog.** Jeder Hinweis hat Titel, Begründung und Handlungsempfehlung an *einer* Stelle (`question_bank/findings.py`), damit Wortlaut und Einstufung konsistent sind. Prüfungen warnen nur, wenn sie sich sicher sind (z. B. Einfachauswahl mit Teilpunkten 100/50/0 wird *nicht* markiert; 33,33333 × 3 wird nicht als „≠ 100 %“ gewertet). Grenze: Ähnlichkeit ist Wortüberlappung (Jaccard ≥ 0,8), nicht Bedeutung; Fragetypen außer Single/Multiple Choice, Wahr/Falsch, Kurzantwort werden nur mitgeführt und als „nicht geprüft“ gemeldet.

**Fairness-Mathematik.** Annahme: Moodle zieht je Person und Kategorie zufällig ohne Zurücklegen. Dann teilen zwei Personen im Erwartungswert Σ k²/n Fragen (n Poolgröße, k Fragen pro Person); P(zwei bestimmte Personen haben das identische Set) = 1/∏C(n,k). Überschneidungsfreie Sets für N Personen sind nur möglich, wenn jede Kategorie ≥ N·k Fragen hat. Die Simulation (feste Seeds) bestätigt k²/n (Test mit 300 Personen, Toleranz 0,1). **Wichtig:** Eine feste „ausgewogene“ Verteilung senkt die *durchschnittliche* Überschneidung nicht, sie gleicht nur die Nutzung der Fragen aus und vermeidet identische Sets. Die App verspricht deshalb nirgends „für alle völlig andere Fragen“, sondern sagt, wenn das rechnerisch unmöglich ist. Grenze: Annahme gleichverteilter, unabhängiger Ziehung; Moodle-Zufall wurde nicht gegen echte Versuche gemessen.

**Prozentverteilung.** Die „Themenabdeckung“ verwendet ausschließlich die vorhandenen Moodle-Kategorien. Es werden keine Themen erfunden. Ist ein Pool zu klein, wird das angezeigt (Abdeckung in %, fehlende Fragen).

**Export-Vorschau.** Sie beschreibt die Datei, garantiert aber keinen fehlerfreien Moodle-Import (steht so im Dialog). Moodle erkennt Duplikate beim Import nicht → Checkliste empfiehlt Testkurs.

## 4. Offene Punkte / bekannte Grenzen
1. **Re-Import in echtes Moodle nicht verifiziert.** Round-Trip (Import → Export → gleiche Fragen) ist durch Tests belegt, der Import der erzeugten Datei in Moodle selbst wurde in dieser Umgebung nicht ausgeführt (kein Moodle erreichbar).
2. Annahme: Beschreibungs-Elemente (`description`) werden von Moodle nicht zufällig gezogen; sie werden im Pool ausgeschlossen. Nicht in Moodle geprüft.
3. Ähnlichkeit nur lexikalisch; semantische Ähnlichkeit (Embeddings) ist P2.
4. Mehr als ~5000 ähnliche Paare werden als „5.000+“ angezeigt (Obergrenze).
5. Keine direkte Moodle-Anbindung (Web-Service-API) – P2, siehe `FUTURE_MOODLE_INTEGRATION.md`.
6. Die Hinweise zu Jahreszahlen und Antwortlängen sind Heuristiken (nur „Information“).
7. Frontend: die Fragenseite (`/frage/:id`) wurde automatisiert nur über Typprüfung/Build und im Backend per Test abgedeckt, nicht per Screenshot-Durchlauf.

## 5. P2 (nur dokumentiert)
* Semantische Ähnlichkeit (Embeddings) mit Lehrenden-Freigabe, weil Fragetexte an externe Dienste gehen würden.
* Direkte Moodle-API (Fragen lesen/schreiben): würde Export/Import-Dateien ersetzen, braucht Zugangsdaten und Moodle-Admin-Freigabe.
* Diff zwischen zwei Exporten; Benutzer-Datenlöschung; Mehrsprachigkeit.
