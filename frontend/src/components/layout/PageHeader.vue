<script setup lang="ts">
defineProps<{
  title: string;
  description: string;
}>();
</script>

<template>
  <div class="page-header">
    <div class="page-header__copy">
      <p class="eyebrow">TryApplyPilot</p>
      <div class="page-header__heading-group">
        <h1 class="type-heading">{{ title }}</h1>
        <p class="type-small page-header__description">{{ description }}</p>
      </div>
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
  gap: var(--page-section-gap);
}

.page-header__copy {
  display: grid;
  gap: var(--subtitle-gap);
}

.page-header__heading-group {
  display: grid;
  gap: var(--heading-gap);
}

.page-header__description {
  margin: 0;
  color: var(--color-text-muted);
}

@media (max-width: 767px) {
  .page-header {
    flex-direction: column;
  }
}
</style>
