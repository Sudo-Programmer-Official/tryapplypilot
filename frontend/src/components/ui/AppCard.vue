<script setup lang="ts">
import { computed, useSlots } from "vue";

const props = defineProps<{
  title?: string;
  subtitle?: string;
  padded?: boolean;
}>();

const slots = useSlots();

const hasHeader = computed(() => Boolean(props.title || props.subtitle || slots.header || slots.actions));
</script>

<template>
  <section class="app-card surface-card" :class="{ 'app-card--padded': padded !== false }">
    <header v-if="hasHeader" class="app-card__header">
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
    <div class="app-card__body" :class="{ 'app-card__body--standalone': !hasHeader }">
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
  min-width: 0;
}

.app-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--content-gap);
}

.app-card--padded .app-card__header {
  padding: var(--card-padding) var(--card-padding) 0;
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

.app-card__body {
  display: grid;
  gap: var(--content-gap);
  min-width: 0;
}

.app-card--padded .app-card__body {
  padding: 0 var(--card-padding) var(--card-padding);
}

.app-card--padded .app-card__body--standalone {
  padding-top: var(--card-padding);
}
</style>
