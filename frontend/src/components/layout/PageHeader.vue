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
      <h1 class="type-heading">{{ title }}</h1>
      <p class="type-small page-header__description">{{ description }}</p>
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
  gap: var(--content-gap);
}

.page-header__description {
  margin-top: var(--space-2);
  color: var(--color-text-muted);
}

@media (max-width: 767px) {
  .page-header {
    flex-direction: column;
  }
}
</style>
