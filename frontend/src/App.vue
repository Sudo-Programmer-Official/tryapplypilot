<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import StatCard from "./components/StatCard.vue";
import {
  clearAuthSession,
  createTelegramConnectSession,
  fetchCurrentUser,
  fetchDashboard,
  fetchUserAlerts,
  fetchUserJobs,
  hasStoredSession,
  login,
  logout,
  saveCompany,
  saveOnboarding,
  savePreferences,
  saveWatchlist,
  signup,
  verifyTelegramConnection,
} from "./lib/api";
import type {
  AlertEvent,
  AuthUser,
  CompanyPreference,
  DashboardSnapshot,
  JobOpportunity,
  ScoutSettings,
  SourceStatus,
  TelegramConnectSession,
  Watchlist,
} from "./types";

type AuthMode = "login" | "signup";
type OnboardingDraft = {
  full_name: string;
  linkedin_url: string;
  portfolio_url: string;
  github_url: string;
  years_of_experience: number | null;
  visa_status: string;
  work_authorization: string;
  resume_uploaded: boolean;
  country: string;
  freshness_hours: number;
  minimum_match_score: number;
};

const snapshot = ref<DashboardSnapshot | null>(null);
const currentUser = ref<AuthUser | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const authMode = ref<AuthMode>("login");
const authEmail = ref("");
const authPassword = ref("");
const authFullName = ref("");
const authMessage = ref<string | null>(null);
const saving = ref(false);
const saveMessage = ref<string | null>(null);
const companyDrafts = ref<CompanyPreference[]>([]);
const watchlistDrafts = ref<Watchlist[]>([]);
const settingsDraft = ref<ScoutSettings | null>(null);
const rolesText = ref("");
const roleFamiliesText = ref("");
const workArrangementsText = ref("");
const experienceLevelsText = ref("");
const excludedKeywordsText = ref("");
const newCompany = ref<CompanyPreference>(createBlankCompany());
const newWatchlistName = ref("");
const newWatchlistTerms = ref("");
const onboardingDraft = ref<OnboardingDraft>(createBlankOnboardingDraft());
const onboardingLocationsText = ref("");
const onboardingCompaniesText = ref("");
const onboardingRolesText = ref("");
const onboardingSkillsText = ref("");
const onboardingWatchlistsText = ref("");
const onboardingWorkArrangementsText = ref("");
const onboardingExperienceLevelsText = ref("");
const telegramConnectSession = ref<TelegramConnectSession | null>(null);
const telegramMessage = ref<string | null>(null);
const userJobs = ref<JobOpportunity[]>([]);
const userAlerts = ref<AlertEvent[]>([]);

const notificationPreview = computed(() => snapshot.value?.notification_preview ?? null);
const isAdminUser = computed(() => currentUser.value?.role === "admin" || currentUser.value?.role === "super_admin");
const applyNowJobs = computed(() => snapshot.value?.jobs.filter((job) => job.decision === "APPLY_NOW") ?? []);
const reviewJobs = computed(() => snapshot.value?.jobs.filter((job) => job.decision === "REVIEW") ?? []);
const ignoreJobs = computed(() => snapshot.value?.jobs.filter((job) => job.decision === "IGNORE") ?? []);
const enabledCompanyCount = computed(() => snapshot.value?.settings.companies.filter((company) => company.enabled).length ?? 0);
const enabledRoleCount = computed(() => snapshot.value?.settings.roles.filter((role) => role.enabled).length ?? 0);
const enabledRoleFamilyCount = computed(() => snapshot.value?.settings.role_families.filter((family) => family.enabled).length ?? 0);
const systemStatusComponents = computed(() => snapshot.value?.system_status.components ?? []);
const systemStatusStats = computed(() => snapshot.value?.system_status.stats ?? null);

const summaryCards = computed(() => {
  if (!snapshot.value) {
    return [];
  }

  const { summary } = snapshot.value;
  return [
    {
      label: "Today's jobs",
      value: summary.todays_jobs,
      detail: "New roles ingested",
      tone: "ink" as const,
    },
    {
      label: "Apply now",
      value: summary.apply_now_queue,
      detail: `>= ${summary.apply_now_threshold_score}% match`,
      tone: "clay" as const,
    },
    {
      label: "Review",
      value: summary.review_queue,
      detail: `${summary.review_threshold_score}-${summary.apply_now_threshold_score - 1}% match`,
      tone: "brass" as const,
    },
    {
      label: "Ignore",
      value: summary.ignore_queue,
      detail: `< ${summary.review_threshold_score}% match`,
      tone: "moss" as const,
    },
    {
      label: "Live connectors",
      value: summary.live_connectors,
      detail: `${summary.next_connectors} queued next`,
      tone: "ink" as const,
    },
    {
      label: "Alerts sent",
      value: summary.alerts_sent,
      detail: "Telegram-first delivery",
      tone: "moss" as const,
    },
  ];
});

function createBlankCompany(): CompanyPreference {
  return {
    id: "",
    company: "",
    enabled: true,
    tier: 3,
    priority: 999,
    connector: "company-api",
    poll_interval_minutes: 5,
    country: "US",
    career_url: "",
    external_identifier: "",
    role_families: ["Core Engineering", "Backend"],
  };
}

function createBlankOnboardingDraft(): OnboardingDraft {
  return {
    full_name: "",
    linkedin_url: "",
    portfolio_url: "",
    github_url: "",
    years_of_experience: null,
    visa_status: "",
    work_authorization: "",
    resume_uploaded: false,
    country: "US",
    freshness_hours: 6,
    minimum_match_score: 90,
  };
}

function cloneCompany(company: CompanyPreference): CompanyPreference {
  return {
    ...company,
    role_families: [...company.role_families],
  };
}

function cloneWatchlist(watchlist: Watchlist): Watchlist {
  return {
    ...watchlist,
    terms: watchlist.terms.map((term) => ({ ...term })),
  };
}

function cloneSettings(settings: ScoutSettings): ScoutSettings {
  return {
    ...settings,
    companies: settings.companies.map(cloneCompany),
    roles: settings.roles.map((role) => ({ ...role })),
    notifications: settings.notifications.map((channel) => ({ ...channel })),
    role_families: settings.role_families.map((family) => ({ ...family })),
    work_arrangements: settings.work_arrangements.map((arrangement) => ({ ...arrangement })),
    experience_levels: settings.experience_levels.map((level) => ({ ...level })),
    excluded_keywords: [...settings.excluded_keywords],
    watchlists: settings.watchlists.map(cloneWatchlist),
  };
}

function toCommaText(values: string[]) {
  return values.join(", ");
}

function parseCommaText(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function watchlistTermsText(watchlist: Watchlist) {
  return watchlist.terms
    .map((term) => (term.company ? `${term.company} | ${term.term}` : term.term))
    .join("\n");
}

function parseWatchlistTerms(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item, index) => {
      const [companyPart, termPart] = item.includes("|")
        ? item.split("|", 2).map((part) => part.trim())
        : ["", item];
      return {
        id: `draft-${index}-${companyPart}-${termPart}`,
        company: companyPart,
        term: termPart,
        enabled: true,
      };
    });
}

function syncDraftsFromSnapshot() {
  if (!snapshot.value) {
    return;
  }
  companyDrafts.value = snapshot.value.settings.companies.map(cloneCompany);
  watchlistDrafts.value = snapshot.value.settings.watchlists.map(cloneWatchlist);
  settingsDraft.value = cloneSettings(snapshot.value.settings);
  rolesText.value = toCommaText(snapshot.value.settings.roles.filter((role) => role.enabled).map((role) => role.label));
  roleFamiliesText.value = toCommaText(snapshot.value.settings.role_families.filter((role) => role.enabled).map((role) => role.label));
  workArrangementsText.value = toCommaText(snapshot.value.settings.work_arrangements.filter((role) => role.enabled).map((role) => role.label));
  experienceLevelsText.value = toCommaText(snapshot.value.settings.experience_levels.filter((role) => role.enabled).map((role) => role.label));
  excludedKeywordsText.value = toCommaText(snapshot.value.settings.excluded_keywords);
}

function syncOnboardingDraftFromUser() {
  if (!currentUser.value) {
    onboardingDraft.value = createBlankOnboardingDraft();
    onboardingLocationsText.value = "";
    onboardingCompaniesText.value = "";
    onboardingRolesText.value = "";
    onboardingSkillsText.value = "";
    onboardingWatchlistsText.value = "";
    onboardingWorkArrangementsText.value = "";
    onboardingExperienceLevelsText.value = "";
    return;
  }
  const profile = currentUser.value.profile ?? {};
  const preferences = currentUser.value.preferences ?? {};
  onboardingDraft.value = {
    full_name: String(profile.full_name ?? currentUser.value.full_name ?? ""),
    linkedin_url: String(profile.linkedin_url ?? ""),
    portfolio_url: String(profile.portfolio_url ?? ""),
    github_url: String(profile.github_url ?? ""),
    years_of_experience:
      typeof profile.years_of_experience === "number"
        ? profile.years_of_experience
        : profile.years_of_experience === null || profile.years_of_experience === undefined
          ? null
          : Number(profile.years_of_experience),
    visa_status: String(profile.visa_status ?? ""),
    work_authorization: String(profile.work_authorization ?? ""),
    resume_uploaded: Boolean(profile.resume_uploaded),
    country: String(preferences.country ?? currentUser.value.country ?? "US"),
    freshness_hours: Number(preferences.freshness_hours ?? 6),
    minimum_match_score: Number(preferences.minimum_match_score ?? 90),
  };
  onboardingLocationsText.value = toCommaText(Array.isArray(preferences.locations) ? preferences.locations.map(String) : []);
  onboardingCompaniesText.value = toCommaText(Array.isArray(preferences.preferred_companies) ? preferences.preferred_companies.map(String) : []);
  onboardingRolesText.value = toCommaText(Array.isArray(preferences.preferred_roles) ? preferences.preferred_roles.map(String) : []);
  onboardingSkillsText.value = toCommaText(Array.isArray(preferences.skills) ? preferences.skills.map(String) : []);
  onboardingWatchlistsText.value = toCommaText(Array.isArray(preferences.watchlists) ? preferences.watchlists.map(String) : []);
  onboardingWorkArrangementsText.value = toCommaText(Array.isArray(preferences.work_arrangements) ? preferences.work_arrangements.map(String) : []);
  onboardingExperienceLevelsText.value = toCommaText(Array.isArray(preferences.experience_levels) ? preferences.experience_levels.map(String) : []);
}

async function refreshDashboard() {
  if (!isAdminUser.value) {
    snapshot.value = null;
    return;
  }
  snapshot.value = await fetchDashboard();
  syncDraftsFromSnapshot();
}

async function refreshSessionState() {
  const payload = await fetchCurrentUser();
  currentUser.value = payload.user;
  authMessage.value = null;
  telegramMessage.value = null;
  if (isAdminUser.value) {
    await refreshDashboard();
  } else {
    snapshot.value = null;
    syncOnboardingDraftFromUser();
    const [jobsPayload, alertsPayload] = await Promise.all([fetchUserJobs(), fetchUserAlerts()]);
    userJobs.value = jobsPayload.items;
    userAlerts.value = alertsPayload.items;
  }
}

async function runSave(operation: () => Promise<void>, successMessage: string) {
  saving.value = true;
  saveMessage.value = null;
  error.value = null;
  try {
    await operation();
    await refreshDashboard();
    saveMessage.value = successMessage;
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : "Unknown request failure";
  } finally {
    saving.value = false;
  }
}

async function submitAuth() {
  loading.value = true;
  authMessage.value = null;
  error.value = null;
  try {
    currentUser.value =
      authMode.value === "login"
        ? await login(authEmail.value, authPassword.value)
        : await signup(authEmail.value, authPassword.value, authFullName.value);
    if (isAdminUser.value) {
      await refreshDashboard();
    } else {
      snapshot.value = null;
      syncOnboardingDraftFromUser();
      const [jobsPayload, alertsPayload] = await Promise.all([fetchUserJobs(), fetchUserAlerts()]);
      userJobs.value = jobsPayload.items;
      userAlerts.value = alertsPayload.items;
    }
    authPassword.value = "";
    authMessage.value = authMode.value === "login" ? "Signed in." : "Account created.";
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : "Unknown request failure";
  } finally {
    loading.value = false;
  }
}

async function handleLogout() {
  await logout();
  clearAuthSession();
  currentUser.value = null;
  snapshot.value = null;
  telegramConnectSession.value = null;
  telegramMessage.value = null;
  userJobs.value = [];
  userAlerts.value = [];
  authEmail.value = "";
  authPassword.value = "";
  authFullName.value = "";
  authMessage.value = "Signed out.";
  saveMessage.value = null;
}

async function beginTelegramConnect() {
  saving.value = true;
  telegramMessage.value = null;
  error.value = null;
  try {
    telegramConnectSession.value = await createTelegramConnectSession();
    telegramMessage.value = "Open the bot link, press Start, then come back and verify.";
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : "Unknown request failure";
  } finally {
    saving.value = false;
  }
}

async function verifyTelegramConnect() {
  if (!telegramConnectSession.value) {
    telegramMessage.value = "Generate a Telegram connect link first.";
    return;
  }
  saving.value = true;
  telegramMessage.value = null;
  error.value = null;
  try {
    const payload = await verifyTelegramConnection(telegramConnectSession.value.connect_token);
    currentUser.value = payload.user;
    syncOnboardingDraftFromUser();
    telegramMessage.value = payload.connected
      ? "✅ Telegram Connected. You'll now receive personalized job alerts."
      : payload.message ?? "Telegram bot has not received the start command yet.";
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : "Unknown request failure";
  } finally {
    saving.value = false;
  }
}

function decisionClass(decision: "APPLY_NOW" | "REVIEW" | "IGNORE") {
  if (decision === "APPLY_NOW") {
    return "border-clay/25 bg-clay/10 text-clay";
  }
  if (decision === "REVIEW") {
    return "border-brass/25 bg-brass/10 text-brass";
  }
  return "border-moss/25 bg-moss/10 text-moss";
}

function recommendationClass(tone: "apply" | "review" | "skip") {
  if (tone === "apply") {
    return "border-clay/25 bg-clay/10 text-clay";
  }
  if (tone === "review") {
    return "border-brass/25 bg-brass/10 text-brass";
  }
  return "border-moss/25 bg-moss/10 text-moss";
}

function freshnessClass(tone: "fresh" | "aging" | "stale") {
  if (tone === "fresh") {
    return "border-moss/20 bg-moss/10 text-moss";
  }
  if (tone === "aging") {
    return "border-brass/20 bg-brass/10 text-brass";
  }
  return "border-clay/20 bg-clay/10 text-clay";
}

function decisionLabel(decision: "APPLY_NOW" | "REVIEW" | "IGNORE") {
  if (decision === "APPLY_NOW") {
    return "Apply Now";
  }
  if (decision === "REVIEW") {
    return "Review";
  }
  return "Ignore";
}

function jobStatusClass(status: "new" | "seen" | "dismissed" | "skipped") {
  if (status === "new") {
    return "border-moss/20 bg-moss/10 text-moss";
  }
  if (status === "seen") {
    return "border-ink/15 bg-white/70 text-ink/70";
  }
  if (status === "dismissed") {
    return "border-clay/20 bg-clay/10 text-clay";
  }
  return "border-brass/20 bg-brass/10 text-brass";
}

function sourceStateClass(state: "healthy" | "lagging" | "degraded") {
  if (state === "healthy") {
    return "border-moss/20 bg-moss/10 text-moss";
  }
  if (state === "lagging") {
    return "border-brass/20 bg-brass/10 text-brass";
  }
  return "border-clay/20 bg-clay/10 text-clay";
}

function systemStateClass(state: "healthy" | "lagging" | "degraded") {
  if (state === "healthy") {
    return "border-moss/20 bg-moss/10 text-moss";
  }
  if (state === "lagging") {
    return "border-brass/20 bg-brass/10 text-brass";
  }
  return "border-clay/20 bg-clay/10 text-clay";
}

function systemStateGlyph(state: "healthy" | "lagging" | "degraded") {
  if (state === "healthy") {
    return "✓";
  }
  if (state === "lagging") {
    return "!";
  }
  return "×";
}

function rolloutStageClass(stage: "live" | "next" | "later") {
  if (stage === "live") {
    return "border-clay/20 bg-clay/10 text-clay";
  }
  if (stage === "next") {
    return "border-brass/20 bg-brass/10 text-brass";
  }
  return "border-ink/15 bg-white/70 text-ink/70";
}

function rolloutStageLabel(stage: "live" | "next" | "later") {
  if (stage === "live") {
    return "Live";
  }
  if (stage === "next") {
    return "Next";
  }
  return "Later";
}

function companyTierClass(tier: number) {
  if (tier === 1) {
    return "border-clay/25 bg-clay/10 text-clay";
  }
  if (tier === 2) {
    return "border-brass/25 bg-brass/10 text-brass";
  }
  return "border-moss/20 bg-moss/10 text-moss";
}

function companyTierLabel(tier: number) {
  if (tier === 1) {
    return "Tier 1";
  }
  if (tier === 2) {
    return "Tier 2";
  }
  return "Tier 3";
}

function connectorLabel(connector: string) {
  const normalized = connector.trim().toLowerCase();
  if (normalized === "company-api") {
    return "Company API";
  }
  if (normalized === "microsoft-careers") {
    return "Microsoft Careers";
  }
  if (normalized === "google-careers") {
    return "Google Careers";
  }
  if (normalized === "smartrecruiters") {
    return "SmartRecruiters";
  }
  return connector
    .split("-")
    .map((value) => value.charAt(0).toUpperCase() + value.slice(1))
    .join(" ");
}

function channelLabel(channel: "telegram" | "email" | "slack" | "desktop") {
  return channel.charAt(0).toUpperCase() + channel.slice(1);
}

function toggleGlyph(enabled: boolean) {
  return enabled ? "☑" : "☐";
}

function formatGeneratedAt(timestamp: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

function countryLabel(code: string) {
  if (code === "US") {
    return "🇺🇸 United States";
  }
  if (code === "CA") {
    return "🇨🇦 Canada";
  }
  if (code === "IN") {
    return "🇮🇳 India";
  }
  return "🌍 Any";
}

function formatClock(timestamp: string | null) {
  if (!timestamp) {
    return "Waiting";
  }
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

function formatSync(source: SourceStatus) {
  if (!source.last_successful_sync) {
    return "Not synced yet";
  }
  return formatGeneratedAt(source.last_successful_sync);
}

function formatLastRun(source: SourceStatus) {
  if (source.last_run_minutes_ago === null) {
    return "Not running yet";
  }
  return `${source.last_run_minutes_ago} minutes ago`;
}

function renderQueueReason(job: JobOpportunity) {
  return job.why.join(" • ");
}

function renderGapReason(job: JobOpportunity) {
  return job.gaps.join(" • ");
}

function updateCompanyRoleFamilies(index: number, value: string) {
  companyDrafts.value[index].role_families = parseCommaText(value);
}

function updateWatchlistTerms(index: number, value: string) {
  watchlistDrafts.value[index].terms = parseWatchlistTerms(value);
}

async function persistCompany(company: CompanyPreference) {
  await runSave(async () => {
    await saveCompany(company);
  }, `${company.company} saved.`);
}

async function addCompany() {
  if (!newCompany.value.company.trim()) {
    error.value = "Company name is required.";
    return;
  }
  const payload = cloneCompany(newCompany.value);
  await runSave(async () => {
    await saveCompany(payload);
  }, `${payload.company} added.`);
  newCompany.value = createBlankCompany();
}

async function persistPreferences() {
  if (settingsDraft.value === null) {
    return;
  }
  const payload: ScoutSettings = {
    ...settingsDraft.value,
    roles: parseCommaText(rolesText.value).map((label) => ({ label, enabled: true })),
    role_families: parseCommaText(roleFamiliesText.value).map((label) => ({ label, enabled: true })),
    work_arrangements: parseCommaText(workArrangementsText.value).map((label) => ({ label, enabled: true })),
    experience_levels: parseCommaText(experienceLevelsText.value).map((label) => ({ label, enabled: true })),
    excluded_keywords: parseCommaText(excludedKeywordsText.value),
  };
  await runSave(async () => {
    await savePreferences(payload);
  }, "Preferences saved.");
}

async function persistWatchlist(watchlist: Watchlist) {
  await runSave(async () => {
    await saveWatchlist(watchlist);
  }, `${watchlist.name} saved.`);
}

async function addWatchlist() {
  if (!newWatchlistName.value.trim()) {
    error.value = "Watchlist name is required.";
    return;
  }
  const payload: Watchlist = {
    id: "",
    name: newWatchlistName.value.trim(),
    enabled: true,
    terms: parseWatchlistTerms(newWatchlistTerms.value),
  };
  await runSave(async () => {
    await saveWatchlist(payload);
  }, `${payload.name} added.`);
  newWatchlistName.value = "";
  newWatchlistTerms.value = "";
}

async function persistOnboarding() {
  if (!currentUser.value) {
    return;
  }
  saving.value = true;
  saveMessage.value = null;
  error.value = null;
  try {
    const payload = await saveOnboarding({
      ...onboardingDraft.value,
      locations: parseCommaText(onboardingLocationsText.value),
      preferred_companies: parseCommaText(onboardingCompaniesText.value),
      preferred_roles: parseCommaText(onboardingRolesText.value),
      skills: parseCommaText(onboardingSkillsText.value),
      watchlists: parseCommaText(onboardingWatchlistsText.value),
      work_arrangements: parseCommaText(onboardingWorkArrangementsText.value),
      experience_levels: parseCommaText(onboardingExperienceLevelsText.value),
    });
    currentUser.value = payload.user;
    syncOnboardingDraftFromUser();
    saveMessage.value = "Onboarding settings saved.";
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : "Unknown request failure";
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  try {
    if (hasStoredSession()) {
      await refreshSessionState();
    }
  } catch (caughtError) {
    clearAuthSession();
    currentUser.value = null;
    error.value = caughtError instanceof Error ? caughtError.message : "Unknown request failure";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <main class="relative overflow-hidden">
    <div class="pointer-events-none absolute inset-0">
      <div class="absolute left-[-8rem] top-20 h-48 w-48 rounded-full bg-clay/15 blur-3xl" />
      <div class="absolute right-[-5rem] top-8 h-56 w-56 rounded-full bg-moss/10 blur-3xl" />
      <div class="absolute bottom-16 left-1/3 h-48 w-48 rounded-full bg-brass/10 blur-3xl" />
    </div>

    <div class="relative mx-auto max-w-7xl px-5 py-8 sm:px-6 lg:px-8 lg:py-10">
      <section class="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <article class="panel p-8">
          <p class="eyebrow">Phase 1.0</p>
          <h1 class="mt-4 max-w-3xl font-display text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
            One real source end-to-end before anything else.
          </h1>
          <p class="mt-5 max-w-2xl text-base leading-7 text-ink/70 sm:text-lg">
            The active build target is a single production-ready path: collect from Greenhouse, normalize, deduplicate,
            store, match, notify on Telegram, and show the result in the dashboard, all on your local machine first.
          </p>

          <div v-if="snapshot" class="mt-8 flex flex-wrap gap-3">
            <span class="chip">{{ snapshot.product.name }}</span>
            <span class="chip">Local-first phase</span>
            <span class="chip">{{ snapshot.agent.current_connector }} live connector</span>
            <span class="chip">Telegram first channel</span>
            <span class="chip">{{ snapshot.agent.polling_interval_minutes }} minute polling cadence</span>
            <span class="chip">Updated {{ formatGeneratedAt(snapshot.generated_at) }}</span>
          </div>
          <div v-else-if="currentUser" class="mt-8 flex flex-wrap items-center gap-3">
            <span class="chip">{{ currentUser.email }}</span>
            <span class="chip">{{ currentUser.role === "super_admin" ? "Super Admin" : currentUser.role === "admin" ? "Admin" : "User" }}</span>
            <button
              class="rounded-full border border-ink/10 bg-white/80 px-4 py-2 text-sm font-semibold text-ink transition hover:bg-white"
              @click="handleLogout"
            >
              Sign out
            </button>
          </div>
        </article>

        <article class="panel flex flex-col justify-between p-8">
          <div>
            <p class="eyebrow">Execution Focus</p>
            <h2 class="mt-4 font-display text-2xl font-semibold tracking-tight text-ink">
              {{ snapshot?.agent.name ?? "Market Scout Agent" }}
            </h2>
            <p class="mt-4 text-base leading-7 text-ink/70">
              New features stay blocked until the first connector is live, scheduled, deduped, persisted, matched, and
              producing real Telegram alerts reliably.
            </p>
          </div>

          <div class="mt-6 grid gap-3 rounded-[26px] border border-ink/10 bg-smoke/45 p-5">
            <div class="flex items-center justify-between">
              <span class="subtle-label">Connector</span>
              <span class="font-display text-2xl font-semibold text-clay">
                {{ snapshot?.agent.current_connector ?? "Greenhouse" }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="subtle-label">Apply now threshold</span>
              <span class="text-sm font-semibold text-ink">
                {{ snapshot?.agent.apply_now_threshold_score ?? "--" }}%
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="subtle-label">Review threshold</span>
              <span class="text-sm font-semibold text-ink">
                {{ snapshot?.agent.review_threshold_score ?? "--" }}%
              </span>
            </div>
            <div class="mt-2 flex flex-wrap gap-2">
              <span v-for="step in snapshot?.agent.workflow ?? []" :key="step" class="chip">{{ step }}</span>
            </div>
          </div>
        </article>
      </section>

      <section v-if="loading" class="mt-8 panel p-8">
        <p class="panel-title">Loading market radar...</p>
      </section>

      <section v-else-if="!currentUser" class="mt-8 grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <article class="panel p-8">
          <p class="eyebrow">Sign In</p>
          <h3 class="panel-title mt-2">{{ authMode === "login" ? "Access the admin portal" : "Create a new account" }}</h3>
          <p class="mt-4 text-sm leading-6 text-ink/70">
            Admins land in the operations dashboard. Standard users get the onboarding portal and private job preferences.
          </p>
          <div class="mt-6 flex gap-2">
            <button
              :class="['rounded-full px-4 py-2 text-sm font-semibold transition', authMode === 'login' ? 'bg-ink text-white' : 'border border-ink/10 bg-white/80 text-ink']"
              @click="authMode = 'login'"
            >
              Login
            </button>
            <button
              :class="['rounded-full px-4 py-2 text-sm font-semibold transition', authMode === 'signup' ? 'bg-ink text-white' : 'border border-ink/10 bg-white/80 text-ink']"
              @click="authMode = 'signup'"
            >
              Sign up
            </button>
          </div>
          <div class="mt-6 grid gap-4">
            <label v-if="authMode === 'signup'" class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Full name</span>
              <input v-model="authFullName" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Email</span>
              <input v-model="authEmail" type="email" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Password</span>
              <input v-model="authPassword" type="password" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
          </div>
          <p v-if="authMessage" class="mt-4 rounded-[18px] border border-moss/20 bg-moss/10 px-4 py-3 text-sm text-moss">
            {{ authMessage }}
          </p>
          <p v-if="error" class="mt-4 rounded-[18px] border border-clay/20 bg-clay/10 px-4 py-3 text-sm text-clay">
            {{ error }}
          </p>
          <button
            class="mt-6 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="loading"
            @click="submitAuth"
          >
            {{ authMode === "login" ? "Login" : "Create account" }}
          </button>
        </article>

        <article class="panel p-8">
          <p class="eyebrow">V1 Flow</p>
          <h3 class="panel-title mt-2">Seven steps to receiving personalized job alerts</h3>
          <div class="mt-6 grid gap-3">
            <div class="rounded-[20px] border border-ink/10 bg-white/80 px-4 py-3 text-sm text-ink/75">1. Create account</div>
            <div class="rounded-[20px] border border-ink/10 bg-white/80 px-4 py-3 text-sm text-ink/75">2. Upload resume metadata</div>
            <div class="rounded-[20px] border border-ink/10 bg-white/80 px-4 py-3 text-sm text-ink/75">3. Choose country and locations</div>
            <div class="rounded-[20px] border border-ink/10 bg-white/80 px-4 py-3 text-sm text-ink/75">4. Choose companies and roles</div>
            <div class="rounded-[20px] border border-ink/10 bg-white/80 px-4 py-3 text-sm text-ink/75">5. Set match and freshness thresholds</div>
            <div class="rounded-[20px] border border-ink/10 bg-white/80 px-4 py-3 text-sm text-ink/75">6. Connect Telegram</div>
            <div class="rounded-[20px] border border-ink/10 bg-white/80 px-4 py-3 text-sm text-ink/75">7. Start receiving private alerts</div>
          </div>
        </article>
      </section>

      <section v-else-if="currentUser && !isAdminUser" class="mt-8 grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <article class="panel p-8">
          <p class="eyebrow">User Portal</p>
          <h3 class="panel-title mt-2">Complete your setup</h3>
          <p class="mt-4 text-sm leading-6 text-ink/70">
            This is the first user-facing slice: onboarding progress, personal preferences, and private Telegram-ready account settings.
          </p>
          <div class="mt-6 rounded-[24px] border border-ink/10 bg-smoke/45 p-5">
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="subtle-label">Setup progress</p>
                <p class="mt-2 font-display text-4xl font-semibold text-ink">{{ currentUser.onboarding.progress_percent }}%</p>
              </div>
              <span class="chip">{{ currentUser.email }}</span>
            </div>
            <div class="mt-5 space-y-3">
              <div
                v-for="step in currentUser.onboarding.steps"
                :key="step.id"
                class="flex items-center justify-between rounded-[18px] border border-ink/10 bg-white/80 px-4 py-3 text-sm text-ink/75"
              >
                <span>{{ step.label }}</span>
                <span class="font-semibold">{{ step.completed ? "✓" : "○" }}</span>
              </div>
            </div>
          </div>
          <p v-if="saveMessage" class="mt-4 rounded-[18px] border border-moss/20 bg-moss/10 px-4 py-3 text-sm text-moss">
            {{ saveMessage }}
          </p>
          <p v-if="telegramMessage" class="mt-4 rounded-[18px] border border-brass/20 bg-brass/10 px-4 py-3 text-sm text-ink/75">
            {{ telegramMessage }}
          </p>
          <p v-if="error" class="mt-4 rounded-[18px] border border-clay/20 bg-clay/10 px-4 py-3 text-sm text-clay">
            {{ error }}
          </p>
        </article>

        <article class="panel p-8">
          <div class="flex items-center justify-between gap-3">
            <div>
              <p class="eyebrow">Onboarding</p>
              <h3 class="panel-title mt-2">Profile, preferences, and Telegram readiness</h3>
            </div>
            <button
              class="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="saving"
              @click="persistOnboarding"
            >
              Save setup
            </button>
          </div>

          <div class="mt-6 grid gap-4 sm:grid-cols-2">
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Full name</span>
              <input v-model="onboardingDraft.full_name" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Country</span>
              <select v-model="onboardingDraft.country" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none">
                <option value="US">United States</option>
                <option value="CA">Canada</option>
                <option value="IN">India</option>
                <option value="ANY">Any</option>
              </select>
            </label>
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Years of experience</span>
              <input v-model.number="onboardingDraft.years_of_experience" type="number" min="0" max="60" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">LinkedIn URL</span>
              <input v-model="onboardingDraft.linkedin_url" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Portfolio URL</span>
              <input v-model="onboardingDraft.portfolio_url" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">GitHub URL</span>
              <input v-model="onboardingDraft.github_url" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Resume uploaded</span>
              <select v-model="onboardingDraft.resume_uploaded" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none">
                <option :value="true">Yes</option>
                <option :value="false">Not yet</option>
              </select>
            </label>
          </div>

          <div class="mt-4 rounded-[24px] border border-ink/10 bg-smoke/45 p-5">
            <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p class="subtle-label">Telegram connection</p>
                <p class="mt-2 text-sm leading-6 text-ink/70">
                  Notifications stay private. Start the bot from your personal account, then verify the link here.
                </p>
                <p class="mt-3 text-sm font-semibold text-ink">
                  {{ currentUser.telegram_chat_id ? `Connected chat: ${currentUser.telegram_chat_id}` : "Not connected yet" }}
                </p>
              </div>
              <div class="flex flex-wrap gap-2">
                <button
                  class="rounded-full border border-ink/10 bg-white/80 px-4 py-2 text-sm font-semibold text-ink transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                  :disabled="saving"
                  @click="beginTelegramConnect"
                >
                  Start bot
                </button>
                <button
                  class="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-60"
                  :disabled="saving || !telegramConnectSession"
                  @click="verifyTelegramConnect"
                >
                  Verify Telegram
                </button>
              </div>
            </div>
            <div v-if="telegramConnectSession" class="mt-4 rounded-[18px] border border-ink/10 bg-white/80 p-4 text-sm text-ink/75">
              <p class="subtle-label">Bot link</p>
              <a
                :href="telegramConnectSession.connect_url"
                target="_blank"
                rel="noreferrer"
                class="mt-2 inline-flex text-sm font-semibold text-ink underline decoration-clay/50 underline-offset-4"
              >
                Open @{{ telegramConnectSession.bot_username }}
              </a>
              <p class="mt-2">
                Session expires in {{ Math.max(1, Math.round(telegramConnectSession.expires_in_seconds / 60)) }} minutes.
              </p>
            </div>
          </div>

          <div class="mt-4 grid gap-4">
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Locations</span>
              <textarea v-model="onboardingLocationsText" rows="2" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Preferred companies</span>
              <textarea v-model="onboardingCompaniesText" rows="2" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Preferred roles</span>
              <textarea v-model="onboardingRolesText" rows="2" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Skills</span>
              <textarea v-model="onboardingSkillsText" rows="2" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
            <label class="grid gap-2 text-sm text-ink/70">
              <span class="subtle-label">Watchlists</span>
              <textarea v-model="onboardingWatchlistsText" rows="2" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
            </label>
            <div class="grid gap-4 sm:grid-cols-2">
              <label class="grid gap-2 text-sm text-ink/70">
                <span class="subtle-label">Work arrangements</span>
                <textarea v-model="onboardingWorkArrangementsText" rows="2" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
              </label>
              <label class="grid gap-2 text-sm text-ink/70">
                <span class="subtle-label">Experience levels</span>
                <textarea v-model="onboardingExperienceLevelsText" rows="2" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
              </label>
            </div>
            <div class="grid gap-4 sm:grid-cols-2">
              <label class="grid gap-2 text-sm text-ink/70">
                <span class="subtle-label">Freshness (hours)</span>
                <input v-model.number="onboardingDraft.freshness_hours" type="number" min="1" max="168" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
              </label>
              <label class="grid gap-2 text-sm text-ink/70">
                <span class="subtle-label">Minimum match</span>
                <input v-model.number="onboardingDraft.minimum_match_score" type="number" min="0" max="100" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
              </label>
            </div>
          </div>
        </article>

        <article class="panel p-8 lg:col-span-2">
          <div class="grid gap-6 xl:grid-cols-2">
            <section>
              <p class="eyebrow">Latest Alerts</p>
              <h3 class="panel-title mt-2">Personalized Telegram-ready opportunities</h3>
              <div v-if="userAlerts.length" class="mt-6 space-y-4">
                <article
                  v-for="alert in userAlerts.slice(0, 5)"
                  :key="alert.id"
                  class="rounded-[22px] border border-ink/10 bg-white/80 p-4"
                >
                  <div class="flex flex-wrap items-center gap-3">
                    <p class="font-display text-xl font-semibold text-ink">{{ alert.company }}</p>
                    <span :class="['chip', recommendationClass(alert.recommendation_tone)]">{{ alert.recommendation }}</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-ink/85">{{ alert.title }}</p>
                  <p class="mt-2 text-sm text-ink/65">{{ alert.freshness_label }}</p>
                  <div class="mt-3 flex flex-wrap gap-2">
                    <span v-for="reason in alert.why" :key="`${alert.id}-${reason}`" class="chip">{{ reason }}</span>
                  </div>
                  <div class="mt-4 flex items-center justify-between gap-3">
                    <span class="text-sm font-semibold text-ink">{{ alert.match_score }}% match</span>
                    <a
                      :href="alert.apply_url"
                      target="_blank"
                      rel="noreferrer"
                      class="text-sm font-semibold text-ink underline decoration-clay/50 underline-offset-4"
                    >
                      Apply Now
                    </a>
                  </div>
                </article>
              </div>
              <div v-else class="mt-6 rounded-[22px] border border-dashed border-ink/15 bg-smoke/45 p-5 text-sm leading-6 text-ink/70">
                {{ currentUser.onboarding.progress_percent < 100
                  ? "Finish your setup and connect Telegram to start receiving personalized alerts."
                  : "No alerts yet. The system is monitoring your selected companies and will notify you when a new role clears your threshold." }}
              </div>
            </section>

            <section>
              <p class="eyebrow">Matched Jobs</p>
              <h3 class="panel-title mt-2">What currently fits your profile</h3>
              <div v-if="userJobs.length" class="mt-6 space-y-4">
                <article
                  v-for="job in userJobs.slice(0, 5)"
                  :key="job.id"
                  class="rounded-[22px] border border-ink/10 bg-white/80 p-4"
                >
                  <div class="flex flex-wrap items-center gap-3">
                    <p class="font-display text-xl font-semibold text-ink">{{ job.company }}</p>
                    <span :class="['chip', decisionClass(job.decision)]">{{ decisionLabel(job.decision) }}</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-ink/85">{{ job.title }}</p>
                  <p class="mt-1 text-sm text-ink/60">{{ job.location }} · {{ job.remote_policy }}</p>
                  <p class="mt-2 text-sm text-ink/65">{{ job.freshness_label }}</p>
                  <div class="mt-3 flex flex-wrap gap-2">
                    <span v-for="reason in job.why" :key="`${job.id}-${reason}`" class="chip">{{ reason }}</span>
                  </div>
                  <div class="mt-4 flex items-center justify-between gap-3">
                    <span class="text-sm font-semibold text-ink">{{ job.match_score }}% match</span>
                    <a
                      :href="job.apply_url"
                      target="_blank"
                      rel="noreferrer"
                      class="text-sm font-semibold text-ink underline decoration-clay/50 underline-offset-4"
                    >
                      Open Apply Page
                    </a>
                  </div>
                </article>
              </div>
              <div v-else class="mt-6 rounded-[22px] border border-dashed border-ink/15 bg-smoke/45 p-5 text-sm leading-6 text-ink/70">
                {{ currentUser.onboarding.progress_percent < 100
                  ? "No personalized matches yet. Add companies, roles, and locations so the matcher can start filtering jobs for you."
                  : "No current matches have cleared your filters yet. Try broadening companies, locations, or the minimum match threshold." }}
              </div>
            </section>
          </div>
        </article>
      </section>

      <section v-else-if="error" class="mt-8 panel p-8">
        <p class="panel-title">Backend unavailable</p>
        <p class="mt-3 text-sm leading-6 text-ink/70">
          The admin dashboard could not load its authenticated data. Start the FastAPI service, verify the JWT setup, or set `VITE_API_BASE_URL`.
        </p>
        <p class="mt-2 rounded-2xl bg-smoke/60 px-4 py-3 text-sm text-ink/75">{{ error }}</p>
      </section>

      <template v-else-if="snapshot">
        <section class="mt-8 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <article class="panel p-6">
            <div class="flex items-center justify-between gap-4">
              <div>
                <p class="eyebrow">System Status</p>
                <h3 class="panel-title mt-2">Local pipeline health at a glance</h3>
              </div>
              <span class="chip">Debug the failing component first</span>
            </div>

            <div class="mt-6 grid gap-3 sm:grid-cols-2">
              <article
                v-for="component in systemStatusComponents"
                :key="component.key"
                class="rounded-[20px] border border-ink/10 bg-white/80 p-4"
              >
                <div class="flex items-center justify-between gap-3">
                  <p class="font-semibold text-ink">{{ component.label }}</p>
                  <span
                    :class="[
                      'inline-flex h-8 w-8 items-center justify-center rounded-full border text-sm font-semibold',
                      systemStateClass(component.status),
                    ]"
                  >
                    {{ systemStateGlyph(component.status) }}
                  </span>
                </div>
                <p class="mt-3 text-sm leading-6 text-ink/70">{{ component.detail }}</p>
              </article>
            </div>
          </article>

          <article class="panel p-6">
            <div class="flex items-center justify-between gap-4">
              <div>
                <p class="eyebrow">Scheduler Pulse</p>
                <h3 class="panel-title mt-2">What moved, when, and what happens next</h3>
              </div>
              <span class="chip">5-minute local loop</span>
            </div>

            <div v-if="systemStatusStats" class="mt-6 grid gap-4 sm:grid-cols-2">
              <div class="rounded-[20px] border border-ink/10 bg-smoke/45 p-4">
                <p class="subtle-label">Jobs collected</p>
                <p class="mt-3 font-display text-3xl font-semibold text-ink">{{ systemStatusStats.jobs_collected }}</p>
              </div>
              <div class="rounded-[20px] border border-ink/10 bg-smoke/45 p-4">
                <p class="subtle-label">New today</p>
                <p class="mt-3 font-display text-3xl font-semibold text-clay">{{ systemStatusStats.new_today }}</p>
              </div>
              <div class="rounded-[20px] border border-ink/10 bg-smoke/45 p-4">
                <p class="subtle-label">Notifications sent</p>
                <p class="mt-3 font-display text-3xl font-semibold text-moss">{{ systemStatusStats.notifications_sent }}</p>
              </div>
              <div class="rounded-[20px] border border-ink/10 bg-smoke/45 p-4">
                <p class="subtle-label">Last poll</p>
                <p class="mt-3 font-display text-3xl font-semibold text-ink">{{ formatClock(systemStatusStats.last_poll_at) }}</p>
              </div>
              <div class="rounded-[20px] border border-ink/10 bg-smoke/45 p-4 sm:col-span-2">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <p class="subtle-label">Next poll</p>
                    <p class="mt-3 font-display text-3xl font-semibold text-brass">
                      {{ formatClock(systemStatusStats.next_poll_at) }}
                    </p>
                  </div>
                  <span :class="['chip', systemStateClass(snapshot.agent.state)]">
                    {{ snapshot.agent.state === "healthy" ? "Running" : snapshot.agent.state }}
                  </span>
                </div>
              </div>
            </div>
          </article>
        </section>

        <section class="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <StatCard
            v-for="card in summaryCards"
            :key="card.label"
            :label="card.label"
            :value="card.value"
            :detail="card.detail"
            :tone="card.tone"
          />
        </section>

        <section v-if="notificationPreview" class="mt-8">
          <article class="panel overflow-hidden">
            <div class="bg-gradient-to-r from-clay/15 via-transparent to-moss/15 p-7">
              <div class="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
                <div class="max-w-3xl">
                  <p class="eyebrow">Latest Telegram Alert</p>
                  <div class="mt-5 rounded-[24px] border border-ink/10 bg-white/80 p-5">
                    <div class="flex flex-wrap items-center gap-3">
                      <p class="font-display text-2xl font-semibold text-ink">New High-Match Job</p>
                      <span
                        :class="[
                          'rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]',
                          decisionClass(notificationPreview.decision),
                        ]"
                      >
                        {{ decisionLabel(notificationPreview.decision) }}
                      </span>
                    </div>
                    <div class="mt-4 grid gap-2 text-sm text-ink/80 sm:grid-cols-2">
                      <p><span class="subtle-label">Company</span><br />{{ notificationPreview.company }}</p>
                      <p><span class="subtle-label">Country</span><br />{{ notificationPreview.country_display }}</p>
                      <p><span class="subtle-label">Role</span><br />{{ notificationPreview.title }}</p>
                      <p><span class="subtle-label">Match</span><br />{{ notificationPreview.match_score }}%</p>
                      <p><span class="subtle-label">Freshness</span><br />{{ notificationPreview.freshness_label }}</p>
                      <p><span class="subtle-label">Recommendation</span><br />{{ notificationPreview.recommendation }}</p>
                      <p><span class="subtle-label">Resume</span><br />{{ notificationPreview.recommended_resume }}</p>
                      <p><span class="subtle-label">Channel</span><br />{{ channelLabel(notificationPreview.channel) }}</p>
                    </div>
                    <div class="mt-4 flex flex-wrap gap-2">
                      <span v-for="reason in notificationPreview.why" :key="reason" class="chip">{{ reason }}</span>
                    </div>
                    <div v-if="notificationPreview.gaps.length" class="mt-4 rounded-[18px] border border-brass/20 bg-brass/10 px-4 py-3 text-sm text-ink/75">
                      <p class="subtle-label">Missing</p>
                      <p class="mt-2">{{ notificationPreview.gaps.join(" • ") }}</p>
                    </div>
                  </div>
                </div>

                <div class="grid min-w-[250px] gap-3 rounded-[24px] border border-ink/10 bg-white/80 p-5">
                  <div class="flex items-center justify-between">
                    <span class="subtle-label">Sent</span>
                    <span class="text-sm font-semibold text-ink">{{ notificationPreview.sent_minutes_ago }} min ago</span>
                  </div>
                  <div class="flex items-center justify-between">
                    <span class="subtle-label">Recommendation</span>
                    <span :class="['chip', recommendationClass(notificationPreview.recommendation_tone)]">
                      {{ notificationPreview.recommendation }}
                    </span>
                  </div>
                  <div class="flex items-center justify-between">
                    <span class="subtle-label">Apply</span>
                    <a
                      :href="notificationPreview.apply_url"
                      target="_blank"
                      rel="noreferrer"
                      class="text-sm font-semibold text-ink underline decoration-clay/50 underline-offset-4"
                    >
                      Apply Now
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </section>

        <section class="mt-8 grid gap-6 xl:grid-cols-[1.45fr_0.95fr]">
          <article class="panel p-6">
            <div class="flex items-center justify-between gap-4">
              <div>
                <p class="eyebrow">Priority Queue</p>
                <h3 class="panel-title mt-2">Interrupt only for roles worth immediate action</h3>
              </div>
              <span class="chip">Lower-scoring jobs remain visible in the dashboard</span>
            </div>

            <div class="mt-6 grid gap-5">
              <section class="rounded-[24px] border border-clay/20 bg-clay/10 p-5">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <p class="subtle-label">Apply Now</p>
                    <p class="mt-2 font-display text-2xl font-semibold text-ink">
                      {{ snapshot.summary.apply_now_queue }} role<span v-if="snapshot.summary.apply_now_queue !== 1">s</span>
                    </p>
                  </div>
                  <span class="chip border-clay/20 bg-white/70 text-clay">
                    >= {{ snapshot.summary.apply_now_threshold_score }}%
                  </span>
                </div>
                <div class="mt-4 space-y-4">
                  <article
                    v-for="job in applyNowJobs"
                    :key="job.id"
                    class="rounded-[20px] border border-white/70 bg-white/80 p-4"
                  >
                    <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div class="min-w-0 flex-1">
                        <div class="flex flex-wrap items-center gap-3">
                          <p class="font-display text-xl font-semibold text-ink">{{ job.company }}</p>
                          <span class="chip border-clay/20 bg-clay/10 text-clay">{{ decisionLabel(job.decision) }}</span>
                          <span :class="['rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]', jobStatusClass(job.status)]">
                            {{ job.status }}
                          </span>
                        </div>
                        <p class="mt-2 text-base font-medium text-ink/90">{{ job.title }}</p>
                        <p class="mt-1 text-sm text-ink/60">
                          {{ job.source }} · {{ job.location }} · {{ job.remote_policy }} · {{ job.country_display }}
                        </p>
                        <p :class="['mt-3 inline-flex rounded-full border px-3 py-1 text-xs font-semibold', freshnessClass(job.freshness_tone)]">
                          {{ job.freshness_label }}
                        </p>
                        <p class="mt-3 text-sm leading-6 text-ink/70">{{ renderQueueReason(job) }}</p>
                        <p v-if="job.gaps.length" class="mt-2 text-sm leading-6 text-ink/55">Missing: {{ renderGapReason(job) }}</p>
                      </div>

                      <div class="grid min-w-[250px] gap-3 rounded-[20px] border border-ink/10 bg-smoke/45 p-4">
                        <div class="flex items-center justify-between">
                          <span class="subtle-label">Match</span>
                          <span class="font-display text-3xl font-semibold text-clay">{{ job.match_score }}%</span>
                        </div>
                        <div class="flex items-center justify-between">
                          <span class="subtle-label">Recommendation</span>
                          <span :class="['chip', recommendationClass(job.recommendation_tone)]">{{ job.recommendation }}</span>
                        </div>
                        <div class="flex items-center justify-between">
                          <span class="subtle-label">Resume</span>
                          <span class="text-sm font-semibold text-ink">{{ job.recommended_resume }}</span>
                        </div>
                        <a
                          :href="job.apply_url"
                          target="_blank"
                          rel="noreferrer"
                          class="inline-flex items-center justify-center rounded-full bg-ink px-4 py-3 text-sm font-semibold text-white transition hover:bg-ink/90"
                        >
                          Open apply page
                        </a>
                      </div>
                    </div>
                  </article>
                </div>
              </section>

              <div class="grid gap-5 lg:grid-cols-2">
                <section class="rounded-[24px] border border-brass/20 bg-brass/10 p-5">
                  <div class="flex items-center justify-between gap-3">
                    <div>
                      <p class="subtle-label">Review</p>
                      <p class="mt-2 font-display text-2xl font-semibold text-ink">{{ snapshot.summary.review_queue }} roles</p>
                    </div>
                    <span class="chip border-brass/20 bg-white/70 text-brass">
                      {{ snapshot.summary.review_threshold_score }}-{{ snapshot.summary.apply_now_threshold_score - 1 }}%
                    </span>
                  </div>
                  <div class="mt-4 space-y-3">
                    <article
                      v-for="job in reviewJobs"
                      :key="job.id"
                      class="rounded-[20px] border border-white/70 bg-white/80 p-4"
                    >
                      <div class="flex items-start justify-between gap-4">
                        <div class="min-w-0 flex-1">
                          <p class="font-semibold text-ink">{{ job.company }}</p>
                          <p class="mt-1 text-sm font-medium text-ink/80">{{ job.title }}</p>
                          <p class="mt-1 text-sm text-ink/60">{{ job.match_score }}% · {{ job.freshness_label }}</p>
                        </div>
                        <span :class="['rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]', jobStatusClass(job.status)]">
                          {{ job.status }}
                        </span>
                      </div>
                    </article>
                  </div>
                </section>

                <section class="rounded-[24px] border border-moss/20 bg-moss/10 p-5">
                  <div class="flex items-center justify-between gap-3">
                    <div>
                      <p class="subtle-label">Ignore</p>
                      <p class="mt-2 font-display text-2xl font-semibold text-ink">{{ snapshot.summary.ignore_queue }} roles</p>
                    </div>
                    <span class="chip border-moss/20 bg-white/70 text-moss">
                      &lt; {{ snapshot.summary.review_threshold_score }}%
                    </span>
                  </div>
                  <div class="mt-4 space-y-3">
                    <article
                      v-for="job in ignoreJobs"
                      :key="job.id"
                      class="rounded-[20px] border border-white/70 bg-white/80 p-4"
                    >
                      <div class="flex items-start justify-between gap-4">
                        <div class="min-w-0 flex-1">
                          <p class="font-semibold text-ink">{{ job.company }}</p>
                          <p class="mt-1 text-sm font-medium text-ink/80">{{ job.title }}</p>
                          <p class="mt-1 text-sm text-ink/60">{{ job.match_score }}% · {{ job.freshness_label }}</p>
                        </div>
                        <span :class="['rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]', jobStatusClass(job.status)]">
                          {{ job.status }}
                        </span>
                      </div>
                    </article>
                  </div>
                </section>
              </div>
            </div>
          </article>

          <div class="grid gap-6">
            <article class="panel p-6">
              <div class="flex items-center justify-between gap-4">
                <div>
                  <p class="eyebrow">Configuration</p>
                  <h3 class="panel-title mt-2">Watchlist and match scope</h3>
                </div>
                <span class="chip">{{ enabledCompanyCount }} companies · {{ enabledRoleCount }} roles · {{ enabledRoleFamilyCount }} families</span>
              </div>

              <div class="mt-6 grid gap-6">
                <section>
                  <p class="subtle-label">User preferences</p>
                  <div class="mt-3 grid gap-3 sm:grid-cols-2">
                    <div class="rounded-[18px] border border-ink/10 bg-white/75 px-4 py-3 text-sm text-ink/80">
                      <span class="subtle-label">Country</span>
                      <p class="mt-2 font-semibold text-ink">{{ countryLabel(snapshot.settings.selected_country) }}</p>
                    </div>
                    <div class="rounded-[18px] border border-ink/10 bg-white/75 px-4 py-3 text-sm text-ink/80">
                      <span class="subtle-label">Minimum match</span>
                      <p class="mt-2 font-semibold text-ink">{{ snapshot.settings.minimum_match_score }}%</p>
                    </div>
                    <div class="rounded-[18px] border border-ink/10 bg-white/75 px-4 py-3 text-sm text-ink/80">
                      <span class="subtle-label">Alert freshness</span>
                      <p class="mt-2 font-semibold text-ink">{{ snapshot.settings.alert_freshness_hours }} hours</p>
                    </div>
                    <div class="rounded-[18px] border border-ink/10 bg-white/75 px-4 py-3 text-sm text-ink/80">
                      <span class="subtle-label">Dashboard freshness</span>
                      <p class="mt-2 font-semibold text-ink">{{ snapshot.settings.dashboard_freshness_hours }} hours</p>
                    </div>
                  </div>
                </section>

                <section>
                  <p class="subtle-label">Role families</p>
                  <div class="mt-3 grid gap-2 sm:grid-cols-2">
                    <div
                      v-for="family in snapshot.settings.role_families"
                      :key="family.label"
                      class="rounded-[18px] border border-ink/10 bg-white/75 px-4 py-3 text-sm text-ink/80"
                    >
                      <span class="font-semibold">{{ toggleGlyph(family.enabled) }}</span>
                      <span class="ml-2">{{ family.label }}</span>
                    </div>
                  </div>
                </section>

                <section>
                  <p class="subtle-label">Companies</p>
                  <div class="mt-3 grid gap-2 sm:grid-cols-2">
                    <div
                      v-for="company in snapshot.settings.companies"
                      :key="company.company"
                      class="rounded-[18px] border border-ink/10 bg-white/75 px-4 py-3 text-sm text-ink/80"
                    >
                      <div class="flex items-start justify-between gap-3">
                        <div>
                          <span class="font-semibold">{{ toggleGlyph(company.enabled) }}</span>
                          <span class="ml-2">{{ company.company }}</span>
                        </div>
                        <span :class="['rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]', companyTierClass(company.tier)]">
                          {{ companyTierLabel(company.tier) }}
                        </span>
                      </div>
                      <p class="mt-2 text-xs text-ink/55">
                        {{ connectorLabel(company.connector) }} · Priority {{ company.priority }} · Every
                        {{ company.poll_interval_minutes }} min
                      </p>
                    </div>
                  </div>
                </section>

                <section>
                  <p class="subtle-label">Roles and keywords</p>
                  <div class="mt-3 grid gap-2 sm:grid-cols-2">
                    <div
                      v-for="role in snapshot.settings.roles"
                      :key="role.label"
                      class="rounded-[18px] border border-ink/10 bg-white/75 px-4 py-3 text-sm text-ink/80"
                    >
                      <span class="font-semibold">{{ toggleGlyph(role.enabled) }}</span>
                      <span class="ml-2">{{ role.label }}</span>
                    </div>
                  </div>
                </section>

                <section>
                  <p class="subtle-label">Work arrangements</p>
                  <div class="mt-3 grid gap-2 sm:grid-cols-3">
                    <div
                      v-for="arrangement in snapshot.settings.work_arrangements"
                      :key="arrangement.label"
                      class="rounded-[18px] border border-ink/10 bg-white/75 px-4 py-3 text-sm text-ink/80"
                    >
                      <span class="font-semibold">{{ toggleGlyph(arrangement.enabled) }}</span>
                      <span class="ml-2">{{ arrangement.label }}</span>
                    </div>
                  </div>
                </section>

                <section>
                  <p class="subtle-label">Experience levels</p>
                  <div class="mt-3 grid gap-2 sm:grid-cols-3">
                    <div
                      v-for="level in snapshot.settings.experience_levels"
                      :key="level.label"
                      class="rounded-[18px] border border-ink/10 bg-white/75 px-4 py-3 text-sm text-ink/80"
                    >
                      <span class="font-semibold">{{ toggleGlyph(level.enabled) }}</span>
                      <span class="ml-2">{{ level.label }}</span>
                    </div>
                  </div>
                </section>

                <section>
                  <p class="subtle-label">Excluded by default</p>
                  <div class="mt-3 flex flex-wrap gap-2">
                    <span v-for="keyword in snapshot.settings.excluded_keywords" :key="keyword" class="chip">
                      {{ keyword }}
                    </span>
                  </div>
                </section>

                <section>
                  <p class="subtle-label">Watchlists</p>
                  <div class="mt-3 space-y-3">
                    <article
                      v-for="watchlist in snapshot.settings.watchlists"
                      :key="watchlist.id"
                      class="rounded-[18px] border border-ink/10 bg-white/75 px-4 py-3 text-sm text-ink/80"
                    >
                      <div class="flex items-center justify-between gap-3">
                        <p class="font-semibold text-ink">{{ toggleGlyph(watchlist.enabled) }} {{ watchlist.name }}</p>
                        <span class="text-xs text-ink/50">{{ watchlist.terms.length }} terms</span>
                      </div>
                      <p class="mt-2 text-xs leading-6 text-ink/55">
                        {{ watchlist.terms.map((term) => term.company ? `${term.company} · ${term.term}` : term.term).join(" • ") }}
                      </p>
                    </article>
                  </div>
                </section>

                <section>
                  <p class="subtle-label">Notifications</p>
                  <div class="mt-3 space-y-3">
                    <div
                      v-for="channel in snapshot.settings.notifications"
                      :key="channel.channel"
                      class="rounded-[18px] border border-ink/10 bg-white/75 px-4 py-3"
                    >
                      <div class="flex items-center justify-between gap-3">
                        <p class="text-sm font-semibold text-ink">
                          {{ toggleGlyph(channel.enabled) }} {{ channelLabel(channel.channel) }}
                        </p>
                        <span class="text-xs text-ink/50">{{ channel.destination }}</span>
                      </div>
                    </div>
                  </div>
                </section>
              </div>
            </article>

            <article class="panel p-6">
              <div class="flex items-center justify-between gap-4">
                <div>
                  <p class="eyebrow">Control Plane</p>
                  <h3 class="panel-title mt-2">Manage companies, watchlists, and filters without redeploying</h3>
                </div>
                <span class="chip">{{ saving ? "Saving..." : "Postgres-backed catalog" }}</span>
              </div>

              <p v-if="saveMessage" class="mt-4 rounded-[18px] border border-moss/20 bg-moss/10 px-4 py-3 text-sm text-moss">
                {{ saveMessage }}
              </p>

              <div v-if="settingsDraft" class="mt-6 grid gap-6">
                <section class="rounded-[24px] border border-ink/10 bg-white/80 p-5">
                  <div class="flex items-center justify-between gap-3">
                    <div>
                      <p class="subtle-label">Preferences</p>
                      <p class="mt-2 text-sm text-ink/60">Thresholds, polling cadence, and matching scope now live in the database.</p>
                    </div>
                    <button
                      class="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="saving"
                      @click="persistPreferences"
                    >
                      Save preferences
                    </button>
                  </div>

                  <div class="mt-5 grid gap-4 sm:grid-cols-2">
                    <label class="grid gap-2 text-sm text-ink/70">
                      <span class="subtle-label">Primary connector</span>
                      <input v-model="settingsDraft.primary_connector" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
                    </label>
                    <label class="grid gap-2 text-sm text-ink/70">
                      <span class="subtle-label">Country</span>
                      <select v-model="settingsDraft.selected_country" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none">
                        <option value="US">United States</option>
                        <option value="CA">Canada</option>
                        <option value="IN">India</option>
                        <option value="ANY">Any</option>
                      </select>
                    </label>
                    <label class="grid gap-2 text-sm text-ink/70">
                      <span class="subtle-label">Minimum match</span>
                      <input v-model.number="settingsDraft.minimum_match_score" type="number" min="0" max="100" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
                    </label>
                    <label class="grid gap-2 text-sm text-ink/70">
                      <span class="subtle-label">Polling cadence (min)</span>
                      <input v-model.number="settingsDraft.polling_interval_minutes" type="number" min="1" max="1440" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
                    </label>
                    <label class="grid gap-2 text-sm text-ink/70">
                      <span class="subtle-label">Apply now threshold</span>
                      <input v-model.number="settingsDraft.apply_now_threshold_score" type="number" min="0" max="100" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
                    </label>
                    <label class="grid gap-2 text-sm text-ink/70">
                      <span class="subtle-label">Review threshold</span>
                      <input v-model.number="settingsDraft.review_threshold_score" type="number" min="0" max="100" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
                    </label>
                    <label class="grid gap-2 text-sm text-ink/70">
                      <span class="subtle-label">Alert freshness (hours)</span>
                      <input v-model.number="settingsDraft.alert_freshness_hours" type="number" min="1" max="168" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
                    </label>
                    <label class="grid gap-2 text-sm text-ink/70">
                      <span class="subtle-label">Dashboard freshness (hours)</span>
                      <input v-model.number="settingsDraft.dashboard_freshness_hours" type="number" min="1" max="720" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
                    </label>
                  </div>

                  <div class="mt-4 grid gap-4">
                    <label class="grid gap-2 text-sm text-ink/70">
                      <span class="subtle-label">Roles</span>
                      <textarea v-model="rolesText" rows="3" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
                    </label>
                    <label class="grid gap-2 text-sm text-ink/70">
                      <span class="subtle-label">Role families</span>
                      <textarea v-model="roleFamiliesText" rows="2" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
                    </label>
                    <div class="grid gap-4 sm:grid-cols-2">
                      <label class="grid gap-2 text-sm text-ink/70">
                        <span class="subtle-label">Work arrangements</span>
                        <textarea v-model="workArrangementsText" rows="2" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
                      </label>
                      <label class="grid gap-2 text-sm text-ink/70">
                        <span class="subtle-label">Experience levels</span>
                        <textarea v-model="experienceLevelsText" rows="2" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
                      </label>
                    </div>
                    <label class="grid gap-2 text-sm text-ink/70">
                      <span class="subtle-label">Excluded keywords</span>
                      <textarea v-model="excludedKeywordsText" rows="3" class="rounded-[16px] border border-ink/10 bg-smoke/45 px-4 py-3 text-ink outline-none" />
                    </label>
                  </div>
                </section>

                <section class="rounded-[24px] border border-ink/10 bg-white/80 p-5">
                  <div class="flex items-center justify-between gap-3">
                    <div>
                      <p class="subtle-label">Target companies</p>
                      <p class="mt-2 text-sm text-ink/60">Each company row stores connector choice, external source ID, cadence, and priority in Postgres.</p>
                    </div>
                    <span class="chip">{{ companyDrafts.length }} tracked</span>
                  </div>

                  <div class="mt-5 space-y-4">
                    <article
                      v-for="(company, index) in companyDrafts"
                      :key="company.id || company.company"
                      class="rounded-[20px] border border-ink/10 bg-smoke/45 p-4"
                    >
                      <div class="grid gap-4 sm:grid-cols-2">
                        <label class="grid gap-2 text-sm text-ink/70">
                          <span class="subtle-label">Company</span>
                          <input v-model="company.company" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none" />
                        </label>
                        <label class="grid gap-2 text-sm text-ink/70">
                          <span class="subtle-label">Connector</span>
                          <select v-model="company.connector" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none">
                            <option value="greenhouse">Greenhouse</option>
                            <option value="lever">Lever</option>
                            <option value="ashby">Ashby</option>
                            <option value="microsoft-careers">Microsoft Careers</option>
                            <option value="google-careers">Google Careers</option>
                            <option value="workday">Workday</option>
                            <option value="smartrecruiters">SmartRecruiters</option>
                            <option value="company-api">Company API</option>
                          </select>
                        </label>
                        <label class="grid gap-2 text-sm text-ink/70">
                          <span class="subtle-label">Priority</span>
                          <input v-model.number="company.priority" type="number" min="1" max="999" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none" />
                        </label>
                        <label class="grid gap-2 text-sm text-ink/70">
                          <span class="subtle-label">Tier</span>
                          <select v-model.number="company.tier" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none">
                            <option :value="1">Tier 1</option>
                            <option :value="2">Tier 2</option>
                            <option :value="3">Tier 3</option>
                          </select>
                        </label>
                        <label class="grid gap-2 text-sm text-ink/70">
                          <span class="subtle-label">Poll interval (min)</span>
                          <input v-model.number="company.poll_interval_minutes" type="number" min="1" max="1440" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none" />
                        </label>
                        <label class="grid gap-2 text-sm text-ink/70">
                          <span class="subtle-label">Country</span>
                          <select v-model="company.country" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none">
                            <option value="US">United States</option>
                            <option value="CA">Canada</option>
                            <option value="IN">India</option>
                            <option value="ANY">Any</option>
                          </select>
                        </label>
                        <label class="grid gap-2 text-sm text-ink/70">
                          <span class="subtle-label">Source identifier</span>
                          <input v-model="company.external_identifier" placeholder="Greenhouse board token or source id" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none" />
                        </label>
                        <label class="grid gap-2 text-sm text-ink/70">
                          <span class="subtle-label">Career URL</span>
                          <input v-model="company.career_url" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none" />
                        </label>
                      </div>
                      <label class="mt-4 grid gap-2 text-sm text-ink/70">
                        <span class="subtle-label">Role families</span>
                        <input
                          :value="company.role_families.join(', ')"
                          class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none"
                          @input="updateCompanyRoleFamilies(index, ($event.target as HTMLInputElement).value)"
                        />
                      </label>
                      <div class="mt-4 flex items-center justify-between gap-3">
                        <label class="inline-flex items-center gap-2 text-sm text-ink/70">
                          <input v-model="company.enabled" type="checkbox" class="h-4 w-4 rounded border-ink/20" />
                          Enabled
                        </label>
                        <button
                          class="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-60"
                          :disabled="saving"
                          @click="persistCompany(company)"
                        >
                          Save company
                        </button>
                      </div>
                    </article>
                  </div>

                  <div class="mt-5 rounded-[20px] border border-dashed border-ink/15 bg-white/70 p-4">
                    <p class="subtle-label">Add company</p>
                    <div class="mt-4 grid gap-4 sm:grid-cols-2">
                      <input v-model="newCompany.company" placeholder="Company name" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none" />
                      <select v-model="newCompany.connector" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none">
                        <option value="greenhouse">Greenhouse</option>
                        <option value="lever">Lever</option>
                        <option value="ashby">Ashby</option>
                        <option value="microsoft-careers">Microsoft Careers</option>
                        <option value="google-careers">Google Careers</option>
                        <option value="workday">Workday</option>
                        <option value="smartrecruiters">SmartRecruiters</option>
                        <option value="company-api">Company API</option>
                      </select>
                      <input v-model.number="newCompany.priority" type="number" min="1" max="999" placeholder="Priority" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none" />
                      <input v-model="newCompany.external_identifier" placeholder="Source identifier" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none" />
                    </div>
                    <button
                      class="mt-4 rounded-full bg-clay px-4 py-2 text-sm font-semibold text-white transition hover:bg-clay/90 disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="saving"
                      @click="addCompany"
                    >
                      Add company
                    </button>
                  </div>
                </section>

                <section class="rounded-[24px] border border-ink/10 bg-white/80 p-5">
                  <div class="flex items-center justify-between gap-3">
                    <div>
                      <p class="subtle-label">Watchlists</p>
                      <p class="mt-2 text-sm text-ink/60">One line per term. Use `Company | Team or keyword` when you want a company-specific watch target.</p>
                    </div>
                    <span class="chip">{{ watchlistDrafts.length }} active lists</span>
                  </div>

                  <div class="mt-5 space-y-4">
                    <article
                      v-for="(watchlist, index) in watchlistDrafts"
                      :key="watchlist.id || watchlist.name"
                      class="rounded-[20px] border border-ink/10 bg-smoke/45 p-4"
                    >
                      <div class="grid gap-4 sm:grid-cols-[1fr_auto]">
                        <input v-model="watchlist.name" class="rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none" />
                        <label class="inline-flex items-center gap-2 text-sm text-ink/70">
                          <input v-model="watchlist.enabled" type="checkbox" class="h-4 w-4 rounded border-ink/20" />
                          Enabled
                        </label>
                      </div>
                      <textarea
                        :value="watchlistTermsText(watchlist)"
                        rows="4"
                        class="mt-4 w-full rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none"
                        @input="updateWatchlistTerms(index, ($event.target as HTMLTextAreaElement).value)"
                      />
                      <div class="mt-4 flex justify-end">
                        <button
                          class="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-60"
                          :disabled="saving"
                          @click="persistWatchlist(watchlist)"
                        >
                          Save watchlist
                        </button>
                      </div>
                    </article>
                  </div>

                  <div class="mt-5 rounded-[20px] border border-dashed border-ink/15 bg-white/70 p-4">
                    <p class="subtle-label">Add watchlist</p>
                    <input v-model="newWatchlistName" placeholder="Watchlist name" class="mt-4 w-full rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none" />
                    <textarea
                      v-model="newWatchlistTerms"
                      rows="4"
                      placeholder="Microsoft | Azure AI&#10;Databricks | Serverless&#10;Copilot"
                      class="mt-4 w-full rounded-[16px] border border-ink/10 bg-white px-4 py-3 text-ink outline-none"
                    />
                    <button
                      class="mt-4 rounded-full bg-clay px-4 py-2 text-sm font-semibold text-white transition hover:bg-clay/90 disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="saving"
                      @click="addWatchlist"
                    >
                      Add watchlist
                    </button>
                  </div>
                </section>
              </div>
            </article>

            <article class="panel p-6">
              <div class="flex items-center justify-between gap-4">
                <div>
                  <p class="eyebrow">Connector Rollout</p>
                  <h3 class="panel-title mt-2">One live source, the rest staged behind it</h3>
                </div>
                <span class="chip">{{ snapshot.summary.live_connectors }} live · {{ snapshot.summary.next_connectors }} next</span>
              </div>

              <div class="mt-6 space-y-4">
                <article
                  v-for="source in snapshot.sources"
                  :key="source.id"
                  class="rounded-[22px] border border-ink/10 bg-white/80 p-4"
                >
                  <div class="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div class="flex flex-wrap items-center gap-2">
                        <p class="font-semibold text-ink">{{ source.source }}</p>
                        <span :class="['rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]', rolloutStageClass(source.rollout_stage)]">
                          {{ rolloutStageLabel(source.rollout_stage) }}
                        </span>
                        <span v-if="source.enabled" :class="['rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]', sourceStateClass(source.state)]">
                          {{ source.state }}
                        </span>
                      </div>
                      <p class="mt-1 text-sm text-ink/55">
                        Every {{ source.cadence_minutes }} min · {{ source.enabled ? `${source.new_jobs_today} new jobs today` : "Not enabled yet" }}
                      </p>
                    </div>
                    <span class="chip">{{ source.enabled ? "Enabled" : "Disabled" }}</span>
                  </div>

                  <div class="mt-4 grid gap-2 text-sm text-ink/65 sm:grid-cols-2">
                    <p>Last run: {{ formatLastRun(source) }}</p>
                    <p>Retries today: {{ source.retries_today }}</p>
                    <p class="sm:col-span-2">Last successful sync: {{ formatSync(source) }}</p>
                  </div>
                  <p v-if="source.lag_reason" class="mt-3 text-sm leading-6 text-ink/65">{{ source.lag_reason }}</p>
                </article>
              </div>
            </article>
          </div>
        </section>

        <section class="mt-8 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <article class="panel p-6">
            <div class="flex items-center justify-between gap-4">
              <div>
                <p class="eyebrow">Recent Alerts</p>
                <h3 class="panel-title mt-2">Only interrupt for apply-now roles</h3>
              </div>
              <span class="chip">{{ snapshot.alerts.length }} alerts sent</span>
            </div>

            <div class="mt-6 space-y-4">
              <article
                v-for="alert in snapshot.alerts"
                :key="alert.id"
                class="rounded-[22px] border border-ink/10 bg-white/80 p-4"
              >
                <div class="flex items-center justify-between gap-3">
                  <p class="font-semibold text-ink">{{ alert.company }}</p>
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="chip">{{ channelLabel(alert.channel) }}</span>
                    <span :class="['rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]', decisionClass(alert.decision)]">
                      {{ decisionLabel(alert.decision) }}
                    </span>
                  </div>
                </div>
                <p class="mt-2 text-sm font-medium text-ink/80">{{ alert.title }}</p>
                <p class="mt-1 text-sm text-ink/60">
                  {{ alert.country_display }} · Match {{ alert.match_score }}% · {{ alert.freshness_label }} · Sent
                  {{ alert.sent_minutes_ago }} min ago
                </p>
                <div class="mt-3 flex flex-wrap gap-2">
                  <span v-for="reason in alert.why" :key="reason" class="chip">{{ reason }}</span>
                </div>
                <div class="mt-3 flex flex-wrap gap-2">
                  <span :class="['chip', recommendationClass(alert.recommendation_tone)]">{{ alert.recommendation }}</span>
                </div>
                <p v-if="alert.gaps.length" class="mt-3 text-sm leading-6 text-ink/55">Missing: {{ alert.gaps.join(" • ") }}</p>
              </article>
            </div>
          </article>

          <article class="panel p-6">
            <div class="flex items-center justify-between gap-4">
              <div>
                <p class="eyebrow">Milestone Lock</p>
                <h3 class="panel-title mt-2">Stop expanding until this first path works</h3>
              </div>
              <span class="chip">Greenhouse -> Telegram -> Dashboard</span>
            </div>

            <div class="mt-6 grid gap-4">
              <div class="rounded-[22px] border border-clay/20 bg-clay/10 p-5">
                <p class="subtle-label">Definition of done</p>
                <p class="mt-3 text-sm leading-7 text-ink/75">
                  Scheduler every 5 minutes on localhost, jobs from one real source, PostgreSQL storage, dedupe
                  protection, Telegram delivery, live dashboard state, retry behavior, and component status reported
                  through `/health`.
                </p>
              </div>
              <div class="rounded-[22px] border border-brass/15 bg-brass/10 p-5">
                <p class="subtle-label">Deferred until stable</p>
                <div class="mt-3 flex flex-wrap gap-2">
                  <span class="chip">Resume tailoring</span>
                  <span class="chip">ATS scoring</span>
                  <span class="chip">Cover letters</span>
                  <span class="chip">Recruiter outreach</span>
                  <span class="chip">Application tracking</span>
                  <span class="chip">Interview prep</span>
                </div>
              </div>
            </div>
          </article>
        </section>
      </template>
    </div>
  </main>
</template>
