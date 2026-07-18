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
    <div class="metric-card__header">
      <span class="metric-card__icon" :class="`metric-card__icon--${tone ?? 'primary'}`">
        <component :is="icon" />
      </span>
      <div>
        <p class="metric-card__label">{{ label }}</p>
        <strong class="metric-card__value">{{ value }}</strong>
      </div>
    </div>
    <p class="metric-card__detail">{{ detail }}</p>
    <svg v-if="sparkline?.length" class="metric-card__spark" viewBox="0 0 120 28" preserveAspectRatio="none">
      <polyline
        :points="sparklinePoints"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  </AppCard>
</template>

<style scoped>
.metric-card {
  height: 100%;
}

.metric-card__header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.metric-card__icon {
  display: grid;
  place-items: center;
  width: 4.5rem;
  height: 4.5rem;
  border-radius: 1.5rem;
}

.metric-card__icon :deep(svg) {
  width: 48px;
  height: 48px;
}

.metric-card__icon--primary {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.metric-card__icon--success {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.metric-card__icon--warning {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.metric-card__icon--info {
  background: var(--color-info-soft);
  color: var(--color-info);
}

.metric-card__label,
.metric-card__detail {
  margin: 0;
  color: var(--color-text-muted);
}

.metric-card__value {
  display: block;
  margin-top: var(--space-1);
  font-family: var(--font-display);
  font-size: var(--type-display);
  letter-spacing: -0.04em;
}

.metric-card__spark {
  width: 100%;
  height: 1.75rem;
  color: var(--color-primary);
}
</style>
