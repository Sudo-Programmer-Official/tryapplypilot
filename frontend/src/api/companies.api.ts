import type { CompanyPreference, ScoutSettings, Watchlist } from "../types";
import { requestJson } from "./client";

export function fetchCatalogCompanies(): Promise<{ items: CompanyPreference[] }> {
  return requestJson<{ items: CompanyPreference[] }>("/api/catalog/companies");
}

export function importRecommendedCompanies(): Promise<{ items: CompanyPreference[]; summary: { count: number; enabled_count: number } }> {
  return requestJson<{ items: CompanyPreference[]; summary: { count: number; enabled_count: number } }>(
    "/api/catalog/companies/import-defaults",
    {
      method: "POST",
    },
  );
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

export function fetchCatalogWatchlists(): Promise<{ items: Watchlist[] }> {
  return requestJson<{ items: Watchlist[] }>("/api/catalog/watchlists");
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

export function fetchAdminSettings(): Promise<ScoutSettings> {
  return requestJson<ScoutSettings>("/api/settings");
}

export function saveAdminPreferences(settings: ScoutSettings): Promise<{ item: ScoutSettings }> {
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
      resume_variants: settings.resume_variants,
      initial_alert_window_hours: settings.initial_alert_window_hours,
      initial_sync_openai_job_limit: settings.initial_sync_openai_job_limit,
      initial_sync_max_alerts: settings.initial_sync_max_alerts,
    }),
  });
}
