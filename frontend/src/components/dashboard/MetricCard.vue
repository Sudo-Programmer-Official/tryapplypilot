<script setup lang="ts">
import { computed } from "vue";

import AppCard from "../ui/AppCard.vue";
import { iconMap } from "../../utils/icons";

const props = defineProps<{
  icon: string;
  label: string;
  value: string | number;
  detail: string;
  tone?: "primary" | "success" | "warning" | "info";
  sparkline?: number[];
}>();

const icon = computed(() => iconMap[props.icon]);
const sparklinePoints = computed(() => {
  const values = props.sparkline ?? [];
  return values
    .map((point, index) => `${(index / Math.max(values.length - 1, 1)) * 120},${28 - point * 5}`)
    .join(" ");
});
</script>

<template>
  <AppCard class="metric-card">
    <div class="metric-card__top">
      <div class="metric-card__copy">
        <p class="metric-card__label">{{ label }}</p>
        <strong class="metric-card__value">{{ value }}</strong>
      </div>
      <span class="metric-card__icon" :class="`metric-card__icon--${tone ?? 'primary'}`">
        <component :is="icon" />
      </span>
    </div>
    <p class="metric-card__detail">{{ detail }}</p>
    <div v-if="sparkline?.length" class="metric-card__trend">
      <span class="metric-card__trend-label">Recent activity</span>
      <svg class="metric-card__spark" viewBox="0 0 120 28" preserveAspectRatio="none">
        <polyline
          :points="sparklinePoints"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </div>
  </AppCard>
</template>

<style scoped>
.metric-card {
  height: 100%;
}

.metric-card :deep(.app-card__body) {
  height: 100%;
  align-content: start;
}

.metric-card__top {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-4);
  align-items: start;
}

.metric-card__copy {
  min-width: 0;
}

.metric-card__icon {
  display: grid;
  place-items: center;
  width: 3.5rem;
  height: 3.5rem;
  border-radius: 1.15rem;
  background: var(--metric-surface);
  color: var(--metric-accent);
  box-shadow: inset 0 0 0 1px rgba(15, 29, 58, 0.05);
}

.metric-card__icon :deep(svg) {
  width: 1.9rem;
  height: 1.9rem;
}

.metric-card__icon--primary {
  --metric-surface: var(--color-primary-soft);
  --metric-accent: var(--color-primary);
}

.metric-card__icon--success {
  --metric-surface: var(--color-success-soft);
  --metric-accent: var(--color-success);
}

.metric-card__icon--warning {
  --metric-surface: var(--color-warning-soft);
  --metric-accent: var(--color-warning);
}

.metric-card__icon--info {
  --metric-surface: var(--color-info-soft);
  --metric-accent: var(--color-info);
}

.metric-card__label,
.metric-card__detail {
  margin: 0;
  color: var(--color-text-muted);
}

.metric-card__label {
  font-size: var(--type-caption);
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.metric-card__value {
  display: block;
  margin-top: var(--space-2);
  font-family: var(--font-display);
  font-size: clamp(2.75rem, 4vw, 3.5rem);
  line-height: 0.92;
  letter-spacing: -0.04em;
}

.metric-card__detail {
  max-width: 26ch;
  font-size: var(--type-small);
  line-height: 1.55;
}

.metric-card__trend {
  display: grid;
  gap: var(--space-2);
  margin-top: auto;
  color: var(--metric-accent, var(--color-primary));
}

.metric-card__trend-label {
  color: var(--color-text-muted);
  font-size: var(--type-caption);
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.metric-card__spark {
  width: 100%;
  height: 2rem;
}
</style>
