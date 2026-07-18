<script setup lang="ts">
import AppBadge from "../ui/AppBadge.vue";
import AppCard from "../ui/AppCard.vue";
import AppTable from "../ui/AppTable.vue";
import type { SourceStatus, TableColumn } from "../../types";
import { formatDateTime, formatDurationSeconds, sourceStatusTone } from "../../utils/format";

defineProps<{
  sources: SourceStatus[];
}>();

const columns: TableColumn[] = [
  { key: "source", label: "Connector" },
  { key: "status", label: "Status" },
  { key: "lastSuccess", label: "Last Success" },
  { key: "lastFailure", label: "Last Failure" },
  { key: "jobsCollected", label: "Jobs Collected" },
  { key: "avgRuntime", label: "Avg Runtime" },
  { key: "nextRun", label: "Next Poll" },
];
</script>

<template>
  <AppCard title="Connector Health">
    <AppTable :columns="columns" :has-rows="sources.length > 0" empty-message="No connector history available.">
      <tr v-for="source in sources" :key="source.id">
        <td>{{ source.source }}</td>
        <td>
          <AppBadge :tone="sourceStatusTone(source) === 'healthy' ? 'success' : sourceStatusTone(source) === 'warning' ? 'warning' : sourceStatusTone(source) === 'failed' ? 'danger' : 'neutral'">
            {{ sourceStatusTone(source) }}
          </AppBadge>
        </td>
        <td>{{ formatDateTime(source.last_successful_sync) }}</td>
        <td>{{ formatDateTime(source.last_failed_sync) }}</td>
        <td>{{ source.jobs_collected }}</td>
        <td>{{ formatDurationSeconds(source.average_runtime_seconds) }}</td>
        <td>{{ formatDateTime(source.next_scheduled_poll) }}</td>
      </tr>
    </AppTable>
  </AppCard>
</template>

<style scoped>
td {
  padding: var(--space-4) 0;
  border-top: 1px solid var(--color-border);
}
</style>
