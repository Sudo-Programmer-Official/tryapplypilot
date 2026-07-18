<script setup lang="ts">
import { onMounted, ref } from "vue";

import CompanyRequestTable from "../../components/admin/CompanyRequestTable.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCheckbox from "../../components/ui/AppCheckbox.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppModal from "../../components/ui/AppModal.vue";
import AppSelect from "../../components/ui/AppSelect.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import { fetchAdminCompanyRequests, reviewCompanyRequest } from "../../api/admin.api";
import { connectorOptions, countryOptions } from "../../config/options";
import { useToast } from "../../composables/useToast";
import type { CompanyRequest } from "../../types";
import { joinCsv, parseCsv } from "../../utils/forms";

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
  <AppPage>
    <PageHeader title="Company requests" description="Approve or reject user-submitted company requests without touching the database directly." />

    <CompanyRequestTable
      v-if="!error"
      :requests="requests"
      :show-actions="true"
      @approve="openReview($event, 'approved')"
      @reject="openReview($event, 'rejected')"
      @edit="openReview($event, 'approved')"
      @merge="openReview($event, 'approved')"
    />

    <AppCard v-else title="Company requests unavailable" :subtitle="error" />

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
