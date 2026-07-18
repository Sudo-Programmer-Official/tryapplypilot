import type { AuthTokens, AuthUser } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const ACCESS_TOKEN_KEY = "tryapplypilot-access-token";
const REFRESH_TOKEN_KEY = "tryapplypilot-refresh-token";

function getAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

function getRefreshToken(): string | null {
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function hasStoredSession(): boolean {
  return Boolean(getAccessToken() && getRefreshToken());
}

export function storeTokens(tokens: AuthTokens): void {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
}

export function clearAuthSession(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

async function parseRequestError(path: string, response: Response): Promise<Error> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (payload.detail?.trim()) {
      return new Error(payload.detail);
    }
  } catch {
    // Fall through to the generic message.
  }
  return new Error(`Request failed for ${path}: ${response.status}`);
}

async function refreshAuthSession(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return false;
  }
  const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    clearAuthSession();
    return false;
  }
  const payload = (await response.json()) as { user: AuthUser; tokens: AuthTokens };
  storeTokens(payload.tokens);
  return true;
}

export async function authorizedRequest(
  path: string,
  options?: RequestInit,
  retryOnUnauthorized = true,
): Promise<Response> {
  const headers = new Headers(options?.headers ?? {});
  const accessToken = getAccessToken();
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  if (options?.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  if (response.status === 401 && retryOnUnauthorized && !path.startsWith("/api/auth/")) {
    const refreshed = await refreshAuthSession();
    if (refreshed) {
      return authorizedRequest(path, options, false);
    }
  }
  return response;
}

export async function requestJson<T>(path: string, options?: RequestInit, retryOnUnauthorized = true): Promise<T> {
  const response = await authorizedRequest(path, options, retryOnUnauthorized);
  if (!response.ok) {
    throw await parseRequestError(path, response);
  }
  return (await response.json()) as T;
}

export async function requestMultipart<T>(path: string, form: FormData): Promise<T> {
  const response = await authorizedRequest(path, { method: "POST", body: form });
  if (!response.ok) {
    throw await parseRequestError(path, response);
  }
  return (await response.json()) as T;
}
