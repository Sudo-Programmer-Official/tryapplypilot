<script setup lang="ts">
import AppBadge from "../ui/AppBadge.vue";

defineProps<{
  completionPercent: number;
  currentTopic: string | null;
  pendingTopicsCount: number;
  queuedChangesCount: number;
}>();

function formatTopicName(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}
</script>

<template>
  <div class="profile-evolution-summary">
    <div class="profile-evolution-summary__metric">
      <span class="eyebrow">Current focus</span>
      <strong>{{ currentTopic ? formatTopicName(currentTopic) : "All topics covered" }}</strong>
    </div>
    <div class="profile-evolution-summary__metric">
      <span class="eyebrow">Pending topics</span>
      <strong>{{ pendingTopicsCount }}</strong>
    </div>
    <div class="profile-evolution-summary__metric">
      <span class="eyebrow">Queued changes</span>
      <strong>{{ queuedChangesCount }}</strong>
    </div>
    <div class="profile-evolution-summary__metric profile-evolution-summary__metric--wide">
      <div class="profile-evolution-summary__header">
        <span class="eyebrow">Guided interview</span>
        <AppBadge tone="primary">{{ completionPercent }}% complete</AppBadge>
      </div>
      <p>
        This flow is not chat. It asks one high-value question, extracts facts, stages evidence-backed changes, and then asks the next question.
      </p>
    </div>
  </div>
</template>

<style scoped>
.profile-evolution-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.profile-evolution-summary__metric {
  padding: var(--space-5);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(246, 249, 253, 0.96));
  box-shadow: 0 12px 26px rgba(15, 29, 58, 0.04);
}

.profile-evolution-summary__metric strong {
  display: block;
  margin-top: var(--space-2);
  font-size: 1rem;
  line-height: 1.35;
}

.profile-evolution-summary__metric--wide {
  grid-column: 1 / -1;
}

.profile-evolution-summary__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.profile-evolution-summary__metric p {
  margin: var(--space-3) 0 0;
  color: var(--color-text-muted);
  line-height: 1.65;
}

@media (max-width: 1023px) {
  .profile-evolution-summary {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .profile-evolution-summary__metric {
    padding: var(--space-4);
  }

  .profile-evolution-summary__header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
