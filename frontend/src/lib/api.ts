import { getVisitorId, resetVisitorId } from "./visitor";

export type ErrorCode =
  | "not_found"
  | "invalid_input"
  | "invalid_state"
  | "session_limit"
  | "quota_exceeded"
  | "demo_paused"
  | "llm_invalid_output"
  | "provider_unavailable"
  | "internal"
  | "network";

const KNOWN_CODES: ReadonlySet<string> = new Set<ErrorCode>([
  "not_found",
  "invalid_input",
  "invalid_state",
  "session_limit",
  "quota_exceeded",
  "demo_paused",
  "llm_invalid_output",
  "provider_unavailable",
  "internal",
]);

export type QuotaScope = "visitor" | "global";

/** API failure. The raw backend `message` is never kept: screens use `errorMessage`. */
export class ApiError extends Error {
  code: ErrorCode;
  retryable: boolean;
  status: number | null;
  scope?: QuotaScope;

  constructor(code: ErrorCode, retryable: boolean, status: number | null, scope?: QuotaScope) {
    super(code);
    this.name = "ApiError";
    this.code = code;
    this.retryable = retryable;
    this.status = status;
    this.scope = scope;
  }
}

type Method = "GET" | "POST" | "DELETE";

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function send(method: Method, path: string, body: unknown, visitorId: string) {
  const headers: Record<string, string> = { "X-Visitor-Id": visitorId };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  try {
    return await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("network", true, null);
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const data = (await response.json()) as {
      error?: { code?: string; retryable?: boolean; scope?: string };
    };
    const raw = data.error;
    if (!raw?.code || !KNOWN_CODES.has(raw.code)) {
      return new ApiError("internal", true, response.status);
    }
    const scope = raw.scope === "visitor" || raw.scope === "global" ? raw.scope : undefined;
    return new ApiError(raw.code as ErrorCode, Boolean(raw.retryable), response.status, scope);
  } catch {
    return new ApiError("internal", true, response.status);
  }
}

/** `invalid_input` on an answer is about the body (too long), not the visitor header. */
function canRetryWithNewVisitor(path: string): boolean {
  return !path.endsWith("/turns");
}

export async function apiRequest<T>(method: Method, path: string, body?: unknown): Promise<T> {
  let response = await send(method, path, body, getVisitorId());
  if (!response.ok) {
    let error = await toApiError(response);
    if (error.code === "invalid_input" && canRetryWithNewVisitor(path)) {
      response = await send(method, path, body, resetVisitorId());
      if (response.ok) return parseBody<T>(response);
      error = await toApiError(response);
    }
    throw error;
  }
  return parseBody<T>(response);
}

async function parseBody<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
