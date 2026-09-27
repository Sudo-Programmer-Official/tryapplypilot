<script setup lang="ts">
import { ref, watch } from "vue";

import { updateUserApplicationMetadata } from "../../api/user.api";
import { useToast } from "../../composables/useToast";
import type { ApplicationRecord } from "../../types";
import { formatDateTime } from "../../utils/format";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";
import AppInput from "../ui/AppInput.vue";

const props = defineProps<{
  application: ApplicationRecord;
}>();

const emit = defineEmits<{
  (event: "updated", application: ApplicationRecord): void;
}>();

const { pushToast } = useToast();
const saving = ref(false);

const form = ref({
  recruiter_name: "",
  recruiter_email: "",
  hiring_manager: "",
  application_portal: "",
  deadline: "",
  assessment_deadline: "",
  follow_up_date: "",
  referral_source: "",
  referral_contact: "",
  salary_range: "",
  sponsorship_status: "",
});

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

function localDateTimeToIso(value: string): string {
  if (!value.trim()) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toISOString();
}

watch(
  () => props.application,
  (application) => {
    form.value = {
      recruiter_name: application.structured_metadata.recruiter_name || "",
      recruiter_email: application.structured_metadata.recruiter_email || "",
      hiring_manager: application.structured_metadata.hiring_manager || "",
      application_portal: application.structured_metadata.application_portal || "",
      deadline: isoToLocalDateTime(application.structured_metadata.deadline),
      assessment_deadline: isoToLocalDateTime(application.structured_metadata.assessment_deadline),
      follow_up_date: isoToLocalDateTime(application.structured_metadata.follow_up_date),
      referral_source: application.structured_metadata.referral_source || "",
      referral_contact: application.structured_metadata.referral_contact || "",
      salary_range: application.structured_metadata.salary_range || "",
      sponsorship_status: application.structured_metadata.sponsorship_status || "",
    };
  },
  { immediate: true },
);

async function saveMetadata(): Promise<void> {
  saving.value = true;
  try {
    const payload = await updateUserApplicationMetadata(props.application.application_id, {
      recruiter_name: form.value.recruiter_name,
      recruiter_email: form.value.recruiter_email,
      hiring_manager: form.value.hiring_manager,
      application_portal: form.value.application_portal,
      deadline: localDateTimeToIso(form.value.deadline),
      assessment_deadline: localDateTimeToIso(form.value.assessment_deadline),
      follow_up_date: localDateTimeToIso(form.value.follow_up_date),
      referral_source: form.value.referral_source,
      referral_contact: form.value.referral_contact,
      salary_range: form.value.salary_range,
      sponsorship_status: form.value.sponsorship_status,
    });
    emit("updated", payload.item);
    pushToast("Metadata updated", `${payload.item.company} now has structured submission context.`, "success");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to update application metadata.";
    pushToast("Metadata update failed", message, "error");
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <AppCard title="Submission summary" subtitle="The structured application record should become the single source of truth for recruiter context, deadlines, and submission details.">
    <div class="metadata-summary">
      <div class="metadata-summary__item">
        <span>Portal</span>
        <strong>{{ application.submission.portal || application.structured_metadata.application_portal || "Not recorded" }}</strong>
      </div>
      <div class="metadata-summary__item">
        <span>Recruiter</span>
        <strong>{{ application.structured_metadata.recruiter_name || "Not recorded" }}</strong>
      </div>
      <div class="metadata-summary__item">
        <span>Confirmation</span>
        <strong>{{ application.submission.confirmation_number || application.structured_metadata.confirmation_number || "Not recorded" }}</strong>
      </div>
      <div class="metadata-summary__item">
        <span>External ID</span>
        <strong>{{ application.submission.external_application_id || application.structured_metadata.external_application_id || "Not recorded" }}</strong>
      </div>
      <div class="metadata-summary__item">
        <span>Submission deadline</span>
        <strong>{{ formatDateTime(application.structured_metadata.deadline) }}</strong>
      </div>
      <div class="metadata-summary__item">
        <span>Follow-up due</span>
        <strong>{{ formatDateTime(application.structured_metadata.follow_up_date) }}</strong>
      </div>
    </div>
  </AppCard>

  <AppCard title="Structured metadata" subtitle="Update recruiter context, deadlines, and follow-up scheduling through one reviewable form.">
    <div class="metadata-form">
      <AppInput v-model="form.recruiter_name" label="Recruiter name" placeholder="Avery Chen" />
      <AppInput v-model="form.recruiter_email" label="Recruiter email" placeholder="avery@example.com" />
      <AppInput v-model="form.hiring_manager" label="Hiring manager" placeholder="Priya Shah" />
      <AppInput v-model="form.application_portal" label="Portal" placeholder="Greenhouse, Lever, direct apply..." />
      <AppInput v-model="form.deadline" label="Submission deadline" type="datetime-local" />
      <AppInput v-model="form.assessment_deadline" label="Assessment deadline" type="datetime-local" />
      <AppInput v-model="form.follow_up_date" label="Follow-up date" type="datetime-local" />
      <AppInput v-model="form.referral_source" label="Referral source" placeholder="Employee referral, recruiter outreach..." />
      <AppInput v-model="form.referral_contact" label="Referral contact" placeholder="Jordan Lee" />
      <AppInput v-model="form.salary_range" label="Salary range" placeholder="$180k-$220k + equity" />
      <AppInput v-model="form.sponsorship_status" label="Sponsorship status" placeholder="Not required, may require transfer..." />
    </div>

    <template #footer>
      <div class="metadata-actions">
        <AppButton variant="secondary" :disabled="saving" @click="saveMetadata">
          {{ saving ? "Saving..." : "Save metadata" }}
        </AppButton>
      </div>
    </template>
  </AppCard>
</template>

<style scoped>
.metadata-summary,
.metadata-form {
  display: grid;
  gap: var(--space-4);
}

.metadata-summary {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.metadata-form {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.metadata-summary__item {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  border-radius: 1.25rem;
  background: rgba(247, 249, 252, 0.9);
  border: 1px solid rgba(15, 29, 58, 0.08);
}

.metadata-summary__item span {
  color: var(--color-text-muted);
  font-size: var(--type-caption);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.metadata-summary__item strong {
  font-weight: 600;
  line-height: 1.5;
}

.metadata-actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 1023px) {
  .metadata-summary,
  .metadata-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .metadata-summary,
  .metadata-form {
    grid-template-columns: 1fr;
  }

  .metadata-actions {
    justify-content: stretch;
  }
}
</style>
