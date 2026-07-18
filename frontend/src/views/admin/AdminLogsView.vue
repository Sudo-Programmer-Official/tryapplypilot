<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import ActivityList from "../../components/dashboard/ActivityList.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import { fetchAuditLogs } from "../../api/admin.api";
import type { AuditLogEntry } from "../../types";
import { formatDateTime } from "../../utils/format";

const logs = ref<AuditLogEntry[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

function logTone(eventType: string): "success" | "warning" | "danger" | "info" {
  if (eventType.endsWith(".failed") || eventType.endsWith(".rejected")) {
    return "danger";
  }
  if (
    eventType.endsWith(".completed") ||
    eventType.endsWith(".approved") ||
    eventType.endsWith(".uploaded") ||
    eventType.endsWith(".registered")
  ) {
    return "success";
  }
  if (eventType.endsWith(".started")) {
    return "info";
  }
  return "warning";
}

const logItems = computed(() =>
  logs.value.map((log) => ({
    id: log.id,
    title: log.message,
    detail: `${log.event_type} · ${log.actor_email ?? "system"} · ${log.subject_type}`,
    age: formatDateTime(log.created_at),
    tone: logTone(log.event_type),
  })),
);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const payload = await fetchAuditLogs();
    logs.value = payload.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load audit logs.";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-stack">
    <PageHeader title="Logs" description="A compact audit trail for user events, scheduler cycles, approvals, and connector failures." />

    <AppEmptyState v-if="error" title="Logs unavailable" :description="error" />
    <AppEmptyState v-else-if="!loading && logItems.length === 0" title="No audit logs yet" description="New operational and account events will appear here." />

    <AppCard v-else title="Recent operational events" subtitle="Use this before digging into raw logs or database state.">
      <ActivityList :items="logItems" />
    </AppCard>
  </div>
</template>

<style scoped>
.page-stack {
  display: grid;
  gap: var(--space-4);
}
</style>
