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
  gap: var(--content-gap);
  overflow: hidden;
  height: 100%;
}

.app-card--padded {
  padding: var(--card-padding);
}

.app-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--content-gap);
}

.app-card__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--type-title);
  line-height: 1.2;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.app-card__subtitle {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
  line-height: 1.5;
}
</style>
