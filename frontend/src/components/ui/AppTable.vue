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
  padding: 0 0 var(--space-4);
  text-align: left;
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.app-table__empty {
  padding: var(--space-8);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  text-align: center;
  color: var(--color-text-muted);
}
</style>
