<script setup lang="ts">
import { onMounted, ref } from "vue";

import JobFilters from "../../components/jobs/JobFilters.vue";
import JobRow from "../../components/jobs/JobRow.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import { fetchAdminJobs } from "../../api/jobs.api";
import { useJobs } from "../../composables/useJobs";
import type { JobOpportunity } from "../../types";

const jobs = ref<JobOpportunity[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const { query, decision, minScore, filteredJobs, toggleSavedJob, isSavedJob } = useJobs(jobs);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const payload = await fetchAdminJobs();
    jobs.value = payload.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load admin jobs.";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-stack">
    <PageHeader
      title="Jobs"
      description="Inspect the shared opportunity pool across connectors, freshness windows, and recommendation decisions."
    />

    <JobFilters
      :query="query"
      :decision="decision"
      :min-score="minScore"
      @update:query="query = $event"
      @update:decision="decision = $event as 'all' | 'APPLY_NOW' | 'REVIEW' | 'IGNORE'"
      @update:min-score="minScore = $event"
    />

    <AppEmptyState v-if="error" title="Admin jobs unavailable" :description="error" />
    <AppEmptyState
      v-else-if="!loading && filteredJobs.length === 0"
      title="No jobs match the current filters"
      description="The connector pipeline may still be syncing or the filter is too narrow."
    />

    <div v-else class="job-list">
      <JobRow
        v-for="job in filteredJobs"
        :key="job.id"
        :job="job"
        :saved="isSavedJob(job.id)"
        @toggle-save="toggleSavedJob"
      />
    </div>
  </div>
</template>

<style scoped>
.page-stack,
.job-list {
  display: grid;
  gap: var(--space-4);
}
</style>
