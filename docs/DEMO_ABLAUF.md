# Demo-Ablauf (ca. 8 Minuten)

Die Demo-Daten sind **vollständig erfundene** Fragen zu „Datenbanksysteme (DEMO)“. Es sind keine echten Hochschuldaten und keine echten Prüfungsfragen. Das Banner „DEMO-MODUS“ ist immer sichtbar, solange sie geladen sind; „Demo-Daten entfernen“ löscht nur sie (eigene Importe bleiben).

1. **Start:** Anmelden → Übersicht → „Mit Demo-Daten ausprobieren“. Es werden drei Semesterdateien importiert (`samples/demo/*.xml`, deterministisch erzeugt aus `backend/app/demo/data.py`).
2. **Import-Bericht** (Seite „Importieren“ zeigt ihn für echte Dateien): Fragetypen, Kategorien, fehlende Bilder.
3. **Übersicht:** echte Zahlen und „Nächste Schritte“ (1 Widerspruch, kritische Hinweise).
4. **Widerspruch prüfen** (Qualität): „NULL und Null“ steht in WS 2023 als *falsch*, in WS 2024 als *wahr*. Nebeneinander ansehen, abweichende Antworten sind markiert → „Diese Variante bleibt“ (Bestätigung). Die andere wird ausgeschlossen, nicht gelöscht.
5. **Weitere Hinweise:** fehlendes Bild („Bestellung Diagramm“), keine richtige Antwort („Sicht Begriff“), sehr ähnliche Fragen („Sperre Begriff“), Freitext wird nur mitgeführt.
6. **Fragenhistorie:** Frage anklicken → Quelldateien, Importdatum, Varianten, ähnliche Fragen, Exporte.
7. **Pool vorbereiten:** Fragenbank → ca. 6 Fragen auswählen (ausgeschlossene sind nicht wählbar).
8. **Export-Vorschau:** Kategorien, offene Hinweise, Checkliste, Verwendungszweck → Datei herunterladen. Verlauf zeigt Notiz und Zusammenfassung.
9. **Testplaner:** „Prozentuale Verteilung“ 40/25/20/15, 20 Fragen pro Person (→ 8/5/4/3), 60 Studierende. Die Kategorie „Transaktionen“ ist klein: Abdeckung < 100 %, Hinweis. Abschnitt „berechnet / simuliert / nicht garantierbar“ erklären.

Reihenfolge der Daten ist deterministisch. Die konkreten Zahlen (z. B. Anzahl der Hinweise) hängen vom Stand der Prüfregeln ab und werden in der Oberfläche aus den echten Daten berechnet.
