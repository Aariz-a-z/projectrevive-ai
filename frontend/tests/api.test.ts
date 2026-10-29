/**
 * The API client's request shape.
 *
 * These exist because of a bug that would have shipped. The session cookie is
 * SameSite=Lax, which browsers do not send cross-site. Calling the backend
 * directly works in development — localhost:3000 and localhost:8000 differ
 * only by port, so they are the same site — and fails in production, where
 * the two sit on different registrable domains. Sign-in would have appeared
 * to succeed while every later request came back anonymous.
 *
 * The fix is that requests stay on this origin and are proxied. Nothing about
 * that is visible locally, so the only thing that can stop it regressing is a
 * test asserting the request shape directly.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, getAnalysis, getMe, login, uploadReport } from "@/lib/api";

function mockFetch(response: Partial<Response> & { json?: () => unknown }) {
  const spy = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({}),
    ...response,
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

describe("request shape", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends requests to this origin, never an absolute backend URL", async () => {
    const fetchSpy = mockFetch({ json: async () => ({ id: "x" }) });
    await getMe();

    const [url] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/auth/me");
    expect(url).not.toMatch(/^https?:\/\//);
  });

  it("always includes credentials", async () => {
    const fetchSpy = mockFetch({ json: async () => ({}) });
    await getMe();

    expect(fetchSpy.mock.calls[0][1]).toMatchObject({
      credentials: "include",
    });
  });

  it("includes credentials on uploads too", async () => {
    const fetchSpy = mockFetch({ status: 201, json: async () => ({ id: "a" }) });
    await uploadReport(new File(["x"], "r.pdf", { type: "application/pdf" }));

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/analyses");
    expect(init.credentials).toBe("include");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("encodes ids so a hostile id cannot alter the path", async () => {
    const fetchSpy = mockFetch({ json: async () => ({}) });
    await getAnalysis("../auth/me");

    expect(fetchSpy.mock.calls[0][0]).toBe("/api/analyses/..%2Fauth%2Fme");
  });

  it("posts JSON with the right content type", async () => {
    const fetchSpy = mockFetch({ json: async () => ({}) });
    await login("a@b.com", "secret-passphrase");

    const [, init] = fetchSpy.mock.calls[0];
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body)).toEqual({
      email: "a@b.com",
      password: "secret-passphrase",
    });
  });
});

describe("error handling", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("surfaces the backend's own message rather than a generic one", async () => {
    mockFetch({
      ok: false,
      status: 422,
      json: async () => ({
        code: "scanned_document",
        message: "That PDF appears to be scanned images.",
      }),
    });

    await expect(getMe()).rejects.toMatchObject({
      code: "scanned_document",
      message: "That PDF appears to be scanned images.",
      status: 422,
    });
  });

  it("flags 401 so callers can redirect to sign-in", async () => {
    mockFetch({ ok: false, status: 401, json: async () => ({ code: "x" }) });

    await expect(getMe()).rejects.toSatisfy(
      (e: ApiError) => e.isAuthError === true,
    );
  });

  it("does not treat other failures as auth failures", async () => {
    mockFetch({ ok: false, status: 500, json: async () => ({}) });
    await expect(getMe()).rejects.toSatisfy(
      (e: ApiError) => e.isAuthError === false,
    );
  });

  it("unpacks FastAPI validation errors, which use a different shape", async () => {
    mockFetch({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [{ msg: "Value error, that is not an email" }],
      }),
    });

    await expect(getMe()).rejects.toMatchObject({
      code: "validation_error",
      message: "that is not an email",
    });
  });

  it("survives an error body that is not JSON", async () => {
    mockFetch({
      ok: false,
      status: 502,
      json: async () => {
        throw new SyntaxError("not json");
      },
    });

    await expect(getMe()).rejects.toMatchObject({ status: 502 });
  });

  it("reports an unreachable API as a network error, not a crash", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    await expect(getMe()).rejects.toMatchObject({ code: "network_error" });
  });

  it("returns nothing for a 204 instead of trying to parse a body", async () => {
    mockFetch({
      status: 204,
      json: async () => {
        throw new Error("204 has no body to parse");
      },
    });

    const { deleteAnalysis } = await import("@/lib/api");
    await expect(deleteAnalysis("abc")).resolves.toBeUndefined();
  });
});
