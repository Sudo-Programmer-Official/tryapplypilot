<script setup lang="ts">
import AppBadge from "../ui/AppBadge.vue";
import AppCard from "../ui/AppCard.vue";
import type { SystemStatusSnapshot } from "../../types";
import { formatDateTime, systemStatusTone } from "../../utils/format";

defineProps<{
  snapshot: SystemStatusSnapshot;
}>();
</script>

<template>
  <AppCard title="System Status">
    <div class="system-status__stats">
      <div>
        <span class="eyebrow">Jobs Collected</span>
        <strong>{{ snapshot.stats.jobs_collected }}</strong>
      </div>
      <div>
        <span class="eyebrow">Notifications</span>
        <strong>{{ snapshot.stats.notifications_sent }}</strong>
      </div>
      <div>
        <span class="eyebrow">Next Poll</span>
        <strong>{{ formatDateTime(snapshot.stats.next_poll_at) }}</strong>
      </div>
    </div>
    <ul class="system-status__list list-reset">
      <li v-for="component in snapshot.components" :key="component.key">
        <div>
          <strong>{{ component.label }}</strong>
          <p>{{ component.detail }}</p>
        </div>
        <AppBadge :tone="systemStatusTone(component.status) === 'healthy' ? 'success' : systemStatusTone(component.status) === 'warning' ? 'warning' : systemStatusTone(component.status) === 'failed' ? 'danger' : 'neutral'">
          {{ systemStatusTone(component.status) }}
        </AppBadge>
      </li>
    </ul>
  </AppCard>
</template>

<style scoped>
.system-status__stats {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}

.system-status__stats strong {
  display: block;
  margin-top: var(--space-2);
  font-family: var(--font-display);
  font-size: 1.25rem;
}

.system-status__list {
  display: grid;
  gap: var(--space-4);
}

.system-status__list li {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.system-status__list p {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
}
</style>
