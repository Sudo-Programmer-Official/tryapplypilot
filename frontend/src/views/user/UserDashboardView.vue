<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import SetupProgress from "../../components/dashboard/SetupProgress.vue";
import ActivityList from "../../components/dashboard/ActivityList.vue";
import MetricCard from "../../components/dashboard/MetricCard.vue";
import StatusCard from "../../components/dashboard/StatusCard.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import JobCard from "../../components/jobs/JobCard.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import { fetchUserAlerts, fetchUserJobs } from "../../api/user.api";
import { useAuth } from "../../composables/useAuth";
import { useJobs } from "../../composables/useJobs";
import type { AlertEvent, JobOpportunity } from "../../types";
import { extractJobTrend, formatRelativeMinutes, sortJobsByScore } from "../../utils/format";

const auth = useAuth();

const jobs = ref<JobOpportunity[]>([]);
const alerts = ref<AlertEvent[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const { savedJobs, toggleSavedJob, isSavedJob } = useJobs(jobs);

const topJobs = computed(() => sortJobsByScore(jobs.value).slice(0, 3));
const applyNowCount = computed(() => jobs.value.filter((job) => job.decision === "APPLY_NOW").length);
const reviewCount = computed(() => jobs.value.filter((job) => job.decision === "REVIEW").length);
const sparkline = computed(() => {
  const values = extractJobTrend(jobs.value);
  const max = Math.max(...values, 1);
  return values.map((value) => Math.round((value / max) * 5));
});

function activityTone(decision: string): "success" | "warning" | "info" {
  if (decision === "APPLY_NOW") {
    return "success";
  }
  if (decision === "REVIEW") {
    return "warning";
  }
  return "info";
}

const activityItems = computed(() =>
  alerts.value.slice(0, 5).map((alert) => ({
    id: alert.id,
    title: `${alert.company} · ${alert.title}`,
    detail: `${alert.match_score}% match · ${alert.recommendation}`,
    age: formatRelativeMinutes(alert.sent_minutes_ago),
    tone: activityTone(alert.decision),
  })),
);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [jobsPayload, alertsPayload] = await Promise.all([fetchUserJobs(), fetchUserAlerts()]);
    jobs.value = jobsPayload.items;
    alerts.value = alertsPayload.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load your dashboard.";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppPage class="dashboard-page">
    <PageHeader
      title="Your job radar"
      description="See what landed today, what deserves action now, and whether your alert pipeline is fully configured."
    />

    <AppGrid as="section" columns="4" class="dashboard-metrics">
      <MetricCard
        icon="BriefcaseBusiness"
        label="New jobs"
        :value="jobs.length"
        detail="Personalized opportunities available in your feed."
        tone="primary"
        :sparkline="sparkline"
      />
      <MetricCard
        icon="Bell"
        label="Apply now"
        :value="applyNowCount"
        detail="High-match jobs that crossed your current threshold."
        tone="success"
      />
      <MetricCard
        icon="Search"
        label="Review queue"
        :value="reviewCount"
        detail="Roles worth checking without interrupting you."
        tone="warning"
      />
      <MetricCard
        icon="Send"
        label="Saved jobs"
        :value="savedJobs.length"
        detail="Bookmarks synced to your account for your next pass."
        tone="info"
      />
    </AppGrid>

    <AppGrid as="section" columns="2" class="dashboard-overview">
      <SetupProgress
        :progress="auth.user.value?.onboarding.progress_percent ?? 0"
        :steps="auth.user.value?.onboarding.steps ?? []"
      />
      <AppGrid columns="2" gap="content" class="dashboard-status-grid">
        <StatusCard
          title="Telegram"
          :value="auth.user.value?.telegram_chat_id ? 'Connected' : 'Pending'"
          :tone="auth.user.value?.telegram_chat_id ? 'healthy' : 'warning'"
          :detail="auth.user.value?.telegram_chat_id ? 'Private alerts are enabled.' : 'Connect Telegram from Profile to receive notifications.'"
        />
        <StatusCard
          title="Preferences"
          :value="`${auth.user.value?.preferences.minimum_match_score ?? 90}% min match`"
          tone="info"
          :detail="`${auth.user.value?.preferences.country ?? auth.user.value?.country ?? 'US'} · ${auth.user.value?.preferences.freshness_hours ?? 6} hour freshness window`"
        />
      </AppGrid>
    </AppGrid>

    <AppGrid as="section" columns="2" class="dashboard-feed">
      <AppCard
        class="dashboard-panel"
        title="Top opportunities"
        subtitle="The highest scoring jobs currently in your personalized queue."
      >
        <AppEmptyState
          v-if="!loading && topJobs.length === 0"
          class="dashboard-empty"
          title="No jobs yet"
          description="Finish onboarding and wait for the next poll cycle to fill your dashboard."
        />
        <div v-else class="job-card-grid">
          <JobCard
            v-for="job in topJobs"
            :key="job.id"
            :job="job"
            :saved="isSavedJob(job.id)"
            @toggle-save="toggleSavedJob"
          />
        </div>
      </AppCard>

      <AppCard
        class="dashboard-panel"
        title="Latest alerts"
        subtitle="Recent notifications that were sent to your configured channels."
      >
        <AppEmptyState
          v-if="!loading && activityItems.length === 0"
          class="dashboard-empty"
          title="No alerts sent yet"
          description="Once a new high-match job lands, it will show up here and in Telegram."
        />
        <ActivityList v-else :items="activityItems" />
      </AppCard>
    </AppGrid>

    <AppEmptyState
      v-if="error"
      title="Dashboard unavailable"
      :description="error"
    />
  </AppPage>
</template>

<style scoped>
.dashboard-page {
  --page-gap: 28px;
}

.dashboard-metrics,
.dashboard-overview,
.dashboard-feed {
  align-items: stretch;
}

.dashboard-status-grid {
  height: 100%;
}

.dashboard-panel {
  min-height: 100%;
}

.dashboard-panel :deep(.app-card__body) {
  align-content: start;
}

.job-card-grid {
  display: grid;
  gap: var(--card-gap);
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.dashboard-empty {
  min-height: 18rem;
  border-style: dashed;
  box-shadow: none;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.95));
}

@media (max-width: 1023px) {
  .dashboard-status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
