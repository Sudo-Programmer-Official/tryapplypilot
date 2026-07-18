<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import ActivityList from "../../components/dashboard/ActivityList.vue";
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
  <div class="page-stack">
    <PageHeader title="Notifications" description="Review what the alert engine sent, where it went, and how urgent each decision was." />

    <AppEmptyState v-if="error" title="Notifications unavailable" :description="error" />

    <section v-else class="content-grid">
      <AppCard title="Latest activity" subtitle="Recent notification events and delivery decisions.">
        <ActivityList :items="activityItems" />
      </AppCard>

      <AppCard title="Notification history" :subtitle="loading ? 'Loading alerts...' : `${alerts.length} alerts loaded.`">
        <AppTable :columns="columns" :has-rows="alerts.length > 0" empty-message="No alert history yet.">
          <tr v-for="alert in alerts" :key="alert.id">
            <td>
              <strong>{{ alert.company }}</strong>
              <p>{{ alert.title }}</p>
            </td>
            <td>{{ alert.recommendation }}</td>
            <td>{{ alert.channel }}</td>
            <td>{{ formatRelativeMinutes(alert.sent_minutes_ago) }}</td>
          </tr>
        </AppTable>
      </AppCard>
    </section>
  </div>
</template>

<style scoped>
.page-stack {
  display: grid;
  gap: var(--space-4);
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.8fr) minmax(0, 1.2fr);
  gap: var(--space-4);
}

td {
  padding: var(--space-4) 0;
  border-top: 1px solid var(--color-border);
}

td p {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
}

@media (max-width: 1023px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
