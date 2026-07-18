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
        <span class="eyebrow">Scheduler</span>
        <strong>{{ snapshot.stats.running ? "Running" : "Stopped" }}</strong>
      </div>
      <div>
        <span class="eyebrow">Jobs Collected</span>
        <strong>{{ snapshot.stats.jobs_collected }}</strong>
      </div>
      <div>
        <span class="eyebrow">Jobs Matched</span>
        <strong>{{ snapshot.stats.jobs_matched }}</strong>
      </div>
      <div>
        <span class="eyebrow">Telegram Sent</span>
        <strong>{{ snapshot.stats.notifications_sent }}</strong>
      </div>
      <div>
        <span class="eyebrow">Errors</span>
        <strong>{{ snapshot.stats.errors }}</strong>
      </div>
      <div>
        <span class="eyebrow">Last Poll</span>
        <strong>{{ formatDateTime(snapshot.stats.last_poll_at) }}</strong>
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
  gap: var(--content-gap);
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}

.system-status__stats strong {
  display: block;
  margin-top: var(--space-2);
  font-family: var(--font-display);
  font-size: var(--type-title);
}

.system-status__list {
  display: grid;
  gap: var(--content-gap);
}

.system-status__list li {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--content-gap);
  padding-top: var(--content-gap);
  border-top: 1px solid var(--color-border);
}

.system-status__list p {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
}
</style>
