<script setup lang="ts">
import { computed, onMounted } from "vue";

import ConnectorHealthTable from "../../components/admin/ConnectorHealthTable.vue";
import SystemStatus from "../../components/admin/SystemStatus.vue";
import ActivityList from "../../components/dashboard/ActivityList.vue";
import MetricCard from "../../components/dashboard/MetricCard.vue";
import StatusCard from "../../components/dashboard/StatusCard.vue";
import JobRow from "../../components/jobs/JobRow.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import { useDashboard } from "../../composables/useDashboard";
import { useJobs } from "../../composables/useJobs";
import type { MatchDecision } from "../../types";
import { extractJobTrend, formatRelativeMinutes } from "../../utils/format";

const dashboard = useDashboard();
const { toggleSavedJob, isSavedJob } = useJobs(dashboard.jobs);

const jobSparkline = computed(() => {
  const values = extractJobTrend(dashboard.jobs.value);
  const max = Math.max(...values, 1);
  return values.map((value) => Math.round((value / max) * 5));
});

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

onMounted(dashboard.load);
</script>

<template>
  <AppPage>
    <PageHeader
      title="Admin dashboard"
      description="Watch the live pipeline, connector health, and notification output without leaving the operations workspace."
    />

    <AppEmptyState v-if="dashboard.error.value" title="Dashboard unavailable" :description="dashboard.error.value" />

    <template v-else-if="dashboard.snapshot.value">
      <AppGrid as="section" columns="4">
        <MetricCard
          icon="BriefcaseBusiness"
          label="Jobs collected"
          :value="dashboard.snapshot.value.summary.todays_jobs"
          detail="Total jobs visible inside the active dashboard freshness window."
          tone="primary"
          :sparkline="jobSparkline"
        />
        <MetricCard
          icon="Bell"
          label="Apply now"
          :value="dashboard.snapshot.value.summary.apply_now_queue"
          detail="High-priority roles ready for immediate notification."
          tone="success"
        />
        <MetricCard
          icon="Users"
          label="Alerts sent"
          :value="dashboard.snapshot.value.summary.alerts_sent"
          detail="Notifications issued across the current dashboard window."
          tone="warning"
        />
        <MetricCard
          icon="Building2"
          label="Companies"
          :value="dashboard.snapshot.value.summary.configured_companies"
          detail="Catalog companies currently available to users and admins."
          tone="info"
        />
      </AppGrid>

      <AppGrid as="section" columns="2">
        <StatusCard
          title="Agent"
          :value="dashboard.snapshot.value.agent.name"
          :tone="dashboard.snapshot.value.agent.state === 'healthy' ? 'healthy' : dashboard.snapshot.value.agent.state === 'lagging' ? 'warning' : 'failed'"
          :detail="`Connector ${dashboard.snapshot.value.agent.current_connector} · next run in ${dashboard.snapshot.value.agent.next_run_minutes} min`"
        />
        <StatusCard
          title="Thresholds"
          :value="`${dashboard.snapshot.value.agent.apply_now_threshold_score}% / ${dashboard.snapshot.value.agent.review_threshold_score}%`"
          tone="info"
          :detail="`Polling every ${dashboard.snapshot.value.agent.polling_interval_minutes} minutes.`"
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
