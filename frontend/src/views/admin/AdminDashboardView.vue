<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from "vue";

import ConnectorHealthTable from "../../components/admin/ConnectorHealthTable.vue";
import SystemStatus from "../../components/admin/SystemStatus.vue";
import ActivityList from "../../components/dashboard/ActivityList.vue";
import MetricCard from "../../components/dashboard/MetricCard.vue";
import StatusCard from "../../components/dashboard/StatusCard.vue";
import JobRow from "../../components/jobs/JobRow.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppSkeleton from "../../components/ui/AppSkeleton.vue";
import { useDashboard } from "../../composables/useDashboard";
import { useJobs } from "../../composables/useJobs";
import { useToast } from "../../composables/useToast";
import type { MatchDecision } from "../../types";
import { extractJobTrend, formatDateTime, formatRelativeMinutes } from "../../utils/format";

const dashboard = useDashboard();
const { pushToast } = useToast();
const { toggleSavedJob, isSavedJob } = useJobs(dashboard.jobs);
let refreshHandle: number | null = null;

const jobSparkline = computed(() => {
  const values = extractJobTrend(dashboard.jobs.value);
  const max = Math.max(...values, 1);
  return values.map((value) => Math.round((value / max) * 5));
});

const scheduler = computed(() => dashboard.effectiveScheduler.value);
const recentJobs = computed(() => dashboard.jobs.value.slice(0, 5));

function activityTone(decision: MatchDecision): "success" | "warning" | "info" {
  if (decision === "APPLY_NOW") {
    return "success";
  }
  if (decision === "REVIEW") {
    return "warning";
  }
  return "info";
}

const alertItems = computed(() =>
  dashboard.alerts.value.slice(0, 6).map((alert) => ({
    id: alert.id,
    title: `${alert.company} · ${alert.title}`,
    detail: `${alert.match_score}% match · ${alert.recommendation}`,
    age: formatRelativeMinutes(alert.sent_minutes_ago),
    tone: activityTone(alert.decision),
  })),
);

async function handleRunNow(): Promise<void> {
  try {
    await dashboard.triggerRunNow();
    pushToast("Scheduler started", "A poll cycle is running now and the dashboard has been refreshed.", "success");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to trigger the scheduler.";
    pushToast("Run now failed", message, "error");
  }
}

onMounted(async () => {
  await dashboard.load();
  refreshHandle = window.setInterval(() => {
    void dashboard.load();
  }, 30_000);
});

onBeforeUnmount(() => {
  if (refreshHandle !== null) {
    window.clearInterval(refreshHandle);
    refreshHandle = null;
  }
});
</script>

<template>
  <AppPage class="admin-dashboard-page">
    <PageHeader
      title="Admin dashboard"
      description="Watch the live pipeline, connector health, and notification output without leaving the operations workspace."
    >
      <template #actions>
        <div class="admin-dashboard-actions">
          <AppBadge :tone="dashboard.loading.value ? 'info' : 'neutral'">
            {{ dashboard.loading.value ? "Refreshing" : "Auto-refresh 30s" }}
          </AppBadge>
          <AppButton :disabled="dashboard.runningNow.value" @click="handleRunNow">
            {{ dashboard.runningNow.value ? "Running..." : "Run Poll Now" }}
          </AppButton>
        </div>
      </template>
    </PageHeader>

    <PageSection v-if="dashboard.error.value">
      <AppGrid columns="1">
        <AppEmptyState title="Dashboard unavailable" :description="dashboard.error.value" />
      </AppGrid>
    </PageSection>

    <PageSection v-else-if="dashboard.loading.value && !dashboard.snapshot.value">
      <AppGrid columns="4">
        <AppCard v-for="index in 4" :key="index" class="admin-dashboard-loading-card">
          <div class="admin-dashboard-loading-card__stack">
            <AppSkeleton class="admin-dashboard-loading-card__eyebrow" />
            <AppSkeleton class="admin-dashboard-loading-card__value" />
            <AppSkeleton class="admin-dashboard-loading-card__detail" />
          </div>
        </AppCard>
      </AppGrid>
      <AppGrid columns="2">
        <AppCard class="admin-dashboard-loading-card" title="Loading system status">
          <div class="admin-dashboard-loading-card__stack">
            <AppSkeleton v-for="index in 4" :key="`status-${index}`" class="admin-dashboard-loading-card__line" />
          </div>
        </AppCard>
        <AppCard class="admin-dashboard-loading-card" title="Loading recent jobs">
          <div class="admin-dashboard-loading-card__stack">
            <AppSkeleton v-for="index in 4" :key="`jobs-${index}`" class="admin-dashboard-loading-card__line" />
          </div>
        </AppCard>
      </AppGrid>
    </PageSection>

    <template v-else-if="dashboard.snapshot.value">
      <PageSection class="admin-dashboard-page__summary-section">
        <div class="admin-dashboard-summary surface-card">
          <div class="admin-dashboard-summary__item">
            <strong>{{ formatDateTime(dashboard.snapshot.value.generated_at) }}</strong>
            <span>last snapshot</span>
          </div>
          <div class="admin-dashboard-summary__item">
            <strong>{{ scheduler?.current_connector ?? "Waiting" }}</strong>
            <span>active connector</span>
          </div>
          <div class="admin-dashboard-summary__item">
            <strong>{{ recentJobs.length }}</strong>
            <span>recent jobs rendered</span>
          </div>
        </div>
      </PageSection>

      <PageSection>
        <AppGrid columns="4">
          <MetricCard
            icon="BriefcaseBusiness"
            label="Jobs collected"
            :value="scheduler?.jobs_collected ?? 0"
            detail="Collected during the last completed poll cycle."
            tone="primary"
            :sparkline="jobSparkline"
          />
          <MetricCard
            icon="Users"
            label="Jobs matched"
            :value="scheduler?.jobs_matched ?? 0"
            detail="User-specific matches scored in the latest cycle."
            tone="success"
          />
          <MetricCard
            icon="Bell"
            label="Telegram sent"
            :value="scheduler?.notifications_sent ?? 0"
            detail="Private alerts delivered in the latest cycle."
            tone="warning"
          />
          <MetricCard
            icon="Building2"
            label="Errors"
            :value="scheduler?.errors ?? 0"
            detail="Connector and delivery errors recorded in the latest cycle."
            tone="info"
          />
        </AppGrid>
      </PageSection>

      <PageSection>
        <AppGrid columns="2">
          <StatusCard
            title="Scheduler"
            :value="scheduler?.running ? 'Running' : 'Stopped'"
            :tone="dashboard.snapshot.value.agent.state === 'healthy' ? 'healthy' : dashboard.snapshot.value.agent.state === 'lagging' ? 'warning' : 'failed'"
            :detail="`Last poll ${formatDateTime(scheduler?.last_run)} · next poll ${formatDateTime(scheduler?.next_run)}`"
          />
          <StatusCard
            title="Connector"
            :value="scheduler?.current_connector ?? dashboard.snapshot.value.agent.current_connector"
            tone="info"
            :detail="`Polling every ${dashboard.snapshot.value.agent.polling_interval_minutes} minutes · ${scheduler?.last_duration_seconds ? `${scheduler.last_duration_seconds.toFixed(1)} sec last cycle` : 'waiting for first completed cycle'}`"
          />
        </AppGrid>
      </PageSection>

      <PageSection>
        <AppGrid columns="2">
          <SystemStatus :snapshot="dashboard.snapshot.value.system_status" />
          <AppCard title="Recent alerts" subtitle="The latest alert decisions the system sent downstream.">
            <ActivityList :items="alertItems" />
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection>
        <AppGrid columns="1">
          <ConnectorHealthTable :sources="dashboard.sources.value" />
        </AppGrid>
      </PageSection>

      <PageSection>
        <AppGrid columns="1">
          <AppCard title="Recent jobs" subtitle="Only the freshest rows are rendered here so the dashboard stays fast as inventory grows.">
            <div class="app-stack app-stack--content">
              <JobRow
                v-for="job in recentJobs"
                :key="job.id"
                :job="job"
                :saved="isSavedJob(job.id)"
                @toggle-save="toggleSavedJob"
              />
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>
    </template>
  </AppPage>
</template>

<style scoped>
.admin-dashboard-page {
  --page-gap: var(--space-5);
}

.admin-dashboard-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
}

.admin-dashboard-page__summary-section {
  margin-bottom: calc(var(--space-2) * -1);
}

.admin-dashboard-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
  padding: clamp(var(--space-4), 2vw, var(--space-5));
}

.admin-dashboard-summary__item,
.admin-dashboard-loading-card__stack {
  display: grid;
  gap: var(--space-2);
}

.admin-dashboard-summary__item strong {
  font-family: var(--font-display);
  font-size: clamp(1.2rem, 1.8vw, 1.45rem);
  letter-spacing: -0.03em;
}

.admin-dashboard-summary__item span {
  color: var(--color-text-muted);
  font-size: 0.92rem;
}

.admin-dashboard-loading-card__eyebrow {
  max-width: 38%;
}

.admin-dashboard-loading-card__value {
  min-height: 2.8rem;
  max-width: 52%;
}

.admin-dashboard-loading-card__detail,
.admin-dashboard-loading-card__line {
  min-height: 1rem;
}

@media (max-width: 1023px) {
  .admin-dashboard-summary {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .admin-dashboard-actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
