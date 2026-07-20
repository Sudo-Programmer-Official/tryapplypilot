<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import JobFilters from "../../components/jobs/JobFilters.vue";
import JobRow from "../../components/jobs/JobRow.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import { fetchUserJobs } from "../../api/user.api";
import { useJobs } from "../../composables/useJobs";
import type { JobOpportunity } from "../../types";

const route = useRoute();
const router = useRouter();
const jobs = ref<JobOpportunity[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const loadMoreSentinel = ref<HTMLElement | null>(null);
const batchSize = 20;
const visibleCount = ref(batchSize);
let loadMoreObserver: IntersectionObserver | null = null;

const {
  query,
  decision,
  freshnessHours,
  minScore,
  sortBy,
  activeQueue,
  queueCounts,
  filteredJobs,
  savedJobs,
  toggleSavedJob,
  isSavedJob,
} = useJobs(jobs, { initialQuery: String(route.query.q ?? "") });

const visibleJobs = computed(() => filteredJobs.value.slice(0, visibleCount.value));
const hasMore = computed(() => visibleCount.value < filteredJobs.value.length);
const updatedLabel = computed(() => (loading.value ? "Updating..." : "Updated just now"));
const queueTabs = computed(() => [
  { value: "all", label: "All", count: queueCounts.value.all },
  { value: "APPLY_NOW", label: "Apply Now", count: queueCounts.value.applyNow },
  { value: "REVIEW", label: "Review", count: queueCounts.value.review },
  { value: "saved", label: "Saved", count: queueCounts.value.saved },
]);

function resetVisible(): void {
  visibleCount.value = batchSize;
}

function loadMore(): void {
  visibleCount.value = Math.min(filteredJobs.value.length, visibleCount.value + batchSize);
}

function disconnectLoadMoreObserver(): void {
  loadMoreObserver?.disconnect();
  loadMoreObserver = null;
}

function syncLoadMoreObserver(): void {
  disconnectLoadMoreObserver();
  if (!loadMoreSentinel.value || !hasMore.value || typeof IntersectionObserver === "undefined") {
    return;
  }
  loadMoreObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        loadMore();
      }
    },
    { rootMargin: "320px 0px" },
  );
  loadMoreObserver.observe(loadMoreSentinel.value);
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const payload = await fetchUserJobs();
    jobs.value = payload.items;
    resetVisible();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load jobs.";
  } finally {
    loading.value = false;
  }
}

watch(
  [query, decision, freshnessHours, minScore, sortBy, activeQueue],
  () => {
    resetVisible();
  },
  { deep: false },
);

watch(
  () => route.query.q,
  (value) => {
    const next = String(value ?? "");
    if (next !== query.value) {
      query.value = next;
    }
  },
);

watch(query, async (value) => {
  const nextQuery = value.trim() ? value : undefined;
  if (String(route.query.q ?? "") === (nextQuery ?? "")) {
    return;
  }
  await router.replace({
    query: {
      ...route.query,
      q: nextQuery,
    },
  });
});

watch([loadMoreSentinel, hasMore], () => {
  syncLoadMoreObserver();
});

onMounted(load);
onBeforeUnmount(disconnectLoadMoreObserver);
</script>

<template>
  <AppPage class="jobs-page">
    <PageSection class="jobs-controls-section">
      <div class="jobs-inline-header">
        <div class="jobs-inline-stats">
          <strong>{{ filteredJobs.length }} jobs</strong>
          <span>{{ savedJobs.length }} saved</span>
          <span>{{ updatedLabel }}</span>
        </div>

        <div class="jobs-queues" aria-label="Job queues">
          <button
            v-for="queue in queueTabs"
            :key="queue.value"
            class="jobs-queue-chip"
            :class="{ 'jobs-queue-chip--active': activeQueue === queue.value }"
            type="button"
            @click="activeQueue = queue.value as 'all' | 'saved' | 'APPLY_NOW' | 'REVIEW'"
          >
            <span>{{ queue.label }}</span>
            <strong>{{ queue.count }}</strong>
          </button>
        </div>
      </div>

      <div class="jobs-toolbar">
        <JobFilters
          :query="query"
          :decision="decision"
          :freshness="freshnessHours"
          :min-score="minScore"
          :sort-by="sortBy"
          @update:query="query = $event"
          @update:decision="decision = $event as 'all' | 'APPLY_NOW' | 'REVIEW' | 'IGNORE'"
          @update:freshness="freshnessHours = $event"
          @update:min-score="minScore = $event"
          @update:sort-by="sortBy = $event as 'highest_match' | 'newest' | 'company' | 'recently_updated'"
        />
      </div>
    </PageSection>

    <PageSection v-if="loading && jobs.length === 0" class="jobs-state-section">
      <AppEmptyState title="Loading jobs" description="Refreshing your personalized queue." />
    </PageSection>
    <PageSection v-else-if="error" class="jobs-state-section">
      <AppEmptyState title="Jobs unavailable" :description="error" />
    </PageSection>
    <PageSection v-else-if="!loading && filteredJobs.length === 0" class="jobs-state-section">
      <AppEmptyState
        title="No jobs match these filters"
        description="Try lowering the score threshold or clearing the search to widen the queue."
      />
    </PageSection>

    <PageSection v-else class="jobs-results-section">
      <div class="jobs-list">
        <JobRow
          v-for="job in visibleJobs"
          :key="job.id"
          :job="job"
          :saved="isSavedJob(job.id)"
          @toggle-save="toggleSavedJob"
        />
      </div>

      <div class="jobs-load-more">
        <p>Showing {{ visibleJobs.length }} of {{ filteredJobs.length }} jobs</p>
        <AppButton v-if="hasMore" variant="secondary" @click="loadMore">Load 20 more</AppButton>
        <span v-else>All matching jobs loaded</span>
        <div ref="loadMoreSentinel" class="jobs-load-more__trigger" aria-hidden="true" />
      </div>
    </PageSection>
  </AppPage>
</template>

<style scoped>
.jobs-page {
  --page-gap: var(--space-5);
}

.jobs-controls-section,
.jobs-results-section,
.jobs-state-section {
  padding: 0;
}

.jobs-controls-section,
.jobs-results-section {
  display: grid;
  gap: var(--space-4);
}

.jobs-inline-header {
  display: grid;
  gap: var(--space-4);
}

.jobs-inline-stats {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
  min-height: 2rem;
}

.jobs-inline-stats strong {
  font-family: var(--font-display);
  font-size: clamp(1.35rem, 2vw, 1.7rem);
  letter-spacing: -0.03em;
}

.jobs-inline-stats span {
  color: var(--color-text-muted);
  font-size: 0.95rem;
}

.jobs-inline-stats span::before {
  content: "•";
  margin-right: var(--space-3);
  color: var(--color-border-strong);
}

.jobs-queues {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.jobs-queue-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 2.75rem;
  padding: 0 var(--space-4);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.76);
  color: var(--color-text-muted);
  cursor: pointer;
  transition:
    transform var(--transition-fast),
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    color var(--transition-fast),
    background var(--transition-fast);
}

.jobs-queue-chip strong {
  color: var(--color-text);
  font-size: 0.95rem;
}

.jobs-queue-chip:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 255, 0.18);
  box-shadow: 0 12px 24px rgba(15, 29, 58, 0.05);
}

.jobs-queue-chip--active {
  border-color: rgba(37, 99, 255, 0.18);
  background: rgba(37, 99, 255, 0.1);
  color: var(--color-primary);
}

.jobs-list {
  display: grid;
  gap: var(--space-4);
}

.jobs-load-more {
  display: grid;
  justify-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0 var(--space-4);
}

.jobs-load-more p,
.jobs-load-more span {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.95rem;
}

.jobs-load-more__trigger {
  width: 100%;
  height: 1px;
}

@media (max-width: 767px) {
  .jobs-inline-stats {
    gap: var(--space-2);
  }

  .jobs-inline-stats span::before {
    margin-right: var(--space-2);
  }

  .jobs-queues {
    gap: var(--space-2);
  }

  .jobs-queue-chip {
    min-height: 2.5rem;
    padding: 0 var(--space-3);
  }
}
</style>
