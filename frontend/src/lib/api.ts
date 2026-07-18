import type {
  AuthTokens,
  AuthUser,
  AlertEvent,
  CompanyPreference,
  DashboardSnapshot,
  JobOpportunity,
  ScoutSettings,
  TelegramConnectSession,
  TelegramVerifyResult,
  Watchlist,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const ACCESS_TOKEN_KEY = "job-radar-access-token";
const REFRESH_TOKEN_KEY = "job-radar-refresh-token";

function getAccessToken() {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

function getRefreshToken() {
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

function storeTokens(tokens: AuthTokens) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
}

export function clearAuthSession() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

async function refreshAuthSession(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return false;
  }
  const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
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

async function requestJson<T>(path: string, options?: RequestInit, retryOnUnauthorized = true): Promise<T> {
  const accessToken = getAccessToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(options?.headers ?? {}),
    },
    ...options,
  });
  if (response.status === 401 && retryOnUnauthorized && !path.startsWith("/api/auth/")) {
    const refreshed = await refreshAuthSession();
    if (refreshed) {
      return requestJson<T>(path, options, false);
    }
  }
  if (!response.ok) {
    throw new Error(`Request failed for ${path}: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function hasStoredSession() {
  return Boolean(getAccessToken() && getRefreshToken());
}

export function fetchCurrentUser(): Promise<{ user: AuthUser }> {
  return requestJson<{ user: AuthUser }>("/api/auth/me");
}

export function fetchUserJobs(): Promise<{ items: JobOpportunity[] }> {
  return requestJson<{ items: JobOpportunity[] }>("/api/auth/me/jobs");
}

export function fetchUserAlerts(): Promise<{ items: AlertEvent[] }> {
  return requestJson<{ items: AlertEvent[] }>("/api/auth/me/alerts");
}

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

export async function logout(): Promise<void> {
  const refreshToken = getRefreshToken();
  if (refreshToken) {
    try {
      await requestJson<{ ok: boolean }>(
        "/api/auth/logout",
        {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken }),
        },
        false,
      );
    } catch {
      // Ignore logout failures and clear the local session regardless.
    }
  }
  clearAuthSession();
}

export function saveOnboarding(payload: Record<string, unknown>): Promise<{ user: AuthUser }> {
  return requestJson<{ user: AuthUser }>("/api/auth/me/onboarding", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function createTelegramConnectSession(): Promise<TelegramConnectSession> {
  return requestJson<TelegramConnectSession>("/api/auth/me/telegram/connect", {
    method: "POST",
  });
}

export function verifyTelegramConnection(connectToken: string): Promise<TelegramVerifyResult> {
  return requestJson<TelegramVerifyResult>("/api/auth/me/telegram/verify", {
    method: "POST",
    body: JSON.stringify({ connect_token: connectToken }),
  });
}

export function fetchDashboard(): Promise<DashboardSnapshot> {
  return requestJson<DashboardSnapshot>("/api/dashboard");
}

export function saveCompany(company: CompanyPreference): Promise<{ item: CompanyPreference }> {
  const path = company.id ? `/api/catalog/companies/${company.id}` : "/api/catalog/companies";
  const method = company.id ? "PUT" : "POST";
  return requestJson<{ item: CompanyPreference }>(path, {
    method,
    body: JSON.stringify({
      company: company.company,
      enabled: company.enabled,
      tier: company.tier,
      priority: company.priority,
      connector: company.connector,
      poll_interval_minutes: company.poll_interval_minutes,
      country: company.country,
      career_url: company.career_url,
      external_identifier: company.external_identifier,
      role_families: company.role_families,
    }),
  });
}

export function saveWatchlist(watchlist: Watchlist): Promise<{ item: Watchlist }> {
  const path = watchlist.id ? `/api/catalog/watchlists/${watchlist.id}` : "/api/catalog/watchlists";
  const method = watchlist.id ? "PUT" : "POST";
  return requestJson<{ item: Watchlist }>(path, {
    method,
    body: JSON.stringify({
      name: watchlist.name,
      enabled: watchlist.enabled,
      terms: watchlist.terms.map((term) => ({
        term: term.term,
        company: term.company,
        enabled: term.enabled,
      })),
    }),
  });
}

export function savePreferences(settings: ScoutSettings): Promise<{ item: ScoutSettings }> {
  return requestJson<{ item: ScoutSettings }>("/api/catalog/preferences", {
    method: "PUT",
    body: JSON.stringify({
      primary_connector: settings.primary_connector,
      minimum_match_score: settings.minimum_match_score,
      apply_now_threshold_score: settings.apply_now_threshold_score,
      review_threshold_score: settings.review_threshold_score,
      polling_interval_minutes: settings.polling_interval_minutes,
      selected_country: settings.selected_country,
      alert_freshness_hours: settings.alert_freshness_hours,
      dashboard_freshness_hours: settings.dashboard_freshness_hours,
      roles: settings.roles.filter((role) => role.enabled).map((role) => role.label),
      role_families: settings.role_families.filter((role) => role.enabled).map((role) => role.label),
      work_arrangements: settings.work_arrangements.filter((role) => role.enabled).map((role) => role.label),
      experience_levels: settings.experience_levels.filter((role) => role.enabled).map((role) => role.label),
      excluded_keywords: settings.excluded_keywords,
    }),
  });
}
