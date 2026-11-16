"""What an import did, in words a lecturer can act on.

The importer keeps every question's original XML, so nothing is lost. But the
app can only *check* some question types. The report says so openly instead of
letting an unchecked file look like a checked one.
"""
from __future__ import annotations

import re
from collections import Counter

from app.moodle_import.parser import ParsedQuestion, missing_files_in_xml

# Moodle types whose answers the quality checks understand.
CHECKED_TYPES = {"multichoice", "truefalse", "shortanswer"}

TYPE_NAMES = {
    "multichoice": "Multiple Choice", "truefalse": "Wahr/Falsch", "shortanswer": "Kurzantwort",
    "essay": "Freitext", "matching": "Zuordnung", "cloze": "Lückentext (Cloze)", "multianswer": "Lückentext (Cloze)",
    "numerical": "Numerisch", "calculated": "Berechnet", "calculatedmulti": "Berechnet (Multiple Choice)",
    "calculatedsimple": "Berechnet (einfach)", "ddwtos": "Drag & Drop (Text)", "gapselect": "Lückenauswahl",
    "ddmarker": "Drag & Drop (Markierungen)", "ddimageortext": "Drag & Drop (Bild)", "description": "Beschreibung",
    "match": "Zuordnung", "randomsamatch": "Zufällige Zuordnung",
}
_PLUGINFILE = re.compile(r"@@PLUGINFILE@@/")


def type_name(moodle_type: str) -> str:
    return TYPE_NAMES.get(moodle_type, f"Fragetyp „{moodle_type}“")


def build_report(questions: list[ParsedQuestion]) -> dict:
    """Summary of one parsed file: types, categories and anything worth a warning."""
    types = Counter(q.moodle_type for q in questions)
    # readable "Fach / Kategorie" instead of Moodle's raw "$course$/top/..." path
    categories = Counter(" / ".join(q.category_segments) or None for q in questions)
    uncategorized = sum(1 for q in questions if q.category_path is None)
    fingerprints = Counter(q.fingerprint for q in questions)
    repeated = sum(c - 1 for c in fingerprints.values() if c > 1)
    media_refs = sum(1 for q in questions if _PLUGINFILE.search(q.raw_xml))
    media_missing = sum(1 for q in questions if missing_files_in_xml(q.raw_xml))

    warnings: list[dict] = []

    def warn(code: str, severity: str, text: str, count: int) -> None:
        warnings.append({"code": code, "severity": severity, "text": text, "count": count})

    if media_missing:
        warn("missing_media", "critical",
             f"{media_missing} Frage(n) verweisen auf Bilder oder Dateien, die nicht in der Datei stehen. "
             "Moodle zeigt sie nach dem Import nicht an. Beim Export aus Moodle werden Bilder normalerweise "
             "mit in die XML-Datei geschrieben; bitte den Export prüfen.", media_missing)
    if uncategorized:
        warn("uncategorized", "review",
             f"{uncategorized} Frage(n) stehen vor dem ersten Kategorie-Eintrag der Datei und kommen in „Ohne Kategorie“. "
             "Beim Export aus Moodle hilft die Option „Kategorie in die Datei schreiben“.", uncategorized)
    unchecked = {t: n for t, n in types.items() if t not in CHECKED_TYPES and t != "description"}
    for moodle_type, n in sorted(unchecked.items(), key=lambda kv: -kv[1]):
        warn("not_checked", "info",
             f"{n} Frage(n) vom Typ {type_name(moodle_type)} werden unverändert übernommen. "
             "Ihre Antworten werden nicht automatisch auf Fehler geprüft.", n)
    if types.get("description"):
        n = types["description"]
        warn("description", "info",
             f"{n} Beschreibung(en) enthalten nur Text und sind keine Fragen. Der Testplaner verwendet sie nicht.", n)
    if repeated:
        warn("repeated_in_file", "info",
             f"{repeated} Frage(n) kamen in dieser Datei mehrfach vor und wurden nur einmal gezählt.", repeated)

    return {
        "types": [{"type": t, "name": type_name(t), "count": n} for t, n in types.most_common()],
        "categories": [{"name": c or "Ohne Kategorie", "count": n} for c, n in categories.most_common()],
        "media": {"with_files": media_refs, "missing": media_missing},
        "warnings": warnings,
    }
