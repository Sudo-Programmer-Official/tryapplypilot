import type { AuthUser, UserPreferenceDraft } from "../types";

function normalizeStrings(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item).trim()).filter(Boolean);
}

export function createPreferenceDraft(user: AuthUser | null): UserPreferenceDraft {
  return {
    full_name: user?.full_name ?? "",
    linkedin_url: user?.profile.linkedin_url ?? "",
    portfolio_url: user?.profile.portfolio_url ?? "",
    github_url: user?.profile.github_url ?? "",
    years_of_experience:
      typeof user?.profile.years_of_experience === "number" ? user.profile.years_of_experience : null,
    visa_status: user?.profile.visa_status ?? "",
    work_authorization: user?.profile.work_authorization ?? "",
    country: user?.preferences.country ?? user?.country ?? "US",
    locations: normalizeStrings(user?.preferences.locations),
    preferred_companies: normalizeStrings(user?.preferences.preferred_companies),
    preferred_roles: normalizeStrings(user?.preferences.preferred_roles),
    skills: normalizeStrings(user?.preferences.skills),
    work_arrangements: normalizeStrings(user?.preferences.work_arrangements),
    experience_levels: normalizeStrings(user?.preferences.experience_levels),
    freshness_hours: Number(user?.preferences.freshness_hours ?? 6),
    minimum_match_score: Number(user?.preferences.minimum_match_score ?? 90),
    notification_frequency: user?.preferences.notification_frequency ?? "instant",
  };
}

export function buildProfilePayload(draft: UserPreferenceDraft): Record<string, unknown> {
  return {
    full_name: draft.full_name,
    linkedin_url: draft.linkedin_url,
    portfolio_url: draft.portfolio_url,
    github_url: draft.github_url,
    years_of_experience: draft.years_of_experience,
    visa_status: draft.visa_status,
    work_authorization: draft.work_authorization,
  };
}

export function buildPreferencePayload(draft: UserPreferenceDraft): Record<string, unknown> {
  return {
    country: draft.country,
    locations: draft.locations,
    preferred_companies: draft.preferred_companies,
    preferred_roles: draft.preferred_roles,
    skills: draft.skills,
    work_arrangements: draft.work_arrangements,
    experience_levels: draft.experience_levels,
    freshness_hours: draft.freshness_hours,
    minimum_match_score: draft.minimum_match_score,
    notification_frequency: draft.notification_frequency,
  };
}

export function cloneDraft(draft: UserPreferenceDraft): UserPreferenceDraft {
  return {
    ...draft,
    locations: [...draft.locations],
    preferred_companies: [...draft.preferred_companies],
    preferred_roles: [...draft.preferred_roles],
    skills: [...draft.skills],
    work_arrangements: [...draft.work_arrangements],
    experience_levels: [...draft.experience_levels],
  };
}
