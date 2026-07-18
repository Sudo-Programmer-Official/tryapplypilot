<script setup lang="ts">
import { computed, useSlots } from "vue";

const props = defineProps<{
  title?: string;
  subtitle?: string;
  padded?: boolean;
}>();

const slots = useSlots();

const hasHeader = computed(() => Boolean(props.title || props.subtitle || slots.header || slots.actions));
const hasStructuredSlots = computed(() => Boolean(slots.header || slots.body || slots.footer));
const hasNamedBody = computed(() => Boolean(slots.body));
</script>

<template>
  <section class="app-card surface-card" :class="{ 'app-card--padded': padded !== false }">
    <template v-if="hasStructuredSlots">
      <slot name="header" />
      <slot v-if="hasNamedBody" name="body" />
      <div v-else-if="$slots.default" class="app-card__body card-content" :class="{ 'app-card__body--standalone': !hasHeader }">
        <slot />
      </div>
      <slot name="footer" />
    </template>
    <template v-else>
      <header v-if="hasHeader" class="app-card__header">
        <div class="app-card__header-copy">
          <slot name="header">
            <h3 v-if="title" class="app-card__title">{{ title }}</h3>
            <p v-if="subtitle" class="app-card__subtitle">{{ subtitle }}</p>
          </slot>
        </div>
        <div v-if="$slots.actions" class="app-card__actions">
          <slot name="actions" />
        </div>
      </header>
      <div class="app-card__body card-content" :class="{ 'app-card__body--standalone': !hasHeader }">
        <slot />
      </div>
      <footer v-if="$slots.footer" class="app-card__footer">
        <slot name="footer" />
      </footer>
    </template>
  </section>
</template>

<style scoped>
.app-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  min-width: 0;
}

.app-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--content-gap);
  min-width: 0;
}

.app-card__header-copy {
  display: grid;
  gap: var(--heading-gap);
  min-width: 0;
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
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
  line-height: 1.5;
}

.app-card__body {
  min-width: 0;
  padding-top: var(--card-padding);
}

.app-card--padded .app-card__body {
  padding-top: var(--card-body-padding-top);
}

.app-card--padded .app-card__body--standalone {
  padding-top: var(--card-padding);
}

.app-card__actions {
  display: inline-flex;
  align-items: center;
  gap: var(--content-gap);
}

.app-card__footer {
  padding: 0 var(--card-padding) var(--card-padding);
}
</style>
