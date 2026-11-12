import { describe, expect, it } from "vitest";
import { checkRandomDraw, plainText, selection, setSelected, shortText, toggleSelected, typeLabel } from "../bank";

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
