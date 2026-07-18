<script setup lang="ts">
defineProps<{
  title?: string;
  subtitle?: string;
  padded?: boolean;
}>();
</script>

<template>
  <section class="app-card surface-card" :class="{ 'app-card--padded': padded !== false }">
    <header v-if="title || subtitle || $slots.header || $slots.actions" class="app-card__header">
      <div>
        <slot name="header">
          <h3 v-if="title" class="app-card__title">{{ title }}</h3>
          <p v-if="subtitle" class="app-card__subtitle">{{ subtitle }}</p>
        </slot>
      </div>
      <div v-if="$slots.actions" class="app-card__actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="app-card__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.app-card {
  display: grid;
  gap: var(--space-4);
}

.app-card--padded {
  padding: var(--space-5);
}

.app-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.app-card__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.app-card__subtitle {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
  font-size: 0.92rem;
}
</style>
