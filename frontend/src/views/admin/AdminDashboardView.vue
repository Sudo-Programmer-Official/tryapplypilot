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
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
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
  <AppPage>
    <PageHeader
      title="Admin dashboard"
      description="Watch the live pipeline, connector health, and notification output without leaving the operations workspace."
    >
      <template #actions>
        <AppButton :disabled="dashboard.runningNow.value" @click="handleRunNow">
          {{ dashboard.runningNow.value ? "Running..." : "Run Poll Now" }}
        </AppButton>
      </template>
    </PageHeader>

    <AppEmptyState v-if="dashboard.error.value" title="Dashboard unavailable" :description="dashboard.error.value" />

    <template v-else-if="dashboard.snapshot.value">
      <AppGrid as="section" columns="4">
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

      <AppGrid as="section" columns="2">
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

      <AppGrid as="section" columns="2">
        <SystemStatus :snapshot="dashboard.snapshot.value.system_status" />
        <AppCard title="Recent alerts" subtitle="The latest alert decisions the system sent downstream.">
          <ActivityList :items="alertItems" />
        </AppCard>
      </AppGrid>

      <ConnectorHealthTable :sources="dashboard.sources.value" />

      <AppCard title="Recent jobs" subtitle="Fresh jobs currently visible to the admin workspace.">
        <div class="app-stack app-stack--content">
          <JobRow
            v-for="job in dashboard.jobs.value.slice(0, 5)"
            :key="job.id"
            :job="job"
            :saved="isSavedJob(job.id)"
            @toggle-save="toggleSavedJob"
          />
        </div>
      </AppCard>
    </template>
  </AppPage>
</template>
