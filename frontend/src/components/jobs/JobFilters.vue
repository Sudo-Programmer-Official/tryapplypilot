<script setup lang="ts">
import AppInput from "../ui/AppInput.vue";
import AppSelect from "../ui/AppSelect.vue";

withDefaults(
  defineProps<{
    query: string;
    decision: string;
    freshness?: number | "all";
    minScore: number;
    sortBy?: string;
  }>(),
  {
    freshness: "all",
    sortBy: "highest_match",
  },
);

defineEmits<{
  (event: "update:query", value: string): void;
  (event: "update:decision", value: string): void;
  (event: "update:freshness", value: number | "all"): void;
  (event: "update:minScore", value: number): void;
  (event: "update:sortBy", value: string): void;
}>();
</script>

<template>
  <div class="job-filters surface-card">
    <div class="job-filters__toolbar">
      <AppInput :model-value="query" placeholder="Search roles or companies" @update:model-value="$emit('update:query', String($event))" />
      <AppSelect
        :model-value="decision"
        :options="[
          { label: 'Decision: All', value: 'all' },
          { label: 'Decision: Apply now', value: 'APPLY_NOW' },
          { label: 'Decision: Review', value: 'REVIEW' },
          { label: 'Decision: Ignore', value: 'IGNORE' },
        ]"
        @update:model-value="$emit('update:decision', $event)"
      />
      <AppSelect
        :model-value="freshness"
        :options="[
          { label: 'Freshness: All', value: 'all' },
          { label: 'Last 1 hour', value: 1 },
          { label: 'Last 6 hours', value: 6 },
          { label: 'Today', value: 24 },
          { label: 'Last 3 days', value: 24 * 3 },
          { label: 'Last 7 days', value: 24 * 7 },
          { label: 'Last 30 days', value: 24 * 30 },
        ]"
        @update:model-value="$emit('update:freshness', $event === 'all' ? 'all' : Number($event) || 'all')"
      />
      <AppInput
        :model-value="minScore"
        type="number"
        placeholder="Match >= 90"
        :min="0"
        :max="100"
        @update:model-value="$emit('update:minScore', Number($event) || 0)"
      />
      <AppSelect
        :model-value="sortBy"
        :options="[
          { label: 'Sort: Highest Match', value: 'highest_match' },
          { label: 'Sort: Newest', value: 'newest' },
          { label: 'Sort: Company', value: 'company' },
          { label: 'Sort: Recently Updated', value: 'recently_updated' },
        ]"
        @update:model-value="$emit('update:sortBy', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.job-filters {
  padding: var(--space-4);
}

.job-filters__toolbar {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: minmax(0, 2.3fr) repeat(3, minmax(150px, 0.9fr)) minmax(160px, 1fr);
}

.job-filters :deep(.app-input),
.job-filters :deep(.app-select) {
  min-height: 3.35rem;
  border-radius: 1rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.68);
}

.job-filters :deep(.app-input:hover),
.job-filters :deep(.app-select:hover) {
  border-color: var(--color-border-strong);
}

@media (max-width: 1023px) {
  .job-filters__toolbar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .job-filters {
    padding: var(--space-3);
  }

  .job-filters__toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
