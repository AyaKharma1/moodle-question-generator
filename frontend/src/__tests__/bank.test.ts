import { describe, expect, it } from "vitest";
import {
  checkRandomDraw, excerpt, formatVariants, highlight, matchFields, plainText, searchTerms, selection,
  setSelected, shortText, toggleSelected, typeLabel,
} from "../bank";

describe("checkRandomDraw", () => {
  it("flags categories that cannot fill a test", () => {
    expect(checkRandomDraw(3, 4).level).toBe("impossible");
  });

  it("rates category size by how many questions two students share", () => {
    expect(checkRandomDraw(5, 4)).toEqual({ level: "small", sharedOnAverage: 3.2 });
    expect(checkRandomDraw(12, 4).level).toBe("tight");
    expect(checkRandomDraw(40, 4)).toEqual({ level: "good", sharedOnAverage: 0.4 });
  });
});

describe("plainText", () => {
  it("drops markup and decodes entities without executing anything", () => {
    expect(plainText("<p>Was ist <strong>RAM</strong>?</p>")).toBe("Was ist RAM?");
    expect(plainText("a &amp; b<script>alert(1)</script>")).toBe("a & balert(1)");
    expect(plainText("<p>Warnungen</p><p>Wenn Sie</p><ul><li>eins</li><li>zwei</li></ul>")).toBe("Warnungen Wenn Sie eins zwei");
  });
});

describe("selection", () => {
  it("toggles and bulk-sets ids", () => {
    setSelected([1, 2, 3], true);
    toggleSelected(2);
    expect([...selection.ids]).toEqual([1, 3]);
    setSelected([1, 3], false);
    expect(selection.ids.size).toBe(0);
  });
});

describe("typeLabel", () => {
  it("translates known Moodle types and keeps unknown ones", () => {
    expect(typeLabel("essay")).toBe("Freitext");
    expect(typeLabel("cloze")).toBe("Lückentext (Cloze)");
    expect(typeLabel("calculated")).toBe("calculated");
  });
});

describe("shortText", () => {
  it("shortens only long texts", () => {
    expect(shortText("kurz")).toBe("kurz");
    expect(shortText("a".repeat(400)).length).toBe(281);
  });
});

describe("search helpers", () => {
  it("splits the query into words", () => {
    expect(searchTerms("  RAM   Speicher ")).toEqual(["RAM", "Speicher"]);
    expect(searchTerms(undefined)).toEqual([]);
    expect(searchTerms("a b c d e f g h i j")).toHaveLength(8);
  });

  it("marks every hit, ignoring case and umlaut case, and never treats input as markup", () => {
    expect(highlight("Übersetzen mit make", ["übersetzen"])).toEqual([
      { text: "Übersetzen", hit: true }, { text: " mit make", hit: false },
    ]);
    expect(highlight("a.b und a-b", ["a.b"])).toEqual([
      { text: "a.b", hit: true }, { text: " und a-b", hit: false },
    ]);
    expect(highlight("<b>x</b>", ["x"]).map((s) => s.text).join("")).toBe("<b>x</b>");
    expect(highlight("kein Treffer", [])).toEqual([{ text: "kein Treffer", hit: false }]);
  });

  it("shows the part of a long text around the hit", () => {
    const text = "Anfang ".repeat(60) + "SCHLUSSELWORT und Rest " + "Ende ".repeat(40);
    const out = excerpt(text, ["schlusselwort"], 200);
    expect(out).toContain("SCHLUSSELWORT");
    expect(out.startsWith("…")).toBe(true);
    expect(excerpt("kurz", ["x"])).toBe("kurz");
    expect(excerpt(text, [], 100).endsWith("…")).toBe(true);
  });

  it("says where a question matched", () => {
    const q = { name: "Deadlock", question_text: "<p>Was ist eine Voraussetzung?</p>", explanation: "",
      answers: [{ text: "Zyklisches Warten" }], fach: "Computersysteme", category: "Betriebssysteme",
      origins: [{ filename: "ss2025.xml" }] };
    expect(matchFields(q, ["zyklisches"])).toEqual(["Antwort"]);
    expect(matchFields(q, ["betriebssysteme", "ss2025"])).toEqual(["Kategorie", "Dateiname"]);
    expect(matchFields(q, [])).toEqual([]);
  });

  it("writes huge variant counts readably", () => {
    expect(formatVariants(2.69)).toBe("ca. 490");
    expect(formatVariants(7)).toBe("mehr als 1 Million");
    expect(formatVariants(15)).toBe("mehr als 1 Billion");
  });
});
