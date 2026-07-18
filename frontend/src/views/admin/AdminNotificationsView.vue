<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import ActivityList from "../../components/dashboard/ActivityList.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppTable from "../../components/ui/AppTable.vue";
import { fetchAdminAlerts } from "../../api/admin.api";
import type { AlertEvent, TableColumn } from "../../types";
import { formatRelativeMinutes } from "../../utils/format";

const alerts = ref<AlertEvent[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const columns: TableColumn[] = [
  { key: "job", label: "Job" },
  { key: "decision", label: "Decision" },
  { key: "channel", label: "Channel" },
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
    detail: `${alert.match_score}% match · ${alert.channel}`,
    age: formatRelativeMinutes(alert.sent_minutes_ago),
    tone: alertTone(alert.decision),
  })),
);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const payload = await fetchAdminAlerts();
    alerts.value = payload.items;
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

    <AppGrid v-else as="section" columns="2">
      <AppCard title="Latest activity" subtitle="Recent notification events and delivery decisions.">
        <ActivityList :items="activityItems" />
      </AppCard>

      <AppCard title="Notification history" :subtitle="loading ? 'Loading alerts...' : `${alerts.length} alerts loaded.`">
        <AppTable :columns="columns" :has-rows="alerts.length > 0" empty-message="No alert history yet.">
          <tr v-for="alert in alerts" :key="alert.id">
            <td class="app-table__copy">
              <strong>{{ alert.company }}</strong>
              <p>{{ alert.title }}</p>
            </td>
            <td>{{ alert.recommendation }}</td>
            <td>{{ alert.channel }}</td>
            <td>{{ formatRelativeMinutes(alert.sent_minutes_ago) }}</td>
          </tr>
        </AppTable>
      </AppCard>
    </AppGrid>
  </AppPage>
</template>
