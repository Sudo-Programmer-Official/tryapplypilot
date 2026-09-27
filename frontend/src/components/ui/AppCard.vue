<script setup lang="ts">
import { computed, ref, useSlots } from "vue";
import { ChevronDown } from "lucide-vue-next";

// Vue casts an omitted boolean prop to false, so the padded default must be explicit.
const props = withDefaults(
  defineProps<{
    title?: string;
    subtitle?: string;
    padded?: boolean;
    collapsible?: boolean;
    defaultOpen?: boolean;
  }>(),
  { padded: true, collapsible: false, defaultOpen: false },
);

const slots = useSlots();

const hasHeader = computed(() => Boolean(props.title || props.subtitle || slots.header || slots.actions));
// The standard layout already renders a padded footer; only custom header/body slots need
// the structured layout (which skips the title, subtitle and padding).
const hasStructuredSlots = computed(() => Boolean(slots.header || slots.body));
const hasNamedBody = computed(() => Boolean(slots.body));
const isOpen = ref(!props.collapsible || props.defaultOpen);
</script>

<template>
  <section
    class="app-card surface-card"
    :class="{ 'app-card--padded': props.padded, 'app-card--collapsed': collapsible && !isOpen }"
  >
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
        <button
          v-if="collapsible"
          type="button"
          class="app-card__header-copy app-card__toggle"
          :aria-expanded="isOpen"
          @click="isOpen = !isOpen"
        >
          <span class="app-card__toggle-copy">
            <span v-if="title" class="app-card__title">{{ title }}</span>
            <span v-if="subtitle" class="app-card__subtitle">{{ subtitle }}</span>
          </span>
          <ChevronDown class="app-card__chevron" aria-hidden="true" />
        </button>
        <div v-else class="app-card__header-copy">
          <slot name="header">
            <h3 v-if="title" class="app-card__title">{{ title }}</h3>
            <p v-if="subtitle" class="app-card__subtitle">{{ subtitle }}</p>
          </slot>
        </div>
        <div v-if="$slots.actions && isOpen" class="app-card__actions">
          <slot name="actions" />
        </div>
      </header>
      <div v-show="isOpen" class="app-card__body card-content" :class="{ 'app-card__body--standalone': !hasHeader }">
        <slot />
      </div>
      <footer v-if="$slots.footer" v-show="isOpen" class="app-card__footer">
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

:where(.app-card--padded) .app-card__header {
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

:where(.app-card--padded) .app-card__body {
  padding-top: var(--card-body-padding-top);
}

:where(.app-card--padded) .app-card__body--standalone {
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

.app-card__toggle {
  display: flex;
  flex: 1;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--content-gap);
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.app-card__toggle-copy {
  display: grid;
  gap: var(--heading-gap);
  min-width: 0;
}

.app-card__chevron {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  margin-top: 2px;
  color: var(--color-text-muted);
  transition: transform var(--transition-fast);
}

.app-card__toggle[aria-expanded="true"] .app-card__chevron {
  transform: rotate(180deg);
}

:where(.app-card--collapsed.app-card--padded) .app-card__header {
  padding-bottom: var(--card-padding);
}
</style>
