<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { fetchAdminJobs } from "../../api/jobs.api";
import JobFilters from "../../components/jobs/JobFilters.vue";
import JobRow from "../../components/jobs/JobRow.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppSkeleton from "../../components/ui/AppSkeleton.vue";
import { useJobs } from "../../composables/useJobs";
import type { JobDecisionFilter, JobSortOption } from "../../composables/useJobs";
import type { JobOpportunity } from "../../types";
import { formatCompactNumber } from "../../utils/format";

const PAGE_SIZE = 20;

const jobs = ref<JobOpportunity[]>([]);
const total = ref(0);
const hasMore = ref(false);
const loading = ref(true);
const loadingMore = ref(false);
const error = ref<string | null>(null);

const query = ref("");
const decision = ref<JobDecisionFilter>("all");
const freshnessHours = ref<number | "all">("all");
const minScore = ref(0);
const sortBy = ref<JobSortOption>("highest_match");

const { toggleSavedJob, isSavedJob } = useJobs(jobs);

const totalLabel = computed(() => `${formatCompactNumber(total.value)} matching jobs`);
const loadedLabel = computed(() => `${formatCompactNumber(jobs.value.length)} loaded now`);
const inventoryLabel = computed(() => {
  if (loading.value && jobs.value.length === 0) {
    return "Loading shared job inventory...";
  }
  if (loadingMore.value) {
    return "Loading the next 20 jobs...";
  }
  if (loading.value) {
    return "Refreshing filtered inventory...";
  }
  if (hasMore.value) {
    return `${formatCompactNumber(Math.max(total.value - jobs.value.length, 0))} more available on demand`;
  }
  return "All matching jobs currently loaded";
});

let reloadHandle: number | null = null;
let requestVersion = 0;

async function load(append = false): Promise<void> {
  const nextOffset = append ? jobs.value.length : 0;
  const currentRequest = ++requestVersion;

  if (append) {
    loadingMore.value = true;
  } else {
    loading.value = true;
  }
  error.value = null;

  try {
    const payload = await fetchAdminJobs({
      query: query.value,
      decision: decision.value,
      minScore: minScore.value > 0 ? minScore.value : undefined,
      maxAgeHours: freshnessHours.value === "all" ? undefined : freshnessHours.value,
      sortBy: sortBy.value,
      limit: PAGE_SIZE,
      offset: nextOffset,
    });
    if (currentRequest !== requestVersion) {
      return;
    }
    jobs.value = append ? [...jobs.value, ...payload.items] : payload.items;
    total.value = payload.total;
    hasMore.value = payload.has_more;
  } catch (err) {
    if (currentRequest !== requestVersion) {
      return;
    }
    error.value = err instanceof Error ? err.message : "Failed to load admin jobs.";
    if (!append) {
      jobs.value = [];
      total.value = 0;
      hasMore.value = false;
    }
  } finally {
    if (currentRequest === requestVersion) {
      loading.value = false;
      loadingMore.value = false;
    }
  }
}

function queueReload(): void {
  if (reloadHandle !== null) {
    window.clearTimeout(reloadHandle);
  }
  reloadHandle = window.setTimeout(() => {
    void load(false);
  }, 180);
}

watch([query, decision, freshnessHours, minScore, sortBy], queueReload);

onMounted(() => {
  void load(false);
});

onBeforeUnmount(() => {
  if (reloadHandle !== null) {
    window.clearTimeout(reloadHandle);
  }
});
</script>

<template>
  <AppPage class="admin-jobs-page">
    <PageHeader
      title="Jobs"
      description="Inspect the shared opportunity pool without forcing the admin workspace to render the full inventory at once."
    />

    <PageSection class="admin-jobs-page__summary-section">
      <div class="admin-jobs-summary surface-card">
        <div class="admin-jobs-summary__copy">
          <p class="admin-jobs-summary__eyebrow">Admin Inventory</p>
          <div class="admin-jobs-summary__stats">
            <strong>{{ totalLabel }}</strong>
            <span>{{ loadedLabel }}</span>
            <span>{{ inventoryLabel }}</span>
          </div>
        </div>
        <div class="admin-jobs-summary__actions">
          <AppBadge :tone="loading || loadingMore ? 'info' : 'neutral'">
            {{ loadingMore ? "Loading more" : loading ? "Refreshing" : "Paged view" }}
          </AppBadge>
          <AppButton variant="secondary" :disabled="loading || loadingMore" @click="void load(false)">
            {{ loading ? "Refreshing..." : "Refresh" }}
          </AppButton>
        </div>
      </div>
    </PageSection>

    <PageSection>
      <AppGrid columns="1">
        <JobFilters
          :query="query"
          :decision="decision"
          :freshness="freshnessHours"
          :min-score="minScore"
          :sort-by="sortBy"
          @update:query="query = $event"
          @update:decision="decision = $event as JobDecisionFilter"
          @update:freshness="freshnessHours = $event"
          @update:min-score="minScore = $event"
          @update:sort-by="sortBy = $event as JobSortOption"
        />
      </AppGrid>
    </PageSection>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Admin jobs unavailable" :description="error" />
      </AppGrid>
    </PageSection>

    <PageSection v-else-if="loading && jobs.length === 0">
      <AppGrid columns="1">
        <AppCard class="admin-jobs-loading" title="Loading admin inventory" subtitle="Fetching the first 20 jobs and the current total count.">
          <div class="admin-jobs-loading__stack">
            <div v-for="index in 3" :key="index" class="admin-jobs-loading__item">
              <AppSkeleton class="admin-jobs-loading__title" />
              <AppSkeleton class="admin-jobs-loading__meta" />
              <AppSkeleton class="admin-jobs-loading__meta admin-jobs-loading__meta--short" />
            </div>
          </div>
        </AppCard>
      </AppGrid>
    </PageSection>

    <PageSection v-else-if="jobs.length === 0">
      <AppGrid columns="1">
        <AppEmptyState
          title="No jobs match the current filters"
          description="Broaden the filter set or wait for the next connector cycle to surface more inventory."
        />
      </AppGrid>
    </PageSection>

    <PageSection v-else>
      <AppGrid columns="1">
        <div class="app-stack app-stack--content admin-jobs-list">
          <JobRow
            v-for="job in jobs"
            :key="job.id"
            :job="job"
            :saved="isSavedJob(job.id)"
            @toggle-save="toggleSavedJob"
          />
        </div>
      </AppGrid>
    </PageSection>

    <PageSection v-if="!error && jobs.length > 0 && hasMore">
      <AppGrid columns="1">
        <div class="admin-jobs-load-more surface-card">
          <div class="admin-jobs-load-more__copy">
            <strong>{{ formatCompactNumber(total - jobs.length) }} jobs still hidden</strong>
            <span>Admin pages now load in 20-job batches so large inventories stay responsive.</span>
          </div>
          <AppButton :disabled="loadingMore || loading" @click="void load(true)">
            {{ loadingMore ? "Loading..." : "Load 20 more" }}
          </AppButton>
        </div>
      </AppGrid>
    </PageSection>
  </AppPage>
</template>

<style scoped>
.admin-jobs-page {
  --page-gap: var(--space-5);
}

.admin-jobs-page__summary-section {
  margin-bottom: calc(var(--space-2) * -1);
}

.admin-jobs-summary,
.admin-jobs-load-more {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: clamp(var(--space-4), 2vw, var(--space-5));
}

.admin-jobs-summary__copy,
.admin-jobs-load-more__copy {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.admin-jobs-summary__eyebrow {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--type-caption);
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.admin-jobs-summary__stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: center;
}

.admin-jobs-summary__stats strong,
.admin-jobs-load-more__copy strong {
  font-family: var(--font-display);
  font-size: clamp(1.2rem, 1.6vw, 1.45rem);
  letter-spacing: -0.03em;
}

.admin-jobs-summary__stats span,
.admin-jobs-load-more__copy span {
  color: var(--color-text-muted);
  font-size: 0.95rem;
  line-height: 1.55;
}

.admin-jobs-summary__actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.admin-jobs-list {
  gap: var(--space-4);
}

.admin-jobs-loading__stack {
  display: grid;
  gap: var(--space-4);
}

.admin-jobs-loading__item {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-5);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(246, 249, 253, 0.98));
}

.admin-jobs-loading__title {
  min-height: 1.4rem;
  max-width: 50%;
}

.admin-jobs-loading__meta {
  min-height: 1rem;
}

.admin-jobs-loading__meta--short {
  max-width: 38%;
}

@media (max-width: 767px) {
  .admin-jobs-summary,
  .admin-jobs-load-more {
    flex-direction: column;
    align-items: stretch;
  }

  .admin-jobs-summary__actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
