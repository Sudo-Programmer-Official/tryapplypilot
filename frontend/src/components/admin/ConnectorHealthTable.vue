<script setup lang="ts">
import AppBadge from "../ui/AppBadge.vue";
import AppCard from "../ui/AppCard.vue";
import AppTable from "../ui/AppTable.vue";
import type { SourceStatus, TableColumn } from "../../types";
import { formatDateTime, formatDurationSeconds, formatPercent, sourceStatusTone } from "../../utils/format";

defineProps<{
  sources: SourceStatus[];
}>();

const layerLabels: Record<SourceStatus["layer"], string> = {
  official_ats: "Official ATS",
  company_careers: "Company Careers",
  job_aggregator: "Job Aggregators",
  discovery_agent: "Discovery Agent",
};

const roadmapLabels: Record<SourceStatus["admin_status"], string> = {
  live: "Live",
  beta: "Beta",
  planned: "Planned",
  disabled: "Disabled",
};

const confidenceLabels: Record<SourceStatus["layer"], string> = {
  official_ats: "★★★★★ Official ATS",
  company_careers: "★★★★☆ Company careers",
  job_aggregator: "★★★☆☆ Aggregator",
  discovery_agent: "★★☆☆☆ Discovery",
};

function coveragePercent(source: SourceStatus): number {
  if (source.catalog_company_count <= 0) {
    return 0;
  }
  return (source.companies_enabled / source.catalog_company_count) * 100;
}

const columns: TableColumn[] = [
  { key: "source", label: "Connector" },
  { key: "layer", label: "Layer" },
  { key: "confidence", label: "Confidence" },
  { key: "roadmap", label: "Roadmap" },
  { key: "status", label: "Status" },
  { key: "coverage", label: "Coverage" },
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
        <td>{{ layerLabels[source.layer] }}</td>
        <td>{{ confidenceLabels[source.layer] }}</td>
        <td>{{ roadmapLabels[source.admin_status] }}</td>
        <td>
          <AppBadge :tone="sourceStatusTone(source) === 'healthy' ? 'success' : sourceStatusTone(source) === 'warning' ? 'warning' : sourceStatusTone(source) === 'failed' ? 'danger' : 'neutral'">
            {{ sourceStatusTone(source) }}
          </AppBadge>
        </td>
        <td>{{ source.companies_enabled }}/{{ source.catalog_company_count }} · {{ formatPercent(coveragePercent(source)) }}</td>
        <td>{{ formatDateTime(source.last_successful_sync) }}</td>
        <td>{{ formatDateTime(source.last_failed_sync) }}</td>
        <td>{{ source.jobs_collected }}</td>
        <td>{{ formatDurationSeconds(source.average_runtime_seconds) }}</td>
        <td>{{ formatDateTime(source.next_scheduled_poll) }}</td>
      </tr>
    </AppTable>
  </AppCard>
</template>
