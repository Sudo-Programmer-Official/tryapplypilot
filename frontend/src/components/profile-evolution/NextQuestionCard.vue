<script setup lang="ts">
import AppBadge from "../ui/AppBadge.vue";
import AppButton from "../ui/AppButton.vue";
import AppEmptyState from "../ui/AppEmptyState.vue";
import AppSkeleton from "../ui/AppSkeleton.vue";
import AppTextArea from "../ui/AppTextArea.vue";
import type { ProfileEvolutionQuestion, ProfileEvolutionSubmissionResult } from "../../types";

const props = defineProps<{
  loading: boolean;
  error: string;
  question: ProfileEvolutionQuestion | null;
  answer: string;
  canSubmit: boolean;
  submitting: boolean;
  refreshing: boolean;
  lastResult: ProfileEvolutionSubmissionResult | null;
  completionDelta: { before: number; after: number } | null;
}>();

const emit = defineEmits<{
  "update:answer": [value: string];
  submit: [];
  refresh: [];
}>();

function formatTopicName(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function knowledgeGainEntries() {
  return Object.entries(props.lastResult?.knowledge_gain ?? {}).filter(([key, value]) => key !== "total" && Number(value) > 0);
}
</script>

<template>
  <div v-if="loading" class="profile-evolution-loading">
    <AppSkeleton class="profile-evolution-skeleton profile-evolution-skeleton--headline" />
    <AppSkeleton class="profile-evolution-skeleton" />
    <AppSkeleton class="profile-evolution-skeleton" />
    <AppSkeleton class="profile-evolution-skeleton profile-evolution-skeleton--panel" />
  </div>

  <AppEmptyState v-else-if="error" title="Profile evolution unavailable" :description="error" />

  <div v-else class="profile-evolution-stack">
    <div v-if="lastResult" class="profile-evolution-insight">
      <div class="profile-evolution-insight__header">
        <div>
          <span class="eyebrow">I understood</span>
          <strong>{{ lastResult.extracted_facts.length }} extracted facts</strong>
        </div>
        <AppBadge tone="success">Knowledge captured</AppBadge>
      </div>
      <div class="profile-evolution-tags">
        <AppBadge
          v-for="fact in lastResult.extracted_facts.slice(0, 8)"
          :key="`${fact.entity_type}-${fact.canonical_name}`"
          tone="info"
          size="sm"
        >
          {{ fact.canonical_name }}
        </AppBadge>
      </div>
      <div class="profile-evolution-insight__gain">
        <div class="profile-evolution-insight__metric">
          <span class="eyebrow">Knowledge improved</span>
          <div class="profile-evolution-tags">
            <AppBadge v-for="[key] in knowledgeGainEntries()" :key="key" tone="primary" size="sm">
              {{ formatTopicName(key) }}
            </AppBadge>
          </div>
        </div>
        <div v-if="completionDelta" class="profile-evolution-insight__metric">
          <span class="eyebrow">Profile completeness</span>
          <strong>{{ completionDelta.before }}% -> {{ completionDelta.after }}%</strong>
        </div>
      </div>
    </div>

    <div v-if="question" class="profile-evolution-question">
      <div class="profile-evolution-question__header">
        <AppBadge tone="info">{{ formatTopicName(question.topic) }}</AppBadge>
        <AppBadge tone="neutral">Confidence {{ Math.round(question.confidence * 100) }}%</AppBadge>
      </div>
      <h3>{{ question.prompt }}</h3>
      <p>{{ question.rationale }}</p>
      <div v-if="question.missing_fields.length > 0" class="profile-evolution-tags">
        <AppBadge v-for="field in question.missing_fields" :key="field" tone="neutral" size="sm">
          {{ formatTopicName(field) }}
        </AppBadge>
      </div>
      <AppTextArea
        :model-value="answer"
        label="Your answer"
        hint="Be concrete. Metrics, technologies, ownership, and business outcome create stronger evidence."
        :rows="6"
        placeholder="Example: I designed a Kubernetes-based scheduling platform on AWS with PostgreSQL that handled 90,000 jobs per day..."
        @update:model-value="emit('update:answer', String($event ?? ''))"
      />
      <div class="profile-evolution-actions">
        <AppButton :disabled="!canSubmit" @click="emit('submit')">
          {{ submitting ? "Saving answer..." : "Save answer" }}
        </AppButton>
        <AppButton variant="secondary" :disabled="refreshing" @click="emit('refresh')">
          {{ refreshing ? "Refreshing..." : "Refresh question" }}
        </AppButton>
      </div>
    </div>

    <AppEmptyState
      v-else
      title="No open profile questions"
      description="Your current knowledge coverage has no urgent follow-up prompts. New questions will appear as your profile and evidence graph evolve."
    />
  </div>
</template>

<style scoped>
.profile-evolution-loading,
.profile-evolution-stack {
  display: grid;
  gap: var(--space-5);
}

.profile-evolution-skeleton {
  min-height: 1rem;
}

.profile-evolution-skeleton--headline {
  min-height: 1.8rem;
  width: 48%;
}

.profile-evolution-skeleton--panel {
  min-height: 12rem;
  border-radius: 1.5rem;
}

.profile-evolution-insight,
.profile-evolution-question {
  display: grid;
  gap: var(--space-4);
  padding: clamp(var(--space-5), 2vw, var(--space-6));
  border-radius: 1.75rem;
}

.profile-evolution-insight {
  border: 1px solid rgba(17, 166, 131, 0.16);
  background: linear-gradient(180deg, rgba(241, 253, 249, 0.98), rgba(255, 255, 255, 0.96));
}

.profile-evolution-question {
  border: 1px solid rgba(37, 99, 255, 0.12);
  background:
    radial-gradient(circle at top right, rgba(37, 99, 255, 0.1), transparent 38%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(243, 247, 255, 0.98));
}

.profile-evolution-insight__header,
.profile-evolution-question__header,
.profile-evolution-actions,
.profile-evolution-insight__gain,
.profile-evolution-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.profile-evolution-insight__header {
  justify-content: space-between;
  align-items: flex-start;
}

.profile-evolution-insight__header strong,
.profile-evolution-insight__metric strong {
  display: block;
  margin-top: var(--space-2);
}

.profile-evolution-question h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.3rem;
  line-height: 1.2;
  letter-spacing: -0.025em;
}

.profile-evolution-question p {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.65;
}

@media (max-width: 767px) {
  .profile-evolution-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .profile-evolution-insight,
  .profile-evolution-question {
    padding: var(--space-4);
  }

  .profile-evolution-insight__header {
    flex-direction: column;
  }
}
</style>
