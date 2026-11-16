# Kurz erklärt: Was das Werkzeug tut und was nicht

**Idee.** Ihre Fragen liegen schon in Moodle. Dieses Werkzeug liest deren Moodle-XML-Exporte (beliebig viele Dateien, verschiedene Fächer), merkt sich, aus welcher Datei, welchem Fach und welcher Kategorie jede Frage stammt, und macht sie sofort durchsuchbar. Es zeigt Auffälligkeiten (doppelt, widersprüchlich, ähnlich, fehlerhaft) und hilft, einen Fragenpool für einen Test so zusammenzustellen, dass Überschneidungen zwischen Studierenden gering bleiben.

**Was es nicht tut.** Es verbindet sich nicht mit Moodle, ändert keine Originaldateien und entscheidet nie, welche Antwort fachlich richtig ist. KI-Generierung ist optional und wird nicht benötigt.

**Wie sicher ist „andere Fragen für alle“?** Das lässt sich nur rechnerisch einschätzen: Zwei Studierende teilen im Schnitt k²/n Fragen (k = Fragen pro Person, n = Poolgröße). Ein größerer Pool hilft; völlig verschiedene Fragen für alle gibt es nur, wenn jede Kategorie mindestens (Studierende × k) Fragen hat. Das Werkzeug zeigt, was berechnet, was simuliert und was nicht garantierbar ist.

**Datenschutz.** Fragen sind pro Benutzerkonto getrennt. Es werden keine Fragetexte an externe Dienste gesendet, außer Sie nutzen ausdrücklich den optionalen KI-Generator.

**Vor dem produktiven Einsatz.** Erzeugte XML-Dateien zuerst in einem Testkurs in Moodle importieren (Moodle erkennt beim Import keine Duplikate).
