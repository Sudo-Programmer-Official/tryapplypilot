import type { AuthUser, CompanyPriorityLevel, SkillPriority, UserPreferenceDraft } from "../types";

const DEFAULT_JOB_TYPES = ["full_time", "contract", "contract_to_hire"];
const DEFAULT_COMPANY_SIZES = ["growth", "enterprise"];
const DEFAULT_INDUSTRIES = [
  "artificial_intelligence",
  "developer_tools",
  "cloud_infrastructure",
  "enterprise_software",
  "data_platform",
];
const DEFAULT_NOTIFICATION_RULES = ["only_new_jobs"];

function normalizeStrings(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item).trim()).filter(Boolean);
}

function normalizeCompanyPriority(value: unknown): CompanyPriorityLevel {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (normalized === "dream") {
    return "dream";
  }
  if (normalized === "high") {
    return "high";
  }
  if (normalized === "hidden") {
    return "hidden";
  }
  return "normal";
}

function normalizeCompanyPriorities(
  value: unknown,
  fallbackCompanies: string[],
): Record<string, CompanyPriorityLevel> {
  const priorities: Record<string, CompanyPriorityLevel> = {};
  if (value && typeof value === "object" && !Array.isArray(value)) {
    Object.entries(value as Record<string, unknown>).forEach(([company, priority]) => {
      const normalizedCompany = String(company).trim();
      if (!normalizedCompany) {
        return;
      }
      priorities[normalizedCompany] = normalizeCompanyPriority(priority);
    });
  }
  fallbackCompanies.forEach((company) => {
    if (!priorities[company]) {
      priorities[company] = "normal";
    }
  });
  return priorities;
}

function normalizeSkillPriorities(value: unknown, fallbackSkills: string[]): SkillPriority[] {
  const priorities: SkillPriority[] = [];
  const seen = new Set<string>();
  if (Array.isArray(value)) {
    value.forEach((item) => {
      if (!item || typeof item !== "object") {
        return;
      }
      const skill = String((item as Record<string, unknown>).skill ?? "").trim();
      if (!skill || seen.has(skill.toLowerCase())) {
        return;
      }
      seen.add(skill.toLowerCase());
      const rawWeight = Number((item as Record<string, unknown>).weight ?? 3);
      priorities.push({
        skill,
        weight: Number.isFinite(rawWeight) ? Math.max(1, Math.min(5, rawWeight)) : 3,
      });
    });
  }
  fallbackSkills.forEach((skill) => {
    if (!seen.has(skill.toLowerCase())) {
      seen.add(skill.toLowerCase());
      priorities.push({ skill, weight: 3 });
    }
  });
  return priorities;
}

export function createPreferenceDraft(user: AuthUser | null): UserPreferenceDraft {
  const preferredCompanies = normalizeStrings(user?.preferences.preferred_companies);
  const skills = normalizeStrings(user?.preferences.skills);
  const resumeLibrary = Array.isArray(user?.profile.resume_library) ? user?.profile.resume_library : [];
  return {
    full_name: user?.full_name ?? "",
    linkedin_url: user?.profile.linkedin_url ?? "",
    portfolio_url: user?.profile.portfolio_url ?? "",
    github_url: user?.profile.github_url ?? "",
    years_of_experience:
      typeof user?.preferences.years_of_experience === "number"
        ? user.preferences.years_of_experience
        : typeof user?.profile.years_of_experience === "number"
          ? user.profile.years_of_experience
          : null,
    visa_status: user?.preferences.visa_status ?? user?.profile.visa_status ?? "",
    work_authorization: user?.profile.work_authorization ?? "",
    country: user?.preferences.country ?? user?.country ?? "US",
    locations: normalizeStrings(user?.preferences.locations),
    preferred_companies: preferredCompanies,
    company_priorities: normalizeCompanyPriorities(user?.preferences.company_priorities, preferredCompanies),
    preferred_roles: normalizeStrings(user?.preferences.preferred_roles),
    skills,
    skill_priorities: normalizeSkillPriorities(user?.preferences.skill_priorities, skills),
    work_arrangements: normalizeStrings(user?.preferences.work_arrangements),
    experience_levels: normalizeStrings(user?.preferences.experience_levels),
    job_types: normalizeStrings(user?.preferences.job_types).length > 0 ? normalizeStrings(user?.preferences.job_types) : DEFAULT_JOB_TYPES,
    company_sizes:
      normalizeStrings(user?.preferences.company_sizes).length > 0
        ? normalizeStrings(user?.preferences.company_sizes)
        : DEFAULT_COMPANY_SIZES,
    industries:
      normalizeStrings(user?.preferences.industries).length > 0
        ? normalizeStrings(user?.preferences.industries)
        : DEFAULT_INDUSTRIES,
    minimum_salary:
      typeof user?.preferences.minimum_salary === "number" ? user.preferences.minimum_salary : null,
    desired_salary:
      typeof user?.preferences.desired_salary === "number" ? user.preferences.desired_salary : null,
    travel_preference: user?.preferences.travel_preference ?? "up_to_10",
    remote_preference: user?.preferences.remote_preference ?? "mostly_remote",
    freshness_hours: Number(user?.preferences.freshness_hours ?? 24),
    search_window_hours: Number(user?.preferences.search_window_hours ?? 24 * 7),
    minimum_match_score: Number(user?.preferences.minimum_match_score ?? 90),
    notification_frequency: user?.preferences.notification_frequency ?? "instant",
    notification_rules:
      normalizeStrings(user?.preferences.notification_rules).length > 0
        ? normalizeStrings(user?.preferences.notification_rules)
        : DEFAULT_NOTIFICATION_RULES,
    excluded_keywords: normalizeStrings(user?.preferences.excluded_keywords),
    resume_strategy: user?.preferences.resume_strategy ?? "auto",
    preferred_resume_variants:
      normalizeStrings(user?.preferences.preferred_resume_variants).length > 0
        ? normalizeStrings(user?.preferences.preferred_resume_variants)
        : resumeLibrary
            .map((entry) => String(entry.display_name ?? "").trim())
            .filter(Boolean),
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
  const weightedSkills = draft.skill_priorities.map((entry) => entry.skill.trim()).filter(Boolean);
  const dedupedSkills = Array.from(new Set([...weightedSkills, ...draft.skills.map((skill) => skill.trim()).filter(Boolean)]));
  return {
    country: draft.country,
    locations: draft.locations,
    preferred_companies: draft.preferred_companies,
    company_priorities: draft.company_priorities,
    preferred_roles: draft.preferred_roles,
    skills: dedupedSkills,
    skill_priorities: draft.skill_priorities
      .filter((entry) => entry.skill.trim())
      .map((entry) => ({ skill: entry.skill.trim(), weight: entry.weight })),
    work_arrangements: draft.work_arrangements,
    experience_levels: draft.experience_levels,
    job_types: draft.job_types,
    company_sizes: draft.company_sizes,
    industries: draft.industries,
    minimum_salary: draft.minimum_salary,
    desired_salary: draft.desired_salary,
    visa_status: draft.visa_status,
    years_of_experience: draft.years_of_experience,
    travel_preference: draft.travel_preference,
    remote_preference: draft.remote_preference,
    freshness_hours: draft.freshness_hours,
    search_window_hours: draft.search_window_hours,
    minimum_match_score: draft.minimum_match_score,
    notification_frequency: draft.notification_frequency,
    notification_rules: draft.notification_rules,
    excluded_keywords: draft.excluded_keywords,
    resume_strategy: draft.resume_strategy,
    preferred_resume_variants: draft.preferred_resume_variants,
  };
}

export function cloneDraft(draft: UserPreferenceDraft): UserPreferenceDraft {
  return {
    ...draft,
    locations: [...draft.locations],
    preferred_companies: [...draft.preferred_companies],
    company_priorities: { ...draft.company_priorities },
    preferred_roles: [...draft.preferred_roles],
    skills: [...draft.skills],
    skill_priorities: draft.skill_priorities.map((entry) => ({ ...entry })),
    work_arrangements: [...draft.work_arrangements],
    experience_levels: [...draft.experience_levels],
    job_types: [...draft.job_types],
    company_sizes: [...draft.company_sizes],
    industries: [...draft.industries],
    notification_rules: [...draft.notification_rules],
    excluded_keywords: [...draft.excluded_keywords],
    preferred_resume_variants: [...draft.preferred_resume_variants],
  };
}
