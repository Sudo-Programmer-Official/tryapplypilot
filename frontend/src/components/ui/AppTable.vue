<script setup lang="ts">
import type { TableColumn } from "../../types";

defineProps<{
  columns: TableColumn[];
  emptyMessage?: string;
  hasRows: boolean;
}>();
</script>

<template>
  <div class="app-table">
    <table v-if="hasRows">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column.key" :class="column.className">{{ column.label }}</th>
        </tr>
      </thead>
      <tbody>
        <slot />
      </tbody>
    </table>
    <div v-else class="app-table__empty">
      {{ emptyMessage ?? "Nothing to show yet." }}
    </div>
  </div>
</template>

<style scoped>
.app-table {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 720px;
}

th {
  padding: 0 0 var(--content-gap);
  text-align: left;
  color: var(--color-text-muted);
  font-size: var(--type-caption);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

:deep(tbody td) {
  padding: var(--content-gap) 0;
  border-top: 1px solid var(--color-border);
  vertical-align: top;
}

:deep(tbody td p) {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
  line-height: 1.5;
}

:deep(.app-table__actions) {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.app-table__empty {
  padding: var(--card-padding);
  border: 1px dashed var(--color-border);
  border-radius: var(--card-radius);
  text-align: center;
  color: var(--color-text-muted);
}
</style>
