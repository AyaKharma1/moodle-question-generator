import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, describeDetail, onUnauthorized, setToken } from "../api";

afterEach(() => {
  setToken(null);
  onUnauthorized(null);
  vi.restoreAllMocks();
});

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("describeDetail", () => {
  it("passes plain German messages through", () => {
    expect(describeDetail("Frage nicht gefunden", "x")).toBe("Frage nicht gefunden");
  });

  it("turns pydantic errors into sentences instead of [object Object]", () => {
    const detail = [
      { type: "string_too_short", loc: ["body", "password"], msg: "…", ctx: { min_length: 8 } },
      { type: "less_than_equal", loc: ["body", "students"], msg: "…", ctx: { le: 2000 } },
      { type: "missing", loc: ["body", "slots"], msg: "…" },
    ];
    const text = describeDetail(detail, "x");
    expect(text).toContain("Das Passwort ist zu kurz (mindestens 8 Zeichen).");
    expect(text).toContain("Die Anzahl der Studierenden ist zu groß (höchstens 2000).");
    expect(text).toContain("Die Kategorien fehlt.");
    expect(text).not.toContain("[object");
  });

  it("falls back for unknown shapes", () => {
    expect(describeDetail(undefined, "Fehler 500")).toBe("Fehler 500");
    expect(describeDetail([{ type: "seltsam", loc: ["body", "foo"] }], "x")).toBe("Das Feld „foo“ ist ungültig.");
  });
});

describe("expired session", () => {
  it("signs the user out when a logged-in request gets 401", async () => {
    setToken("abgelaufen");
    const handler = vi.fn();
    onUnauthorized(handler);
    vi.stubGlobal("fetch", vi.fn(async () => json(401, { detail: "Ihre Sitzung ist ungültig oder abgelaufen." })));
    await expect(api.listDocuments()).rejects.toMatchObject({ status: 401 });
    expect(handler).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem("mqg_token")).toBeNull();
  });

  it("does not treat a wrong password as an expired session", async () => {
    const handler = vi.fn();
    onUnauthorized(handler);
    setToken("noch-gueltig");
    vi.stubGlobal("fetch", vi.fn(async () => json(401, { detail: "E-Mail-Adresse oder Passwort ist falsch." })));
    await expect(api.login("a@b.de", "falsch")).rejects.toThrowError("E-Mail-Adresse oder Passwort ist falsch.");
    expect(handler).not.toHaveBeenCalled();
  });

  it("does not fire without a token (visitor on the login page)", async () => {
    const handler = vi.fn();
    onUnauthorized(handler);
    vi.stubGlobal("fetch", vi.fn(async () => json(401, { detail: "x" })));
    await expect(api.listDocuments()).rejects.toBeInstanceOf(ApiError);
    expect(handler).not.toHaveBeenCalled();
  });
});

describe("no connection", () => {
  it("explains what to do when the server cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    await expect(api.listDocuments()).rejects.toMatchObject({ status: 0, message: expect.stringContaining("Keine Verbindung") });
  });
});
