import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, getToken, setToken } from "../api";

afterEach(() => {
  setToken(null);
  vi.restoreAllMocks();
});

describe("token storage", () => {
  it("stores and clears the token", () => {
    expect(getToken()).toBeNull();
    setToken("abc");
    expect(getToken()).toBe("abc");
    setToken(null);
    expect(getToken()).toBeNull();
  });
});

describe("api.login", () => {
  it("stores the access token on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ access_token: "tok123" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    await api.login("prof@example.com", "password123");
    expect(getToken()).toBe("tok123");
  });

  it("throws ApiError with the backend detail on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: "Incorrect email or password" }), {
          status: 401,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    await expect(api.login("x@y.z", "bad")).rejects.toThrowError(ApiError);
  });
});
