<script setup lang="ts">
import AppCard from "../ui/AppCard.vue";
import AppInput from "../ui/AppInput.vue";
import AppSelect from "../ui/AppSelect.vue";

defineProps<{
  query: string;
  decision: string;
  minScore: number;
}>();

defineEmits<{
  (event: "update:query", value: string): void;
  (event: "update:decision", value: string): void;
  (event: "update:minScore", value: number): void;
}>();
</script>

<template>
  <AppCard>
    <div class="job-filters">
      <AppInput :model-value="query" placeholder="Search roles or companies" @update:model-value="$emit('update:query', String($event))" />
      <AppSelect
        :model-value="decision"
        :options="[
          { label: 'All decisions', value: 'all' },
          { label: 'Apply now', value: 'APPLY_NOW' },
          { label: 'Review', value: 'REVIEW' },
          { label: 'Ignore', value: 'IGNORE' },
        ]"
        @update:model-value="$emit('update:decision', $event)"
      />
      <AppInput
        :model-value="minScore"
        type="number"
        placeholder="0"
        label="Min score"
        :min="0"
        :max="100"
        @update:model-value="$emit('update:minScore', Number($event) || 0)"
      />
    </div>
  </AppCard>
</template>

<style scoped>
.job-filters {
  display: grid;
  gap: var(--content-gap);
  grid-template-columns: minmax(0, 1.8fr) minmax(220px, 1fr) minmax(160px, 0.75fr);
}

@media (max-width: 767px) {
  .job-filters {
    grid-template-columns: 1fr;
  }
}
</style>
