<script setup lang="ts">
defineProps<{
  title: string;
  description: string;
}>();
</script>

<template>
  <div class="page-header">
    <div>
      <p class="eyebrow">TryApplyPilot</p>
      <h2>{{ title }}</h2>
      <p>{{ description }}</p>
    </div>
    <div v-if="$slots.actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.page-header h2 {
  margin: 0.35rem 0 0;
  font-family: var(--font-display);
  font-size: 1.7rem;
}

.page-header p:last-child {
  margin: var(--space-2) 0 0;
  color: var(--color-text-muted);
}

@media (max-width: 767px) {
  .page-header {
    flex-direction: column;
  }
}
</style>
