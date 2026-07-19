<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import ActivityList from "../../components/dashboard/ActivityList.vue";
import MetricCard from "../../components/dashboard/MetricCard.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppTable from "../../components/ui/AppTable.vue";
import { fetchAdminAlerts, fetchAdminNotificationInsights } from "../../api/admin.api";
import type { AlertEvent, NotificationInsights, TableColumn } from "../../types";
import { formatRelativeMinutes, notificationReasonLabel, notificationStatusTone, notificationTypeLabel } from "../../utils/format";

const alerts = ref<AlertEvent[]>([]);
const insights = ref<NotificationInsights | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);

const columns: TableColumn[] = [
  { key: "job", label: "Job" },
  { key: "type", label: "Type" },
  { key: "status", label: "Status" },
  { key: "sent", label: "Sent" },
];

function alertTone(decision: AlertEvent["decision"]): "success" | "warning" | "info" {
  if (decision === "APPLY_NOW") {
    return "success";
  }
  if (decision === "REVIEW") {
    return "warning";
  }
  return "info";
}

const activityItems = computed(() =>
  alerts.value.slice(0, 8).map((alert) => ({
    id: alert.id,
    title: `${alert.company} · ${alert.title}`,
    detail: `${alert.match_score}% match · ${notificationTypeLabel(alert.notification_type)} · ${notificationReasonLabel(alert.reason_code)}`,
    age: formatRelativeMinutes(alert.sent_minutes_ago),
    tone: alert.alert_status === "failed" ? "warning" : alertTone(alert.decision),
  })),
);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [alertsPayload, insightsPayload] = await Promise.all([fetchAdminAlerts(), fetchAdminNotificationInsights()]);
    alerts.value = alertsPayload.items;
    insights.value = insightsPayload;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load alerts.";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppPage>
    <PageHeader title="Notifications" description="Review what the alert engine sent, where it went, and how urgent each decision was." />

    <AppEmptyState v-if="error" title="Notifications unavailable" :description="error" />

    <AppGrid v-else as="section" columns="4">
      <MetricCard
        icon="Bell"
        label="Delivered"
        :value="insights?.totals.sent ?? 0"
        detail="Notification events that made it through the delivery channel."
        tone="success"
      />
      <MetricCard
        icon="Search"
        label="Missed"
        :value="insights?.totals.missed_opportunities ?? 0"
        detail="Matched jobs still missing a user-facing delivery outcome."
        tone="warning"
      />
      <MetricCard
        icon="Settings"
        label="Suppressed"
        :value="insights?.totals.suppressed ?? 0"
        detail="Evaluations blocked by freshness, rules, or initial-sync policies."
        tone="info"
      />
      <MetricCard
        icon="X"
        label="Failed"
        :value="insights?.totals.failed ?? 0"
        detail="Delivery attempts that need transport or runtime attention."
        tone="warning"
      />
    </AppGrid>

    <AppGrid v-if="!error" as="section" columns="2">
      <AppCard title="Latest activity" subtitle="Recent notification events and delivery decisions.">
        <ActivityList :items="activityItems" />
      </AppCard>

      <AppCard title="Reason analytics" :subtitle="loading ? 'Loading decision reasons...' : 'Why alerts were sent, suppressed, or retried.'">
        <AppEmptyState
          v-if="!loading && !(insights?.reasons.length)"
          title="No analytics yet"
          description="Reason-level analytics will appear after the scheduler evaluates notification decisions."
        />
        <div v-else class="analytics-list">
          <div v-for="reason in insights?.reasons ?? []" :key="reason.key" class="analytics-row">
            <span>{{ notificationReasonLabel(reason.key) }}</span>
            <AppBadge tone="neutral">{{ reason.count }}</AppBadge>
          </div>
        </div>
      </AppCard>
    </AppGrid>

    <AppGrid v-if="!error" as="section" columns="2">
      <AppCard title="Notification paths" :subtitle="loading ? 'Loading notification types...' : 'Fresh, recovery, and digest-oriented delivery paths.'">
        <AppEmptyState
          v-if="!loading && !(insights?.types.length)"
          title="No type analytics yet"
          description="Notification path analytics will appear as the scheduler records decisions."
        />
        <div v-else class="analytics-list">
          <div v-for="entry in insights?.types ?? []" :key="entry.key" class="analytics-row">
            <span>{{ notificationTypeLabel(entry.key) }}</span>
            <AppBadge tone="neutral">{{ entry.count }}</AppBadge>
          </div>
        </div>
      </AppCard>

      <AppCard title="Notification history" :subtitle="loading ? 'Loading alerts...' : `${alerts.length} alerts loaded.`">
        <AppTable :columns="columns" :has-rows="alerts.length > 0" empty-message="No alert history yet.">
          <tr v-for="alert in alerts" :key="alert.id">
            <td class="app-table__copy">
              <strong>{{ alert.company }}</strong>
              <p>{{ alert.title }}</p>
            </td>
            <td>{{ notificationTypeLabel(alert.notification_type) }}</td>
            <td>
              <AppBadge :tone="notificationStatusTone(alert.alert_status)">
                {{ notificationReasonLabel(alert.reason_code) }}
              </AppBadge>
            </td>
            <td>{{ formatRelativeMinutes(alert.sent_minutes_ago) }}</td>
          </tr>
        </AppTable>
      </AppCard>
    </AppGrid>
  </AppPage>
</template>

<style scoped>
.analytics-list {
  display: grid;
  gap: var(--space-3);
}

.analytics-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3) 0;
  border-bottom: 1px solid rgba(15, 29, 58, 0.08);
}

.analytics-row:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}
</style>
