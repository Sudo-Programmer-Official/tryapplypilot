<script setup lang="ts">
import AppBadge from "../ui/AppBadge.vue";
import AppCard from "../ui/AppCard.vue";
import type { StatusTone } from "../../types";

defineProps<{
  title: string;
  value: string;
  tone: StatusTone;
  detail: string;
}>();
</script>

<template>
  <AppCard>
    <div class="status-card">
      <div>
        <p class="status-card__label">{{ title }}</p>
        <strong class="status-card__value">{{ value }}</strong>
      </div>
      <AppBadge :tone="tone === 'healthy' ? 'success' : tone === 'warning' ? 'warning' : tone === 'failed' ? 'danger' : 'neutral'">
        {{ tone }}
      </AppBadge>
    </div>
    <p class="status-card__detail">{{ detail }}</p>
  </AppCard>
</template>

<style scoped>
.status-card {
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

.status-card__value {
  font-family: var(--font-display);
  font-size: 1.6rem;
}
</style>
