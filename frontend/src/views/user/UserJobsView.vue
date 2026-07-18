<script setup lang="ts">
import { onMounted, ref } from "vue";

import JobFilters from "../../components/jobs/JobFilters.vue";
import JobRow from "../../components/jobs/JobRow.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import { fetchUserJobs } from "../../api/user.api";
import { useJobs } from "../../composables/useJobs";
import type { JobOpportunity } from "../../types";

const jobs = ref<JobOpportunity[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const { query, decision, minScore, filteredJobs, savedJobs, toggleSavedJob, isSavedJob } = useJobs(jobs);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const payload = await fetchUserJobs();
    jobs.value = payload.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load jobs.";
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
      description="Search, filter, and bookmark the roles that already passed your personalized scoring pipeline."
    >
      <template #actions>
        <div class="jobs-summary surface-card">
          <strong>{{ filteredJobs.length }}</strong>
          <span>matching jobs · {{ savedJobs.length }} saved</span>
        </div>
      </template>
    </PageHeader>

    <JobFilters
      :query="query"
      :decision="decision"
      :min-score="minScore"
      @update:query="query = $event"
      @update:decision="decision = $event as 'all' | 'APPLY_NOW' | 'REVIEW' | 'IGNORE'"
      @update:min-score="minScore = $event"
    />

    <AppEmptyState v-if="error" title="Jobs unavailable" :description="error" />
    <AppEmptyState
      v-else-if="!loading && filteredJobs.length === 0"
      title="No jobs match these filters"
      description="Try lowering the score threshold or clearing the search to widen the queue."
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

.jobs-summary {
  display: grid;
  gap: var(--space-1);
  padding: var(--space-4);
  text-align: right;
}

.jobs-summary strong {
  font-family: var(--font-display);
  font-size: 1.6rem;
}

.jobs-summary span {
  color: var(--color-text-muted);
  font-size: 0.85rem;
}
</style>
