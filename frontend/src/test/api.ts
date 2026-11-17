// Test helper: route-based fetch mock ("GET /cases" → handler).
type Handler = (body: unknown, url: string) => Response | Promise<Response>;

export function json(status: number, body: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function apiErr(status: number, code: string, retryable = false): Response {
  return json(status, { error: { code, message: "raw", retryable } });
}

export function mockApi(routes: Record<string, Handler | Response | unknown>) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const path = url.replace(/^\/api/, "").split("?")[0];
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path, body });
    const key = `${method} ${path}`;
    const route = routes[key] ?? Object.entries(routes).find(([k]) => matches(k, key))?.[1];
    if (route === undefined) return apiErr(500, "internal", true);
    if (typeof route === "function") return (route as Handler)(body, url);
    if (route instanceof Response) return route.clone();
    return json(200, route);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, calls };
}

function matches(pattern: string, key: string): boolean {
  const re = new RegExp("^" + pattern.replace(/:[a-z_]+/g, "[^/]+") + "$");
  return re.test(key);
}
