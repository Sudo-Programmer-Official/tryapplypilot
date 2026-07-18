import { clearAuthSession, requestJson, storeTokens } from "./client";
import type { AuthTokens, AuthUser } from "../types";

export async function login(email: string, password: string): Promise<AuthUser> {
  const payload = await requestJson<{ user: AuthUser; tokens: AuthTokens }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  storeTokens(payload.tokens);
  return payload.user;
}

export async function signup(email: string, password: string, fullName: string): Promise<AuthUser> {
  const payload = await requestJson<{ user: AuthUser; tokens: AuthTokens }>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name: fullName }),
  });
  storeTokens(payload.tokens);
  return payload.user;
}

export function fetchCurrentUser(): Promise<{ user: AuthUser }> {
  return requestJson<{ user: AuthUser }>("/api/auth/me");
}

export function fetchAdminUsers(): Promise<{ items: AuthUser[] }> {
  return requestJson<{ items: AuthUser[] }>("/api/auth/users");
}

export async function logout(): Promise<void> {
  try {
    await requestJson<{ ok: boolean }>(
      "/api/auth/logout",
      {
        method: "POST",
        body: JSON.stringify({
          refresh_token: window.localStorage.getItem("tryapplypilot-refresh-token"),
        }),
      },
      false,
    );
  } catch {
    // Ignore logout failures.
  } finally {
    clearAuthSession();
  }
}
