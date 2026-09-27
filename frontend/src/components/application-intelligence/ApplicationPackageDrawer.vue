<script setup lang="ts">
import { computed, ref, watch } from "vue";

import {
  addUserApplicationNote,
  submitUserApplication,
  updateUserApplicationStatus,
  updateUserApplicationTask,
} from "../../api/user.api";
import { useToast } from "../../composables/useToast";
import type { ApplicationRecord, ApplicationTask } from "../../types";
import { formatDateTime } from "../../utils/format";
import ApplicationAssetsSection from "./ApplicationAssetsSection.vue";
import ApplicationMetadataSection from "./ApplicationMetadataSection.vue";
import ApplicationTimelineSection from "./ApplicationTimelineSection.vue";
import AppDrawer from "../ui/AppDrawer.vue";
import AppBadge from "../ui/AppBadge.vue";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";
import AppEmptyState from "../ui/AppEmptyState.vue";
import AppInput from "../ui/AppInput.vue";
import AppSelect from "../ui/AppSelect.vue";
import AppTextArea from "../ui/AppTextArea.vue";

const props = defineProps<{
  open: boolean;
  application: ApplicationRecord | null;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "updated", application: ApplicationRecord): void;
}>();

const { pushToast } = useToast();

const submitting = ref(false);
const updatingStatus = ref(false);
const savingNote = ref(false);
const taskBusyId = ref("");

const submitForm = ref({
  submitted_at: "",
  portal: "",
  confirmation_number: "",
  external_application_id: "",
  submitted_url: "",
  notes: "",
});

const statusForm = ref({
  status: "",
  notes: "",
});

const noteForm = ref({
  note_type: "general",
  body: "",
});

const taskStatusOptions = [
  { label: "Pending", value: "pending" },
  { label: "In progress", value: "in_progress" },
  { label: "Completed", value: "completed" },
  { label: "Blocked", value: "blocked" },
  { label: "Skipped", value: "skipped" },
];

function statusLabel(status: string): string {
  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function statusTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "ready_to_apply" || status === "accepted" || status === "completed") {
    return "success";
  }
  if (status === "offer" || status === "interviewing" || status === "in_progress") {
    return "info";
  }
  if (status === "rejected" || status === "withdrawn" || status === "blocked") {
    return "danger";
  }
  if (status === "applied" || status === "pending") {
    return "warning";
  }
  return "neutral";
}

function allowedStatusOptions(currentStatus: string): Array<{ label: string; value: string }> {
  if (currentStatus === "ready_to_apply") {
    return [{ label: "Withdrawn", value: "withdrawn" }];
  }
  if (currentStatus === "applied") {
    return [
      { label: "Interviewing", value: "interviewing" },
      { label: "Offer", value: "offer" },
      { label: "Rejected", value: "rejected" },
      { label: "Withdrawn", value: "withdrawn" },
    ];
  }
  if (currentStatus === "interviewing") {
    return [
      { label: "Offer", value: "offer" },
      { label: "Rejected", value: "rejected" },
      { label: "Withdrawn", value: "withdrawn" },
    ];
  }
  if (currentStatus === "offer") {
    return [
      { label: "Accepted", value: "accepted" },
      { label: "Rejected", value: "rejected" },
      { label: "Withdrawn", value: "withdrawn" },
    ];
  }
  return [];
}

function isoToLocalDateTime(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const pad = (input: number) => String(input).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function localDateTimeToIso(value: string): string | undefined {
  if (!value.trim()) {
    return undefined;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  return date.toISOString();
}

const canSubmit = computed(() => props.application?.status === "ready_to_apply" || props.application?.status === "applied");
const statusOptions = computed(() => allowedStatusOptions(props.application?.status ?? ""));
const canUpdateStatus = computed(() => Boolean(props.application && statusOptions.value.length > 0 && statusForm.value.status));

watch(
  () => props.application,
  (application) => {
    submitForm.value = {
      submitted_at: isoToLocalDateTime(application?.submission.submitted_at ?? ""),
      portal: application?.submission.portal || application?.structured_metadata.application_portal || "",
      confirmation_number: application?.submission.confirmation_number || application?.structured_metadata.confirmation_number || "",
      external_application_id: application?.submission.external_application_id || application?.structured_metadata.external_application_id || "",
      submitted_url: application?.submission.submitted_url || application?.structured_metadata.submitted_url || "",
      notes: "",
    };
    statusForm.value = {
      status: allowedStatusOptions(application?.status ?? "")[0]?.value ?? "",
      notes: "",
    };
    noteForm.value = {
      note_type: "general",
      body: "",
    };
    taskBusyId.value = "";
  },
  { immediate: true },
);

async function handleSubmitApplication(): Promise<void> {
  if (!props.application) {
    return;
  }
  submitting.value = true;
  try {
    const payload = await submitUserApplication(props.application.application_id, {
      submitted_at: localDateTimeToIso(submitForm.value.submitted_at),
      portal: submitForm.value.portal,
      confirmation_number: submitForm.value.confirmation_number,
      external_application_id: submitForm.value.external_application_id,
      submitted_url: submitForm.value.submitted_url,
      notes: submitForm.value.notes,
    });
    emit("updated", payload.item);
    pushToast("Submission recorded", `${payload.item.company} is now marked as applied.`, "success");
    submitForm.value.notes = "";
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to record application submission.";
    pushToast("Submission update failed", message, "error");
  } finally {
    submitting.value = false;
  }
}

async function handleStatusUpdate(): Promise<void> {
  if (!props.application || !statusForm.value.status) {
    return;
  }
  updatingStatus.value = true;
  try {
    const payload = await updateUserApplicationStatus(props.application.application_id, {
      status: statusForm.value.status,
      notes: statusForm.value.notes,
    });
    emit("updated", payload.item);
    pushToast("Application status updated", `${payload.item.company} is now ${statusLabel(payload.item.status).toLowerCase()}.`, "success");
    statusForm.value = {
      status: allowedStatusOptions(payload.item.status)[0]?.value ?? "",
      notes: "",
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to update application status.";
    pushToast("Status update failed", message, "error");
  } finally {
    updatingStatus.value = false;
  }
}

async function handleTaskUpdate(task: ApplicationTask, status: string): Promise<void> {
  if (!props.application) {
    return;
  }
  taskBusyId.value = `${task.task_id}:${status}`;
  try {
    const payload = await updateUserApplicationTask(props.application.application_id, task.task_id, {
      status,
      detail: task.detail,
    });
    emit("updated", payload.item);
    pushToast("Task updated", `${task.label} is now ${statusLabel(status).toLowerCase()}.`, "success");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to update application task.";
    pushToast("Task update failed", message, "error");
  } finally {
    taskBusyId.value = "";
  }
}

async function handleNoteSave(): Promise<void> {
  if (!props.application || !noteForm.value.body.trim()) {
    return;
  }
  savingNote.value = true;
  try {
    const payload = await addUserApplicationNote(props.application.application_id, {
      body: noteForm.value.body,
      note_type: noteForm.value.note_type,
    });
    emit("updated", payload.item);
    pushToast("Note saved", `Added a ${noteForm.value.note_type} note to ${payload.item.company}.`, "success");
    noteForm.value.body = "";
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to save application note.";
    pushToast("Note save failed", message, "error");
  } finally {
    savingNote.value = false;
  }
}
</script>

<template>
  <AppDrawer
    :open="open"
    side="right"
    width="lg"
    title="Application package"
    :description="application ? `${application.company} · ${application.title}` : 'Review package details, submission state, and workflow tasks.'"
    @close="$emit('close')"
  >
    <div class="application-drawer">
      <AppEmptyState
        v-if="!application"
        title="No package selected"
        description="Choose an application package to record submission details, update status, or add notes."
      />

      <template v-else>
        <AppCard class="application-drawer__hero">
          <div class="application-drawer__hero-header">
            <div class="application-drawer__hero-copy">
              <div class="application-drawer__badges">
                <AppBadge :tone="statusTone(application.status)">{{ statusLabel(application.status) }}</AppBadge>
                <AppBadge v-if="application.match_score !== null" tone="primary">{{ application.match_score }}% match</AppBadge>
                <AppBadge tone="info">{{ application.artifacts.length }} artifacts</AppBadge>
              </div>
              <p class="application-drawer__helper">
                Resume version `{{ application.resume_version_id }}` · Created {{ formatDateTime(application.created_at) }}
              </p>
              <p class="application-drawer__helper">
                {{ application.submission.submitted_at ? `Submitted ${formatDateTime(application.submission.submitted_at)}` : "Submission not recorded yet." }}
              </p>
            </div>
            <AppButton :href="application.apply_url" target="_blank" rel="noreferrer">Open apply link</AppButton>
          </div>
        </AppCard>

        <ApplicationTimelineSection
          :application="application"
        />

        <ApplicationMetadataSection
          :application="application"
          @updated="$emit('updated', $event)"
        />

        <AppCard
          title="Record submission"
          subtitle="Capture the actual submission event and confirmation details after using the official apply link."
        >
          <AppEmptyState
            v-if="!canSubmit"
            title="Submission already progressed"
            description="Use status updates and notes below to keep the package current after the initial submission."
          />

          <div v-else class="application-drawer__form-grid">
            <AppInput v-model="submitForm.submitted_at" label="Submitted at" type="datetime-local" />
            <AppInput v-model="submitForm.portal" label="Portal" placeholder="Greenhouse, Lever, company portal..." />
            <AppInput v-model="submitForm.confirmation_number" label="Confirmation number" placeholder="CONF-123" />
            <AppInput v-model="submitForm.external_application_id" label="External application ID" placeholder="APP-789" />
            <AppInput v-model="submitForm.submitted_url" label="Submission URL" placeholder="https://..." />
            <AppTextArea
              v-model="submitForm.notes"
              label="Submission note"
              :rows="4"
              placeholder="Recorded after final review on Tuesday, July 21, 2026."
            />
            <div class="application-drawer__actions">
              <AppButton variant="secondary" :disabled="submitting" @click="handleSubmitApplication">
                {{ submitting ? "Saving..." : application.status === "applied" ? "Refresh submission details" : "Record submission" }}
              </AppButton>
            </div>
          </div>
        </AppCard>

        <ApplicationAssetsSection
          :application="application"
          @updated="$emit('updated', $event)"
        />

        <AppCard
          title="Update status"
          subtitle="Move the application through valid downstream states after submission."
        >
          <div class="application-drawer__form-grid">
            <AppSelect
              v-model="statusForm.status"
              label="Next status"
              :options="statusOptions.length > 0 ? statusOptions : [{ label: 'No transitions available', value: '' }]"
              :disabled="statusOptions.length === 0"
            />
            <AppTextArea
              v-model="statusForm.notes"
              label="Status note"
              :rows="4"
              placeholder="Interview scheduled for Friday, July 24, 2026."
            />
            <div class="application-drawer__actions">
              <AppButton variant="secondary" :disabled="!canUpdateStatus || updatingStatus" @click="handleStatusUpdate">
                {{ updatingStatus ? "Updating..." : "Update status" }}
              </AppButton>
            </div>
          </div>
        </AppCard>

        <AppCard
          title="Tasks"
          subtitle="Keep generated workflow tasks accurate as you complete steps outside the platform."
        >
          <div class="application-drawer__task-list">
            <article v-for="task in application.tasks" :key="task.task_id" class="application-drawer__task">
              <div class="application-drawer__task-copy">
                <div class="application-drawer__badges">
                  <AppBadge :tone="statusTone(task.status)">{{ statusLabel(task.status) }}</AppBadge>
                  <AppBadge tone="neutral">{{ task.category }}</AppBadge>
                  <AppBadge v-if="task.due_at" tone="warning">Due {{ formatDateTime(task.due_at) }}</AppBadge>
                </div>
                <strong>{{ task.label }}</strong>
                <p class="application-drawer__helper">{{ task.detail }}</p>
              </div>
              <div class="application-drawer__task-actions">
                <AppButton
                  v-if="task.action_url"
                  variant="ghost"
                  :href="task.action_url"
                  target="_blank"
                  rel="noreferrer"
                >
                  Open
                </AppButton>
                <AppSelect
                  :model-value="task.status"
                  label=""
                  :options="taskStatusOptions"
                  :disabled="taskBusyId.startsWith(`${task.task_id}:`)"
                  @update:model-value="handleTaskUpdate(task, String($event))"
                />
              </div>
            </article>
          </div>
        </AppCard>

        <AppCard
          title="Notes"
          subtitle="Attach recruiter context, follow-up details, or manual observations to the application timeline."
        >
          <div class="application-drawer__form-grid">
            <AppSelect
              v-model="noteForm.note_type"
              label="Note type"
              :options="[
                { label: 'General', value: 'general' },
                { label: 'Follow up', value: 'follow_up' },
                { label: 'Interview', value: 'interview' },
                { label: 'Offer', value: 'offer' },
              ]"
            />
            <AppTextArea
              v-model="noteForm.body"
              label="Note"
              :rows="5"
              placeholder="Recruiter confirmed the next step and asked for availability."
            />
            <div class="application-drawer__actions">
              <AppButton variant="secondary" :disabled="savingNote || !noteForm.body.trim()" @click="handleNoteSave">
                {{ savingNote ? "Saving..." : "Add note" }}
              </AppButton>
            </div>
          </div>

          <div v-if="application.notes.length > 0" class="application-drawer__note-list">
            <article v-for="note in [...application.notes].reverse()" :key="note.note_id" class="application-drawer__note">
              <div class="application-drawer__badges">
                <AppBadge tone="info">{{ statusLabel(note.note_type) }}</AppBadge>
                <AppBadge tone="neutral">{{ formatDateTime(note.created_at) }}</AppBadge>
              </div>
              <p class="application-drawer__helper">{{ note.body }}</p>
            </article>
          </div>
        </AppCard>
      </template>
    </div>
  </AppDrawer>
</template>

<style scoped>
.application-drawer,
.application-drawer__hero-copy,
.application-drawer__form-grid,
.application-drawer__task-list,
.application-drawer__note-list {
  display: grid;
  gap: var(--space-4);
}

.application-drawer {
  padding: var(--space-5);
}

.application-drawer__hero-header,
.application-drawer__badges,
.application-drawer__actions,
.application-drawer__task-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.application-drawer__hero-header,
.application-drawer__task {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
}

.application-drawer__task,
.application-drawer__note {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: 1.25rem;
  border: 1px solid var(--color-border);
  background: var(--gradient-surface-soft);
}

.application-drawer__task-copy {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}

.application-drawer__task-copy strong {
  font-family: var(--font-display);
  letter-spacing: -0.02em;
}

.application-drawer__helper {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.6;
}

.application-drawer__task-actions {
  align-items: flex-start;
}

.application-drawer__task-actions :deep(.app-field) {
  min-width: 10rem;
}

@media (max-width: 767px) {
  .application-drawer {
    padding: var(--space-4);
  }

  .application-drawer__hero-header,
  .application-drawer__task {
    grid-template-columns: 1fr;
    display: grid;
  }

  .application-drawer__task-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
