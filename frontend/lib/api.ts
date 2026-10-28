/**
 * Typed client for the ProjectRevive API.
 *
 * Every request sends `credentials: "include"` because the session lives in an
 * httpOnly cookie that page JavaScript deliberately cannot read. The backend
 * names one exact allowed origin, which is what lets the browser accept
 * credentialed cross-origin requests at all.
 *
 * Backend domain errors arrive as {code, message, detail} and are surfaced as
 * ApiError so the UI can show the backend's own wording, which is written to
 * be read by users (see backend/app/errors.py).
 */

import type {
  AnalysisDetail,
  AnalysisSummary,
  HealthInfo,
  UserPublic,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly code: string;
  readonly detail?: string;
  readonly status: number;

  constructor(status: number, code: string, message: string, detail?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }

  get isAuthError(): boolean {
    return this.status === 401;
  }
}

const NETWORK_MESSAGE =
  "Could not reach the analysis API. Check that the backend is running and " +
  "that NEXT_PUBLIC_API_BASE_URL points at it.";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/api${path}`, {
      ...init,
      credentials: "include",
    });
  } catch {
    throw new ApiError(0, "network_error", NETWORK_MESSAGE);
  }

  if (!response.ok) {
    let code = "http_error";
    let message = `The API responded with ${response.status}.`;
    let detail: string | undefined;
    try {
      const body = await response.json();
      if (typeof body?.message === "string") message = body.message;
      if (typeof body?.code === "string") code = body.code;
      if (typeof body?.detail === "string") detail = body.detail;
      // FastAPI request-validation errors use a different shape.
      if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
        code = "validation_error";
        message = String(body.detail[0].msg).replace(/^Value error, /, "");
      }
    } catch {
      /* non-JSON error body; keep the generic message */
    }
    throw new ApiError(response.status, code, message, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// --- auth -------------------------------------------------------------------

export const signup = (email: string, password: string) =>
  postJson<UserPublic>("/auth/signup", { email, password });

export const login = (email: string, password: string) =>
  postJson<UserPublic>("/auth/login", { email, password });

export const logout = () => request<void>("/auth/logout", { method: "POST" });

export const getMe = () => request<UserPublic>("/auth/me");

// --- analyses ---------------------------------------------------------------

export const getHealth = () => request<HealthInfo>("/health");

export const listAnalyses = () => request<AnalysisSummary[]>("/analyses");

export const getAnalysis = (id: string) =>
  request<AnalysisDetail>(`/analyses/${encodeURIComponent(id)}`);

export const deleteAnalysis = (id: string) =>
  request<void>(`/analyses/${encodeURIComponent(id)}`, { method: "DELETE" });

export function uploadReport(file: File): Promise<AnalysisDetail> {
  const form = new FormData();
  form.append("file", file);
  return request<AnalysisDetail>("/analyses", { method: "POST", body: form });
}
