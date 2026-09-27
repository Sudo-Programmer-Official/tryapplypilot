<script setup lang="ts">
import { computed, ref } from "vue";

import { addUserApplicationAnswer, addUserApplicationArtifact } from "../../api/user.api";
import { useToast } from "../../composables/useToast";
import type { ApplicationPackageArtifact, ApplicationRecord } from "../../types";
import { formatDateTime } from "../../utils/format";
import AppBadge from "../ui/AppBadge.vue";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";
import AppEmptyState from "../ui/AppEmptyState.vue";
import AppInput from "../ui/AppInput.vue";
import AppSelect from "../ui/AppSelect.vue";
import AppTextArea from "../ui/AppTextArea.vue";

const props = defineProps<{
  application: ApplicationRecord;
}>();

const emit = defineEmits<{
  (event: "updated", application: ApplicationRecord): void;
}>();

const { pushToast } = useToast();
const savingAnswer = ref(false);
const savingArtifact = ref(false);

const answerForm = ref({
  question: "",
  question_key: "",
  answer: "",
  reusable: "yes",
});

const artifactForm = ref({
  kind: "supporting_document",
  title: "",
  url: "",
  detail: "",
});

const listedArtifacts = computed(() =>
  [...props.application.artifacts]
    .filter((artifact) => artifact.kind !== "application_answer")
    .reverse(),
);

const listedAnswers = computed(() => [...props.application.answers].reverse());

function kindLabel(kind: string): string {
  return kind
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function artifactTone(artifact: ApplicationPackageArtifact): "success" | "warning" | "danger" | "info" | "neutral" {
  if (artifact.kind === "confirmation" || artifact.kind === "resume") {
    return "success";
  }
  if (artifact.kind === "supporting_document") {
    return "info";
  }
  if (artifact.kind === "external_link") {
    return "warning";
  }
  return "neutral";
}

async function saveAnswer(): Promise<void> {
  if (!answerForm.value.question.trim() || !answerForm.value.answer.trim()) {
    return;
  }
  savingAnswer.value = true;
  try {
    const payload = await addUserApplicationAnswer(props.application.application_id, {
      question: answerForm.value.question,
      question_key: answerForm.value.question_key,
      answer: answerForm.value.answer,
      source: "user_manual",
      reusable: answerForm.value.reusable === "yes",
      sensitive_data: false,
      user_approved: true,
    });
    emit("updated", payload.item);
    pushToast("Answer saved", `Added a structured answer to ${payload.item.company}.`, "success");
    answerForm.value = {
      question: "",
      question_key: "",
      answer: "",
      reusable: "yes",
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to save application answer.";
    pushToast("Answer save failed", message, "error");
  } finally {
    savingAnswer.value = false;
  }
}

async function saveArtifact(): Promise<void> {
  if (!artifactForm.value.kind.trim() || !artifactForm.value.title.trim()) {
    return;
  }
  savingArtifact.value = true;
  try {
    const payload = await addUserApplicationArtifact(props.application.application_id, {
      kind: artifactForm.value.kind,
      title: artifactForm.value.title,
      source: "manual_upload",
      status: "ready",
      url: artifactForm.value.url,
      detail: artifactForm.value.detail,
    });
    emit("updated", payload.item);
    pushToast("Artifact attached", `Added ${artifactForm.value.title} to ${payload.item.company}.`, "success");
    artifactForm.value = {
      kind: "supporting_document",
      title: "",
      url: "",
      detail: "",
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to attach application artifact.";
    pushToast("Artifact attach failed", message, "error");
  } finally {
    savingArtifact.value = false;
  }
}
</script>

<template>
  <AppCard title="Answers" subtitle="Keep structured answers attached to the application so later submission details remain grounded in the record.">
    <div class="assets-form">
      <AppInput v-model="answerForm.question" label="Question" placeholder="Why do you want to work here?" />
      <AppInput v-model="answerForm.question_key" label="Question key" placeholder="why_company" />
      <AppSelect
        v-model="answerForm.reusable"
        label="Reusable"
        :options="[
          { label: 'Yes', value: 'yes' },
          { label: 'No', value: 'no' },
        ]"
      />
      <AppTextArea
        v-model="answerForm.answer"
        label="Answer"
        :rows="5"
        placeholder="I want to work on high-scale platform systems with strong product ownership."
      />
    </div>

    <template #footer>
      <div class="assets-actions">
        <AppButton variant="secondary" :disabled="savingAnswer || !answerForm.question.trim() || !answerForm.answer.trim()" @click="saveAnswer">
          {{ savingAnswer ? "Saving..." : "Save answer" }}
        </AppButton>
      </div>
    </template>

    <div v-if="listedAnswers.length > 0" class="assets-list">
      <article v-for="answer in listedAnswers" :key="answer.answer_id" class="assets-item">
        <div class="assets-item__header">
          <div class="assets-badges">
            <AppBadge tone="info">{{ answer.normalized_question_key }}</AppBadge>
            <AppBadge :tone="answer.reusable ? 'success' : 'neutral'">{{ answer.reusable ? "Reusable" : "One-off" }}</AppBadge>
          </div>
          <span class="assets-item__time">{{ formatDateTime(answer.created_at) }}</span>
        </div>
        <strong>{{ answer.question }}</strong>
        <p>{{ answer.answer }}</p>
      </article>
    </div>
    <AppEmptyState
      v-else
      title="No answers saved"
      description="Structured answers will also create answer artifacts so future submissions do not rely on memory."
    />
  </AppCard>

  <AppCard title="Artifacts" subtitle="Attach supporting references and keep the submission package auditable beyond the resume PDF.">
    <div class="assets-form">
      <AppSelect
        v-model="artifactForm.kind"
        label="Artifact kind"
        :options="[
          { label: 'Supporting document', value: 'supporting_document' },
          { label: 'Cover letter', value: 'cover_letter' },
          { label: 'Portfolio link', value: 'portfolio_link' },
          { label: 'Work authorization', value: 'work_authorization' },
          { label: 'Other', value: 'other' },
        ]"
      />
      <AppInput v-model="artifactForm.title" label="Title" placeholder="Visa support letter" />
      <AppInput v-model="artifactForm.url" label="URL" placeholder="https://..." />
      <AppTextArea
        v-model="artifactForm.detail"
        label="Detail"
        :rows="4"
        placeholder="Optional supporting document reference or context."
      />
    </div>

    <template #footer>
      <div class="assets-actions">
        <AppButton variant="secondary" :disabled="savingArtifact || !artifactForm.title.trim()" @click="saveArtifact">
          {{ savingArtifact ? "Attaching..." : "Attach artifact" }}
        </AppButton>
      </div>
    </template>

    <div v-if="listedArtifacts.length > 0" class="assets-list">
      <article v-for="artifact in listedArtifacts" :key="artifact.artifact_id" class="assets-item">
        <div class="assets-item__header">
          <div class="assets-badges">
            <AppBadge :tone="artifactTone(artifact)">{{ kindLabel(artifact.kind) }}</AppBadge>
            <AppBadge tone="neutral">{{ artifact.status }}</AppBadge>
          </div>
          <span class="assets-item__time">{{ formatDateTime(artifact.created_at) }}</span>
        </div>
        <strong>{{ artifact.label }}</strong>
        <p>{{ artifact.detail || artifact.file_name || artifact.url || "No additional detail recorded." }}</p>
      </article>
    </div>
    <AppEmptyState
      v-else
      title="No extra artifacts attached"
      description="Resume, apply link, confirmation, and future supporting documents will all live on the application record."
    />
  </AppCard>
</template>

<style scoped>
.assets-form,
.assets-list {
  display: grid;
  gap: var(--space-4);
}

.assets-form {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.assets-actions,
.assets-badges,
.assets-item__header {
  display: flex;
  gap: var(--space-3);
}

.assets-actions,
.assets-item__header {
  justify-content: space-between;
  align-items: flex-start;
}

.assets-item {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: 1.25rem;
  border: 1px solid rgba(15, 29, 58, 0.08);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(246, 249, 253, 0.96));
}

.assets-item strong,
.assets-item p {
  margin: 0;
}

.assets-item p,
.assets-item__time {
  color: var(--color-text-muted);
  line-height: 1.6;
}

@media (max-width: 767px) {
  .assets-form {
    grid-template-columns: 1fr;
  }

  .assets-actions,
  .assets-item__header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
