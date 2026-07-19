<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import ActivityList from "../../components/dashboard/ActivityList.vue";
import MetricCard from "../../components/dashboard/MetricCard.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppTable from "../../components/ui/AppTable.vue";
import { fetchUserAlerts, fetchUserNotificationInsights } from "../../api/user.api";
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

const alertColumns: TableColumn[] = [
  { key: "job", label: "Job" },
  { key: "type", label: "Type" },
  { key: "status", label: "Status" },
  { key: "sent", label: "Sent" },
];

const missedColumns: TableColumn[] = [
  { key: "job", label: "Missed opportunity" },
  { key: "reason", label: "Reason" },
  { key: "type", label: "Path" },
  { key: "action", label: "Action" },
];

const activityItems = computed(() =>
  alerts.value.slice(0, 8).map((alert) => ({
    id: alert.id,
    title: `${alert.company} · ${alert.title}`,
    detail: `${notificationTypeLabel(alert.notification_type)} · ${notificationReasonLabel(alert.reason_code)}`,
    age: formatRelativeMinutes(alert.sent_minutes_ago),
    tone: (alert.alert_status === "failed" ? "warning" : "success") as "warning" | "success",
  })),
);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [alertsPayload, insightsPayload] = await Promise.all([fetchUserAlerts(), fetchUserNotificationInsights()]);
    alerts.value = alertsPayload.items;
    insights.value = insightsPayload;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load notification insights.";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppPage>
    <PageHeader
      title="Notifications"
      description="Understand what was delivered, what was suppressed, and which opportunities need recovery instead of guesswork."
    />

    <PageSection>
      <AppGrid columns="4">
        <MetricCard
          icon="Bell"
          label="Delivered"
          :value="insights?.totals.sent ?? 0"
          detail="Alerts that reached your configured channel."
          tone="success"
        />
        <MetricCard
          icon="Search"
          label="Missed"
          :value="insights?.totals.missed_opportunities ?? 0"
          detail="Matched jobs that did not result in a Telegram delivery."
          tone="warning"
        />
        <MetricCard
          icon="Settings"
          label="Suppressed"
          :value="insights?.totals.suppressed ?? 0"
          detail="Jobs intentionally held back by freshness, sync, or preference rules."
          tone="info"
        />
        <MetricCard
          icon="X"
          label="Failed"
          :value="insights?.totals.failed ?? 0"
          detail="Delivery attempts that hit a transport or runtime error."
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
      <AppGrid columns="2">
        <AppCard title="Recent delivery activity" subtitle="Fresh alerts, recovery alerts, and failures from your recent notification history.">
          <AppEmptyState
            v-if="!loading && activityItems.length === 0"
            title="No delivery history yet"
            description="Once a role qualifies for delivery, it will appear here with the alert type and decision reason."
          />
          <ActivityList v-else :items="activityItems" />
        </AppCard>

        <AppCard title="Reason distribution" :subtitle="loading ? 'Loading reasons...' : 'Why delivery was sent, suppressed, or retried.'">
          <AppEmptyState
            v-if="!loading && !(insights?.reasons.length)"
            title="No decision reasons yet"
            description="Reason analytics will appear after the scheduler evaluates jobs for your account."
          />
          <div v-else class="reason-list">
            <div v-for="reason in insights?.reasons ?? []" :key="reason.key" class="reason-row">
              <span>{{ notificationReasonLabel(reason.key) }}</span>
              <AppBadge tone="neutral">{{ reason.count }}</AppBadge>
            </div>
          </div>
        </AppCard>
      </AppGrid>
    </PageSection>

    <PageSection v-if="!error">
      <AppGrid columns="2">
        <AppCard title="Missed opportunities" subtitle="Jobs that matched you but did not generate a delivery event.">
          <AppTable :columns="missedColumns" :has-rows="(insights?.missed_jobs.length ?? 0) > 0" empty-message="No missed opportunities currently tracked.">
            <tr v-for="job in insights?.missed_jobs ?? []" :key="job.id">
              <td class="app-table__copy">
                <strong>{{ job.company }}</strong>
                <p>{{ job.title }}</p>
                <small>{{ job.freshness_label }} · {{ job.match_score }}%</small>
              </td>
              <td>
                <AppBadge :tone="notificationStatusTone(job.notification_status)">
                  {{ notificationReasonLabel(job.notification_reason) }}
                </AppBadge>
              </td>
              <td>{{ notificationTypeLabel(job.notification_type) }}</td>
              <td>
                <AppButton :href="job.apply_url" target="_blank" rel="noreferrer">Open job</AppButton>
              </td>
            </tr>
          </AppTable>
        </AppCard>

        <AppCard title="Alert history" :subtitle="loading ? 'Loading alerts...' : `${alerts.length} notification events loaded.`">
          <AppTable :columns="alertColumns" :has-rows="alerts.length > 0" empty-message="No alert history yet.">
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
.reason-list {
  display: grid;
  gap: var(--space-3);
}

.reason-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3) 0;
  border-bottom: 1px solid rgba(15, 29, 58, 0.08);
}

.reason-row:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.app-table__copy small {
  display: block;
  margin-top: var(--space-1);
  color: var(--color-text-muted);
}
</style>
