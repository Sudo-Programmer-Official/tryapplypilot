<script setup lang="ts">
import AppBadge from "../ui/AppBadge.vue";
import AppButton from "../ui/AppButton.vue";
import AppTextArea from "../ui/AppTextArea.vue";
import type { ProfileEvolutionChangeItem } from "../../types";
import { formatDateTime } from "../../utils/format";

defineProps<{
  item: ProfileEvolutionChangeItem;
  reviewNote: string;
  active: boolean;
}>();

const emit = defineEmits<{
  "update:reviewNote": [value: string];
  approve: [];
  reject: [];
}>();

function formatTopicName(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function firstEvidenceExcerpt(item: ProfileEvolutionChangeItem): string {
  return item.evidence[0]?.excerpt ?? "Evidence preview unavailable.";
}

function proposedFieldNames(item: ProfileEvolutionChangeItem): string[] {
  return Object.keys(item.version.new_content)
    .filter((field) => !["profile_evolution_session_id", "text", "topic"].includes(field))
    .slice(0, 8);
}
</script>

<template>
  <article class="profile-review-card">
    <div class="profile-review-card__header">
      <div class="profile-review-card__title">
        <strong>{{ item.entity?.canonical_name ?? "Suggested update" }}</strong>
        <span>{{ formatTopicName(item.entity?.entity_type ?? item.version.source) }}</span>
      </div>
      <AppBadge tone="warning">Review required</AppBadge>
    </div>
    <p class="profile-review-card__reason">{{ item.version.reason }}</p>
    <div class="profile-review-card__meta">
      <AppBadge tone="neutral" size="sm">Version {{ item.version.version_number }}</AppBadge>
      <AppBadge tone="neutral" size="sm">{{ Math.round(item.version.confidence * 100) }}% confidence</AppBadge>
      <AppBadge tone="neutral" size="sm">{{ formatDateTime(item.version.created_at) }}</AppBadge>
    </div>
    <div class="profile-review-card__content">
      <span class="eyebrow">Evidence</span>
      <p>{{ firstEvidenceExcerpt(item) }}</p>
    </div>
    <div class="profile-review-card__content">
      <span class="eyebrow">Proposed fields</span>
      <div class="profile-evolution-tags">
        <AppBadge v-for="field in proposedFieldNames(item)" :key="field" tone="primary" size="sm">
          {{ formatTopicName(field) }}
        </AppBadge>
      </div>
    </div>
    <AppTextArea
      :model-value="reviewNote"
      label="Review note"
      hint="Optional context for why you accepted or rejected this suggestion."
      :rows="2"
      placeholder="Optional"
      @update:model-value="emit('update:reviewNote', String($event ?? ''))"
    />
    <div class="profile-evolution-actions">
      <AppButton variant="success" :disabled="active" @click="emit('approve')">
        {{ active ? "Applying..." : "Approve" }}
      </AppButton>
      <AppButton variant="danger" :disabled="active" @click="emit('reject')">
        {{ active ? "Applying..." : "Reject" }}
      </AppButton>
    </div>
  </article>
</template>

<style scoped>
.profile-review-card {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-5);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: 1.5rem;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(246, 249, 253, 0.96));
  box-shadow: 0 12px 26px rgba(15, 29, 58, 0.04);
}

.profile-review-card__header,
.profile-review-card__meta,
.profile-evolution-actions,
.profile-evolution-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.profile-review-card__header {
  align-items: flex-start;
  justify-content: space-between;
}

.profile-review-card__title {
  display: grid;
  gap: var(--space-2);
}

.profile-review-card__title strong {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.3rem;
  line-height: 1.2;
  letter-spacing: -0.025em;
}

.profile-review-card__title span {
  color: var(--color-text-muted);
  font-size: var(--type-small);
}

.profile-review-card__reason,
.profile-review-card__content p {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.65;
}

.profile-review-card__content {
  display: grid;
  gap: var(--space-2);
}

.profile-review-card__content .eyebrow {
  display: block;
}

@media (max-width: 767px) {
  .profile-review-card {
    padding: var(--space-4);
  }

  .profile-review-card__header,
  .profile-evolution-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
