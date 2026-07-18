<script setup lang="ts">
import { computed } from "vue";

import AppBadge from "../ui/AppBadge.vue";
import AppCard from "../ui/AppCard.vue";
import type { StatusTone } from "../../types";

const props = defineProps<{
  title: string;
  value: string;
  tone: StatusTone;
  detail: string;
}>();

const badgeTone = computed(() => {
  if (props.tone === "healthy") {
    return "success";
  }
  if (props.tone === "warning") {
    return "warning";
  }
  if (props.tone === "failed") {
    return "danger";
  }
  if (props.tone === "info") {
    return "info";
  }
  return "neutral";
});

const badgeLabel = computed(() => {
  if (props.tone === "healthy") {
    return "Ready";
  }
  if (props.tone === "warning") {
    return "Attention";
  }
  if (props.tone === "failed") {
    return "Issue";
  }
  if (props.tone === "inactive") {
    return "Inactive";
  }
  return "Info";
});
</script>

<template>
  <AppCard class="status-card-panel">
    <div class="status-card">
      <div class="status-card__header">
        <p class="status-card__label">{{ title }}</p>
        <AppBadge :tone="badgeTone" size="sm">
          {{ badgeLabel }}
        </AppBadge>
      </div>
      <strong class="status-card__value">{{ value }}</strong>
      <p class="status-card__detail">{{ detail }}</p>
    </div>
  </AppCard>
</template>

<style scoped>
.status-card-panel :deep(.app-card__body) {
  height: 100%;
}

.status-card {
  display: grid;
  gap: var(--space-3);
  align-content: start;
}

.status-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.status-card__label,
.status-card__detail {
  margin: 0;
  color: var(--color-text-muted);
}

.status-card__label {
  font-size: var(--type-caption);
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.status-card__value {
  display: block;
  font-family: var(--font-display);
  font-size: clamp(2rem, 3vw, 2.7rem);
  line-height: 0.95;
  letter-spacing: -0.04em;
}

.status-card__detail {
  max-width: 28ch;
  font-size: var(--type-small);
  line-height: 1.55;
}
</style>
