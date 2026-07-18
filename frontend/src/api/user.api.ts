import type { AlertEvent, AuthUser, CompanyRequest, JobOpportunity, SavedJobRecord, Watchlist } from "../types";
import { requestJson } from "./client";

export function fetchUserJobs(): Promise<{ items: JobOpportunity[] }> {
  return requestJson<{ items: JobOpportunity[] }>("/api/auth/me/jobs");
}

export function fetchUserAlerts(): Promise<{ items: AlertEvent[] }> {
  return requestJson<{ items: AlertEvent[] }>("/api/auth/me/alerts");
}

export function fetchUserCompanyRequests(): Promise<{ items: CompanyRequest[] }> {
  return requestJson<{ items: CompanyRequest[] }>("/api/auth/me/company-requests");
}

export function createUserCompanyRequest(payload: {
  company_name: string;
  career_url: string;
  connector_suggestion: string;
  external_identifier_suggestion: string;
  notes: string;
}): Promise<{ item: CompanyRequest }> {
  return requestJson<{ item: CompanyRequest }>("/api/auth/me/company-requests", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchUserSavedJobs(): Promise<{ items: SavedJobRecord[] }> {
  return requestJson<{ items: SavedJobRecord[] }>("/api/auth/me/saved-jobs");
}

export function saveUserSavedJob(jobId: string): Promise<{ item: SavedJobRecord }> {
  return requestJson<{ item: SavedJobRecord }>("/api/auth/me/saved-jobs", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId }),
  });
}

export function deleteUserSavedJob(jobId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/auth/me/saved-jobs/${jobId}`, {
    method: "DELETE",
  });
}

export function fetchUserWatchlists(): Promise<{ items: Watchlist[] }> {
  return requestJson<{ items: Watchlist[] }>("/api/auth/me/watchlists");
}

export function createUserWatchlist(watchlist: Watchlist): Promise<{ item: Watchlist }> {
  return requestJson<{ item: Watchlist }>("/api/auth/me/watchlists", {
    method: "POST",
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

export function updateUserWatchlist(watchlist: Watchlist): Promise<{ item: Watchlist }> {
  return requestJson<{ item: Watchlist }>(`/api/auth/me/watchlists/${watchlist.id}`, {
    method: "PATCH",
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

export function deleteUserWatchlist(watchlistId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/auth/me/watchlists/${watchlistId}`, {
    method: "DELETE",
  });
}

export function saveUserProfile(payload: Record<string, unknown>): Promise<{ user: AuthUser }> {
  return requestJson<{ user: AuthUser }>("/api/auth/me/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function saveUserPreferences(payload: Record<string, unknown>): Promise<{ user: AuthUser }> {
  return requestJson<{ user: AuthUser }>("/api/auth/me/preferences", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
