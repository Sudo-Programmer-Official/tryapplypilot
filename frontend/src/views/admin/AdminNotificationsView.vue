<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { fetchAdminAlerts, fetchAdminNotificationInsights } from "../../api/admin.api";
import ActivityList from "../../components/dashboard/ActivityList.vue";
import MetricCard from "../../components/dashboard/MetricCard.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppSkeleton from "../../components/ui/AppSkeleton.vue";
import AppTable from "../../components/ui/AppTable.vue";
import type { AlertEvent, NotificationInsights, TableColumn } from "../../types";
import {
  formatRelativeMinutes,
  notificationReasonLabel,
  notificationStatusTone,
  notificationTypeLabel,
} from "../../utils/format";

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
  <AppPage class="admin-notifications-page">
    <PageHeader title="Notifications" description="Review what the alert engine sent, where it went, and why delivery was retried, suppressed, or failed." />

    <PageSection v-if="loading && !error">
      <AppGrid columns="4">
        <AppCard v-for="index in 4" :key="index" class="admin-notifications-loading-card">
          <div class="admin-notifications-loading-card__stack">
            <AppSkeleton class="admin-notifications-loading-card__eyebrow" />
            <AppSkeleton class="admin-notifications-loading-card__value" />
            <AppSkeleton class="admin-notifications-loading-card__detail" />
          </div>
        </AppCard>
      </AppGrid>
    </PageSection>

    <PageSection v-else>
      <AppGrid columns="4">
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
    </PageSection>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Notifications unavailable" :description="error" />
      </AppGrid>
    </PageSection>

    <PageSection v-else>
      <AppGrid columns="2" class="admin-notifications-grid">
        <AppCard class="admin-notifications-panel" title="Latest activity" subtitle="Recent notification events and delivery decisions.">
          <AppEmptyState
            v-if="!loading && activityItems.length === 0"
            title="No notification history yet"
            description="Activity will appear once the scheduler records fresh, recovery, or failed delivery events."
          />
          <ActivityList v-else :items="activityItems" />
        </AppCard>

        <AppCard class="admin-notifications-panel" title="Reason analytics" :subtitle="loading ? 'Loading decision reasons...' : 'Why alerts were sent, suppressed, or retried.'">
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
    </PageSection>

    <PageSection v-if="!error">
      <AppGrid columns="2" class="admin-notifications-grid">
        <AppCard class="admin-notifications-panel" title="Notification paths" :subtitle="loading ? 'Loading notification types...' : 'Fresh, recovery, and digest-oriented delivery paths.'">
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

        <AppCard class="admin-notifications-panel" title="Notification history" :subtitle="loading ? 'Loading alerts...' : `${alerts.length} alerts loaded.`">
          <AppTable class="admin-notifications-table" :columns="columns" :has-rows="alerts.length > 0" empty-message="No alert history yet.">
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
    </PageSection>
  </AppPage>
</template>

<style scoped>
.admin-notifications-page {
  --page-gap: var(--space-5);
}

.admin-notifications-grid {
  align-items: stretch;
}

.admin-notifications-panel {
  min-height: 100%;
}

.admin-notifications-panel :deep(.app-card__header) {
  padding: clamp(var(--space-6), 3vw, 2.25rem) clamp(var(--space-6), 4vw, 2.5rem) 0;
}

.admin-notifications-panel :deep(.app-card__body) {
  align-content: start;
  gap: var(--space-6);
  padding: var(--space-6) clamp(var(--space-6), 4vw, 2.5rem) clamp(var(--space-6), 4vw, 2.25rem);
}

.admin-notifications-loading-card__stack {
  display: grid;
  gap: var(--space-2);
}

.admin-notifications-loading-card__eyebrow {
  max-width: 34%;
}

.admin-notifications-loading-card__value {
  min-height: 2.8rem;
  max-width: 48%;
}

.admin-notifications-loading-card__detail {
  min-height: 1rem;
}

.analytics-list {
  display: grid;
  gap: var(--space-4);
}

.analytics-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-5) var(--space-5) var(--space-6);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(246, 249, 253, 0.98));
  box-shadow: 0 14px 28px rgba(15, 29, 58, 0.05);
}
</style>
