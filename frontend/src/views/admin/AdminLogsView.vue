<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { fetchAuditLogs } from "../../api/admin.api";
import ActivityList from "../../components/dashboard/ActivityList.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppSkeleton from "../../components/ui/AppSkeleton.vue";
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
  <AppPage class="admin-logs-page">
    <PageHeader title="Logs" description="A compact audit trail for user events, scheduler cycles, approvals, and connector failures." />

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Logs unavailable" :description="error" />
      </AppGrid>
    </PageSection>

    <PageSection v-else-if="loading">
      <AppGrid columns="1">
        <AppCard class="admin-logs-panel" title="Loading recent operational events">
          <div class="admin-logs-loading">
            <div v-for="index in 5" :key="index" class="admin-logs-loading__row">
              <AppSkeleton class="admin-logs-loading__title" />
              <AppSkeleton class="admin-logs-loading__meta" />
            </div>
          </div>
        </AppCard>
      </AppGrid>
    </PageSection>

    <PageSection v-else-if="logItems.length === 0">
      <AppGrid columns="1">
        <AppEmptyState title="No audit logs yet" description="New operational and account events will appear here." />
      </AppGrid>
    </PageSection>

    <PageSection v-else>
      <AppGrid columns="1">
        <AppCard class="admin-logs-panel" title="Recent operational events" subtitle="Use this before digging into raw logs or database state.">
          <ActivityList :items="logItems" />
        </AppCard>
      </AppGrid>
    </PageSection>
  </AppPage>
</template>

<style scoped>
.admin-logs-page {
  --page-gap: var(--space-5);
}

.admin-logs-panel :deep(.app-card__header) {
  padding: clamp(var(--space-6), 3vw, 2.25rem) clamp(var(--space-6), 4vw, 2.5rem) 0;
}

.admin-logs-panel :deep(.app-card__body) {
  padding: var(--space-5) clamp(var(--space-6), 4vw, 2.5rem) clamp(var(--space-6), 4vw, 2.25rem);
}

.admin-logs-loading {
  display: grid;
  gap: var(--space-4);
}

.admin-logs-loading__row {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-5);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(246, 249, 253, 0.98));
}

.admin-logs-loading__title {
  min-height: 1.2rem;
  max-width: 42%;
}

.admin-logs-loading__meta {
  min-height: 1rem;
}
</style>
