import { ApiError, apiRequest } from "./api";
import { __resetMemoryForTests } from "./visitor";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function apiError(status: number, code: string, retryable = false, extra = {}): Response {
  return jsonResponse(status, { error: { code, message: "raw", retryable, ...extra } });
}

const fetchMock = vi.fn();

beforeEach(() => {
  localStorage.clear();
  __resetMemoryForTests();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

function headerOf(call: unknown[]): string {
  const init = call[1] as RequestInit;
  return new Headers(init.headers).get("X-Visitor-Id")!;
}

describe("apiRequest", () => {
  it("sends X-Visitor-Id and returns the JSON body", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, [{ case_id: "a" }]));
    const data = await apiRequest<{ case_id: string }[]>("GET", "/cases");
    expect(data).toEqual([{ case_id: "a" }]);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/cases");
    expect(headerOf(fetchMock.mock.calls[0])).toBe(localStorage.getItem("mia:visitor_id"));
  });

  it("sends a JSON body on POST", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(201, { session_id: "s" }));
    await apiRequest("POST", "/sessions", { case_id: "c", mode: "text" });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(JSON.stringify({ case_id: "c", mode: "text" }));
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
  });

  it("retries once with a new id after invalid_input", async () => {
    fetchMock
      .mockResolvedValueOnce(apiError(422, "invalid_input"))
      .mockResolvedValueOnce(jsonResponse(200, []));
    await expect(apiRequest("GET", "/sessions")).resolves.toEqual([]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(headerOf(fetchMock.mock.calls[0])).not.toBe(headerOf(fetchMock.mock.calls[1]));
  });

  it("retries only once", async () => {
    fetchMock
      .mockResolvedValueOnce(apiError(422, "invalid_input"))
      .mockResolvedValueOnce(apiError(422, "invalid_input"));
    await expect(apiRequest("GET", "/sessions")).rejects.toMatchObject({ code: "invalid_input" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry invalid_input when sending an answer", async () => {
    fetchMock.mockResolvedValueOnce(apiError(422, "invalid_input"));
    await expect(
      apiRequest("POST", "/sessions/s1/turns", { answer_text: "x" }),
    ).rejects.toMatchObject({ code: "invalid_input" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("maps API errors to ApiError", async () => {
    fetchMock.mockResolvedValueOnce(apiError(503, "demo_paused"));
    const err = await apiRequest("POST", "/sessions", {}).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ code: "demo_paused", retryable: false, status: 503 });
  });

  it("reads scope from quota errors when present", async () => {
    fetchMock.mockResolvedValueOnce(apiError(429, "quota_exceeded", false, { scope: "global" }));
    await expect(apiRequest("POST", "/sessions", {})).rejects.toMatchObject({ scope: "global" });
  });

  it("maps unknown codes to internal", async () => {
    fetchMock.mockResolvedValueOnce(apiError(500, "xyz", true));
    await expect(apiRequest("GET", "/cases")).rejects.toMatchObject({ code: "internal" });
  });

  it("maps a non-JSON error to internal", async () => {
    fetchMock.mockResolvedValueOnce(new Response("oops", { status: 502 }));
    await expect(apiRequest("GET", "/cases")).rejects.toMatchObject({
      code: "internal",
      retryable: true,
    });
  });

  it("maps network failures to network", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(apiRequest("GET", "/cases")).rejects.toMatchObject({
      code: "network",
      status: null,
      retryable: true,
    });
  });

  it("resolves undefined on 204", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(apiRequest("DELETE", "/sessions/s1")).resolves.toBeUndefined();
  });
});
