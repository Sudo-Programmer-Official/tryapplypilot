<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { fetchAdminCompanyRequests, reviewCompanyRequest } from "../../api/admin.api";
import CompanyRequestTable from "../../components/admin/CompanyRequestTable.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppCheckbox from "../../components/ui/AppCheckbox.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppModal from "../../components/ui/AppModal.vue";
import AppSelect from "../../components/ui/AppSelect.vue";
import AppSkeleton from "../../components/ui/AppSkeleton.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import { connectorOptions, countryOptions } from "../../config/options";
import { useToast } from "../../composables/useToast";
import type { CompanyRequest } from "../../types";
import { parseCsv } from "../../utils/forms";

const { pushToast } = useToast();

const requests = ref<CompanyRequest[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const selectedRequest = ref<CompanyRequest | null>(null);
const modalOpen = ref(false);
const reviewStatus = ref<"approved" | "rejected">("approved");
const adminNotes = ref("");
const connector = ref("greenhouse");
const externalIdentifier = ref("");
const careerUrl = ref("");
const tier = ref(1);
const priority = ref(90);
const pollIntervalMinutes = ref(5);
const country = ref("US");
const enabled = ref(true);
const roleFamilies = ref("Software Engineer, Backend Engineer");
const submitting = ref(false);

const pendingCount = computed(() => requests.value.filter((request) => request.status === "pending").length);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const payload = await fetchAdminCompanyRequests();
    requests.value = payload.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load company requests.";
  } finally {
    loading.value = false;
  }
}

function openReview(request: CompanyRequest, status: "approved" | "rejected"): void {
  selectedRequest.value = request;
  reviewStatus.value = status;
  adminNotes.value = request.admin_notes || "";
  connector.value = request.connector_suggestion || "greenhouse";
  externalIdentifier.value = request.external_identifier_suggestion || request.company_name.toLowerCase().replace(/\s+/g, "-");
  careerUrl.value = request.career_url || "";
  tier.value = 1;
  priority.value = 90;
  pollIntervalMinutes.value = 5;
  country.value = "US";
  enabled.value = status === "approved";
  roleFamilies.value = "Software Engineer, Backend Engineer";
  modalOpen.value = true;
}

async function submitReview(): Promise<void> {
  if (!selectedRequest.value) {
    return;
  }
  submitting.value = true;
  try {
    await reviewCompanyRequest(selectedRequest.value.id, {
      status: reviewStatus.value,
      admin_notes: adminNotes.value,
      connector: connector.value,
      external_identifier: externalIdentifier.value,
      career_url: careerUrl.value,
      tier: tier.value,
      priority: priority.value,
      poll_interval_minutes: pollIntervalMinutes.value,
      country: country.value,
      enabled: enabled.value,
      role_families: parseCsv(roleFamilies.value),
    });
    pushToast("Request reviewed", `${selectedRequest.value.company_name} was ${reviewStatus.value}.`, "success");
    modalOpen.value = false;
    await load();
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to review request.";
    pushToast("Review failed", message, "error");
  } finally {
    submitting.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppPage class="admin-requests-page">
    <PageHeader title="Company requests" description="Approve or reject user-submitted company requests without touching the database directly." />

    <PageSection class="admin-requests-page__summary-section">
      <div class="admin-requests-summary surface-card">
        <div class="admin-requests-summary__item">
          <strong>{{ requests.length }}</strong>
          <span>total requests</span>
        </div>
        <div class="admin-requests-summary__item">
          <strong>{{ pendingCount }}</strong>
          <span>pending review</span>
        </div>
      </div>
    </PageSection>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Company requests unavailable" :description="error" />
      </AppGrid>
    </PageSection>

    <PageSection v-else-if="loading">
      <AppGrid columns="1">
        <AppCard class="admin-requests-panel" title="Loading request queue">
          <div class="admin-requests-loading">
            <div v-for="index in 4" :key="index" class="admin-requests-loading__row">
              <AppSkeleton class="admin-requests-loading__title" />
              <AppSkeleton class="admin-requests-loading__meta" />
            </div>
          </div>
        </AppCard>
      </AppGrid>
    </PageSection>

    <PageSection v-else>
      <AppGrid columns="1">
        <CompanyRequestTable
          :requests="requests"
          :show-actions="true"
          @approve="openReview($event, 'approved')"
          @reject="openReview($event, 'rejected')"
          @edit="openReview($event, 'approved')"
          @merge="openReview($event, 'approved')"
        />
      </AppGrid>
    </PageSection>

    <AppModal
      :open="modalOpen"
      title="Review company request"
      description="Finalize the connector and catalog metadata before approving or rejecting the request."
      @close="modalOpen = false"
    >
      <div class="app-form-grid">
        <AppSelect
          :model-value="reviewStatus"
          label="Decision"
          :options="[
            { label: 'Approve', value: 'approved' },
            { label: 'Reject', value: 'rejected' },
          ]"
          @update:model-value="reviewStatus = $event as 'approved' | 'rejected'"
        />
        <AppSelect :model-value="connector" label="Connector" :options="connectorOptions" @update:model-value="connector = $event" />
        <AppSelect :model-value="country" label="Country" :options="countryOptions" @update:model-value="country = $event" />
        <AppInput v-model="externalIdentifier" label="External identifier" placeholder="databricks" />
        <AppInput v-model="careerUrl" label="Career URL" placeholder="https://..." />
        <AppInput :model-value="tier" label="Tier" type="number" :min="1" :max="5" @update:model-value="tier = Number($event) || 1" />
        <AppInput :model-value="priority" label="Priority" type="number" :min="1" :max="100" @update:model-value="priority = Number($event) || 90" />
        <AppInput
          :model-value="pollIntervalMinutes"
          label="Poll interval"
          type="number"
          :min="1"
          @update:model-value="pollIntervalMinutes = Number($event) || 5"
        />
        <AppCheckbox :model-value="enabled" label="Enable on approval" @update:model-value="enabled = $event" />
        <AppTextArea v-model="roleFamilies" label="Role families" :rows="3" />
        <AppTextArea v-model="adminNotes" label="Admin notes" :rows="4" />
        <AppButton :disabled="submitting" @click="submitReview">{{ submitting ? "Saving..." : "Submit review" }}</AppButton>
      </div>
    </AppModal>
  </AppPage>
</template>

<style scoped>
.admin-requests-page {
  --page-gap: var(--space-5);
}

.admin-requests-page__summary-section {
  margin-bottom: calc(var(--space-2) * -1);
}

.admin-requests-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  padding: clamp(var(--space-4), 2vw, var(--space-5));
}

.admin-requests-summary__item,
.admin-requests-loading__row {
  display: grid;
  gap: var(--space-2);
}

.admin-requests-summary__item strong {
  font-family: var(--font-display);
  font-size: clamp(1.2rem, 1.8vw, 1.45rem);
  letter-spacing: -0.03em;
}

.admin-requests-summary__item span {
  color: var(--color-text-muted);
  font-size: 0.92rem;
}

.admin-requests-panel :deep(.app-card__header) {
  padding: clamp(var(--space-6), 3vw, 2.25rem) clamp(var(--space-6), 4vw, 2.5rem) 0;
}

.admin-requests-panel :deep(.app-card__body) {
  padding: var(--space-5) clamp(var(--space-6), 4vw, 2.5rem) clamp(var(--space-6), 4vw, 2.25rem);
}

.admin-requests-loading {
  display: grid;
  gap: var(--space-4);
}

.admin-requests-loading__row {
  padding: var(--space-5);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(246, 249, 253, 0.98));
}

.admin-requests-loading__title {
  min-height: 1.2rem;
  max-width: 36%;
}

.admin-requests-loading__meta {
  min-height: 1rem;
}

@media (max-width: 767px) {
  .admin-requests-summary {
    grid-template-columns: 1fr;
  }
}
</style>
