<script setup lang="ts">
import AppCard from "../ui/AppCard.vue";
import type { ProfileEvolutionQuestion, ProfileEvolutionSubmissionResult } from "../../types";
import NextQuestionCard from "./NextQuestionCard.vue";
import ProfileCompletenessCard from "./ProfileCompletenessCard.vue";

defineProps<{
  loading: boolean;
  error: string;
  question: ProfileEvolutionQuestion | null;
  answer: string;
  canSubmit: boolean;
  submitting: boolean;
  refreshing: boolean;
  completionPercent: number;
  currentTopic: string | null;
  pendingTopicsCount: number;
  queuedChangesCount: number;
  lastResult: ProfileEvolutionSubmissionResult | null;
  completionDelta: { before: number; after: number } | null;
}>();

const emit = defineEmits<{
  "update:answer": [value: string];
  submit: [];
  refresh: [];
}>();
</script>

<template>
  <AppCard
    class="profile-panel profile-evolution-panel"
    title="Profile evolution"
    subtitle="Answer one focused question at a time. Each response becomes staged, evidence-backed knowledge instead of disappearing into chat history."
  >
    <ProfileCompletenessCard
      :completion-percent="completionPercent"
      :current-topic="currentTopic"
      :pending-topics-count="pendingTopicsCount"
      :queued-changes-count="queuedChangesCount"
    />
    <NextQuestionCard
      :loading="loading"
      :error="error"
      :question="question"
      :answer="answer"
      :can-submit="canSubmit"
      :submitting="submitting"
      :refreshing="refreshing"
      :last-result="lastResult"
      :completion-delta="completionDelta"
      @update:answer="emit('update:answer', $event)"
      @submit="emit('submit')"
      @refresh="emit('refresh')"
    />
  </AppCard>
</template>
