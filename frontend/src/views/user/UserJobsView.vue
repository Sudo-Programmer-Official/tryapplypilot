<script setup lang="ts">
import { onMounted, ref } from "vue";

import JobFilters from "../../components/jobs/JobFilters.vue";
import JobRow from "../../components/jobs/JobRow.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
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
  <AppPage>
    <PageHeader
      title="Jobs"
      description="Search, filter, and bookmark the roles that already passed your personalized scoring pipeline."
    >
      <template #actions>
        <AppCard class="jobs-summary" :padded="true">
          <strong class="type-display">{{ filteredJobs.length }}</strong>
          <span class="type-caption">matching jobs · {{ savedJobs.length }} saved</span>
        </AppCard>
      </template>
    </PageHeader>

    <PageSection>
      <AppGrid columns="1">
        <JobFilters
          :query="query"
          :decision="decision"
          :min-score="minScore"
          @update:query="query = $event"
          @update:decision="decision = $event as 'all' | 'APPLY_NOW' | 'REVIEW' | 'IGNORE'"
          @update:min-score="minScore = $event"
        />
      </AppGrid>
    </PageSection>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Jobs unavailable" :description="error" />
      </AppGrid>
    </PageSection>
    <PageSection v-else-if="!loading && filteredJobs.length === 0">
      <AppGrid columns="1">
        <AppEmptyState
          title="No jobs match these filters"
          description="Try lowering the score threshold or clearing the search to widen the queue."
        />
      </AppGrid>
    </PageSection>

    <PageSection v-else>
      <AppGrid columns="1">
        <div class="app-stack app-stack--content">
          <JobRow
            v-for="job in filteredJobs"
            :key="job.id"
            :job="job"
            :saved="isSavedJob(job.id)"
            @toggle-save="toggleSavedJob"
          />
        </div>
      </AppGrid>
    </PageSection>
  </AppPage>
</template>

<style scoped>
.jobs-summary {
  display: grid;
  gap: var(--space-1);
  text-align: right;
  min-width: 192px;
}
</style>
