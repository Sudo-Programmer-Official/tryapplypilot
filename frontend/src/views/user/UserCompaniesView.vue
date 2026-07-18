<script setup lang="ts">
import { onMounted, ref } from "vue";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppCheckbox from "../../components/ui/AppCheckbox.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppSelect from "../../components/ui/AppSelect.vue";
import AppTable from "../../components/ui/AppTable.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import { createUserCompanyRequest, fetchUserCompanies, fetchUserCompanyRequests } from "../../api/user.api";
import { companyPriorityOptions } from "../../config/options";
import { useAuth } from "../../composables/useAuth";
import { usePreferences } from "../../composables/usePreferences";
import { useToast } from "../../composables/useToast";
import type { CompanyPreference, CompanyRequest, TableColumn } from "../../types";
import { formatDate } from "../../utils/format";

const auth = useAuth();
const { pushToast } = useToast();
const { draft, saving, savePreferences } = usePreferences(auth.user);

const companies = ref<CompanyPreference[]>([]);
const requests = ref<CompanyRequest[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const requestCompanyName = ref("");
const requestCareerUrl = ref("");
const requestConnector = ref("greenhouse");
const requestIdentifier = ref("");
const requestNotes = ref("");

const requestColumns: TableColumn[] = [
  { key: "company", label: "Company" },
  { key: "status", label: "Status" },
  { key: "requestedOn", label: "Requested On" },
];

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [companiesPayload, requestsPayload] = await Promise.all([fetchUserCompanies(), fetchUserCompanyRequests()]);
    companies.value = companiesPayload.items.filter((company) => company.enabled);
    requests.value = requestsPayload.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load company data.";
  } finally {
    loading.value = false;
  }
}

function toggleCompany(companyName: string): void {
  const current = draft.value.company_priorities[companyName] ?? "hidden";
  const next = current === "hidden" ? "normal" : "hidden";
  setCompanyPriority(companyName, next);
}

function setCompanyPriority(companyName: string, value: string): void {
  draft.value.company_priorities = {
    ...draft.value.company_priorities,
    [companyName]: value as "dream" | "high" | "normal" | "hidden",
  };
  draft.value.preferred_companies = Object.entries(draft.value.company_priorities)
    .filter(([, priority]) => priority !== "hidden")
    .map(([company]) => company);
}

async function saveSelections(): Promise<void> {
  await savePreferences(auth.setUser);
  pushToast("Company preferences saved", "Your monitored company list has been updated.", "success");
}

async function submitRequest(): Promise<void> {
  try {
    const payload = await createUserCompanyRequest({
      company_name: requestCompanyName.value,
      career_url: requestCareerUrl.value,
      connector_suggestion: requestConnector.value,
      external_identifier_suggestion: requestIdentifier.value,
      notes: requestNotes.value,
    });
    requests.value = [payload.item, ...requests.value];
    requestCompanyName.value = "";
    requestCareerUrl.value = "";
    requestConnector.value = "greenhouse";
    requestIdentifier.value = "";
    requestNotes.value = "";
    pushToast("Company request submitted", "The admin queue has the new company request.", "success");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to submit company request.";
    pushToast("Company request failed", message, "error");
  }
}

onMounted(load);
</script>

<template>
  <AppPage>
    <PageHeader
      title="Target companies"
      description="Choose the companies you want monitored for your account, then request anything missing from the catalog."
    >
      <template #actions>
        <AppButton :disabled="saving" @click="saveSelections">{{ saving ? "Saving..." : "Save selections" }}</AppButton>
      </template>
    </PageHeader>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Companies unavailable" :description="error" />
      </AppGrid>
    </PageSection>

    <PageSection v-else>
      <AppGrid columns="2">
        <AppCard title="Catalog companies" :subtitle="`${draft.preferred_companies.length} selected for your account.`">
          <AppEmptyState
            v-if="!loading && companies.length === 0"
            title="No companies in the catalog"
            description="Ask an admin to seed the catalog or submit your first request below."
          />
          <div v-else class="app-form-grid">
            <div v-for="company in companies" :key="company.id" class="company-row">
              <AppCheckbox
                :model-value="draft.preferred_companies.includes(company.company)"
                :label="company.company"
                @update:model-value="toggleCompany(company.company)"
              />
              <AppSelect
                :model-value="draft.company_priorities[company.company] ?? (draft.preferred_companies.includes(company.company) ? 'normal' : 'hidden')"
                :options="companyPriorityOptions"
                @update:model-value="setCompanyPriority(company.company, String($event || 'hidden'))"
              />
              <span class="company-row__meta">
                {{ company.connector }} · tier {{ company.tier }} · {{ company.country }}
              </span>
            </div>
          </div>
        </AppCard>

        <AppCard title="Request a company" subtitle="Use this when the company you want is not in the current catalog.">
          <div class="app-form-grid">
            <AppInput v-model="requestCompanyName" label="Company name" placeholder="OpenAI" />
            <AppInput v-model="requestCareerUrl" label="Career URL" placeholder="https://..." />
            <AppInput v-model="requestConnector" label="Suggested connector" placeholder="greenhouse" />
            <AppInput v-model="requestIdentifier" label="External identifier" placeholder="openai" />
            <AppTextArea
              v-model="requestNotes"
              label="Notes"
              placeholder="Why this company matters, preferred teams, or board hints."
              :rows="4"
            />
            <AppButton @click="submitRequest">Submit request</AppButton>
          </div>
        </AppCard>
      </AppGrid>
    </PageSection>

    <PageSection v-if="!error">
      <AppGrid columns="1">
        <AppCard title="Your requests" subtitle="Track approvals and rejections without needing direct admin help.">
          <AppTable :columns="requestColumns" :has-rows="requests.length > 0" empty-message="No company requests yet.">
            <tr v-for="request in requests" :key="request.id">
              <td class="app-table__copy">
                <strong>{{ request.company_name }}</strong>
                <p>{{ request.connector_suggestion || "No connector hint" }}</p>
              </td>
              <td>{{ request.status }}</td>
              <td>{{ formatDate(request.created_at) }}</td>
            </tr>
          </AppTable>
        </AppCard>
      </AppGrid>
    </PageSection>
  </AppPage>
</template>

<style scoped>
.company-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--content-gap);
  padding-bottom: var(--content-gap);
  border-bottom: 1px solid var(--color-border);
}

.company-row__meta {
  color: var(--color-text-muted);
  font-size: var(--type-small);
}
</style>
