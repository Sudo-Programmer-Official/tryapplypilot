<script setup lang="ts">
import { computed } from "vue";

import type { ApplicationRecord, ApplicationTimelineEvent } from "../../types";
import { formatDateTime } from "../../utils/format";
import AppBadge from "../ui/AppBadge.vue";
import AppCard from "../ui/AppCard.vue";
import AppEmptyState from "../ui/AppEmptyState.vue";

const props = defineProps<{
  application: ApplicationRecord;
}>();

const timelineItems = computed(() => [...props.application.timeline].reverse());

function eventTone(event: ApplicationTimelineEvent): "success" | "warning" | "danger" | "info" | "neutral" {
  if (event.event_type === "ApplicationSubmitted" || event.event_type === "ConfirmationRecorded") {
    return "success";
  }
  if (event.event_type === "DeadlineAdded" || event.event_type === "FollowUpScheduled") {
    return "warning";
  }
  if (event.event_type === "StatusChanged" && /rejected|withdrawn/i.test(event.label)) {
    return "danger";
  }
  if (event.event_type === "MetadataUpdated" || event.event_type === "TaskUpdated" || event.event_type === "AnswerSaved") {
    return "info";
  }
  return "neutral";
}

function eventLabel(eventType: string): string {
  return eventType
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ");
}
</script>

<template>
  <AppCard title="Timeline" subtitle="Use the application timeline as the primary activity feed for everything that has happened on this package.">
    <div v-if="timelineItems.length > 0" class="timeline-list">
      <article v-for="item in timelineItems" :key="`${item.event_type}-${item.occurred_at}-${item.label}`" class="timeline-item">
        <div class="timeline-item__header">
          <div class="timeline-item__badges">
            <AppBadge :tone="eventTone(item)">{{ eventLabel(item.event_type) }}</AppBadge>
            <AppBadge tone="neutral">{{ formatDateTime(item.occurred_at) }}</AppBadge>
          </div>
          <strong>{{ item.label }}</strong>
        </div>
        <p v-if="item.detail" class="timeline-item__detail">{{ item.detail }}</p>
      </article>
    </div>
    <AppEmptyState
      v-else
      title="No timeline activity yet"
      description="Every package action should write back into the timeline so the application record remains explainable."
    />
  </AppCard>
</template>

<style scoped>
.timeline-list {
  display: grid;
  gap: var(--space-4);
}

.timeline-item {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: 1.25rem;
  border: 1px solid var(--color-border);
  background: var(--gradient-surface-soft);
}

.timeline-item__header,
.timeline-item__badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.timeline-item__header {
  justify-content: space-between;
  align-items: flex-start;
}

.timeline-item__detail {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.6;
}

@media (max-width: 767px) {
  .timeline-item__header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
