/**
 * Shared HTTP helper for the real backend integration
 * (`@integration.eng`'s `*integrate-api`, project-context/2.build/
 * integration.md). Introduced this run — not part of `@frontend.eng`'s
 * original scaffold — because all three swap targets (`mockInquiryClient
 * .ts`, `mockEmailClient.ts`, `mockOpsData.ts`) need the same base-URL
 * resolution and the same `{error_code, message}` error-envelope parsing
 * (sad.md §4 API Architecture), so factoring it once avoids drift between
 * the three call sites. This file is new; no existing component imports
 * it directly (only the three lib/mock*.ts modules do), so it does not
 * change any component's contract.
 */

const DEFAULT_BASE_URL = "http://localhost:8000";

function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (!configured) {
    // Fails open to the documented default (frontend/.env.example) rather
    // than throwing, so a missing .env.local doesn't hard-crash the app —
    // matches this project's "never silently drop or fabricate, but don't
    // crash the UI either" posture (AC-003).
    console.warn(
      "VITE_API_BASE_URL is not set — falling back to " +
        `${DEFAULT_BASE_URL}. Copy frontend/.env.example to .env.local.`,
    );
    return DEFAULT_BASE_URL;
  }
  return configured.replace(/\/+$/, "");
}

/** Mirrors the backend's `{error_code, message}` envelope (sad.md §4, main.py). */
export interface ApiErrorBody {
  error_code?: string;
  message?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly errorCode?: string;

  constructor(status: number, body: ApiErrorBody | undefined, fallbackMessage: string) {
    super(body?.message || fallbackMessage);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = body?.error_code;
  }
}

/**
 * Thin `fetch` wrapper: resolves `VITE_API_BASE_URL`, sends/parses JSON,
 * and throws `ApiError` for both HTTP error responses (4xx/5xx, parsing
 * the `{error_code, message}` envelope when present) and network failures
 * (fetch rejecting outright — offline, connection refused, CORS
 * misconfiguration, etc.), so every caller has exactly one error type to
 * handle.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${getApiBaseUrl()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch (networkError) {
    throw new ApiError(
      0,
      undefined,
      `Could not reach the backend at ${url}. Is it running? (${
        networkError instanceof Error ? networkError.message : String(networkError)
      })`,
    );
  }

  if (!response.ok) {
    let body: ApiErrorBody | undefined;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = undefined;
    }
    throw new ApiError(response.status, body, `Request to ${path} failed with status ${response.status}`);
  }

  // 2xx with no body (none of this backend's routes do this today, but
  // guards against a future no-content response breaking `.json()`).
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
