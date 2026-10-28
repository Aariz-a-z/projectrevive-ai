/**
 * Typed client for the ProjectRevive API.
 *
 * Backend domain errors arrive as {code, message, detail}. Those are surfaced
 * as ApiError so the UI can show the backend's own wording, which is written to
 * be read by users (see backend/app/errors.py).
 */

import type { AnalysisDetail, AnalysisSummary, HealthInfo } from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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
}

const NETWORK_MESSAGE =
  "Could not reach the analysis API. Check that the backend is running and " +
  "that NEXT_PUBLIC_API_BASE_URL points at it.";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/api${path}`, init);
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
    } catch {
      /* non-JSON error body; keep the generic message */
    }
    throw new ApiError(response.status, code, message, detail);
  }

  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthInfo> {
  return request<HealthInfo>("/health");
}

export function listAnalyses(): Promise<AnalysisSummary[]> {
  return request<AnalysisSummary[]>("/analyses");
}

export function getAnalysis(id: string): Promise<AnalysisDetail> {
  return request<AnalysisDetail>(`/analyses/${encodeURIComponent(id)}`);
}

export function uploadReport(file: File): Promise<AnalysisDetail> {
  const form = new FormData();
  form.append("file", file);
  return request<AnalysisDetail>("/analyses", { method: "POST", body: form });
}
