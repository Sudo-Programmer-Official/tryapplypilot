<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppCheckbox from "../../components/ui/AppCheckbox.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppSelect from "../../components/ui/AppSelect.vue";
import AppTable from "../../components/ui/AppTable.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import { createUserCompanyRequest, fetchUserCompanies, fetchUserCompanyRequests } from "../../api/user.api";
import { companyPriorityOptions, connectorOptions } from "../../config/options";
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

const selectedCompanies = computed(() => draft.value.preferred_companies ?? []);
const selectedCount = computed(() => selectedCompanies.value.length);
const pendingRequestCount = computed(() => requests.value.filter((request) => request.status === "pending").length);
const sortedCompanies = computed(() =>
  [...companies.value].sort((left, right) => {
    const leftSelected = selectedCompanies.value.includes(left.company);
    const rightSelected = selectedCompanies.value.includes(right.company);
    if (leftSelected !== rightSelected) {
      return Number(rightSelected) - Number(leftSelected);
    }
    const leftPriority = draft.value.company_priorities[left.company] ?? "hidden";
    const rightPriority = draft.value.company_priorities[right.company] ?? "hidden";
    const rank = (value: string) => {
      if (value === "dream") {
        return 0;
      }
      if (value === "high") {
        return 1;
      }
      if (value === "normal") {
        return 2;
      }
      return 3;
    };
    return rank(leftPriority) - rank(rightPriority) || left.company.localeCompare(right.company);
  }),
);

function isCompanySelected(companyName: string): boolean {
  return selectedCompanies.value.includes(companyName);
}

function requestStatusTone(status: CompanyRequest["status"]): "warning" | "success" | "danger" {
  if (status === "approved") {
    return "success";
  }
  if (status === "rejected") {
    return "danger";
  }
  return "warning";
}

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
  <AppPage class="companies-page">
    <PageSection class="companies-summary-section">
      <div class="companies-summary surface-card">
        <div class="companies-summary__copy">
          <strong>{{ selectedCount }} selected</strong>
          <span>{{ companies.length }} catalog companies</span>
          <span>{{ pendingRequestCount }} pending requests</span>
        </div>
        <AppButton :disabled="saving" @click="saveSelections">{{ saving ? "Saving..." : "Save selections" }}</AppButton>
      </div>
    </PageSection>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Companies unavailable" :description="error" />
      </AppGrid>
    </PageSection>

    <PageSection v-else>
      <AppGrid columns="2" class="companies-grid">
        <AppCard class="companies-panel" title="Catalog companies" :subtitle="`${selectedCount} selected for your account.`">
          <AppEmptyState
            v-if="!loading && companies.length === 0"
            title="No companies in the catalog"
            description="Ask an admin to seed the catalog or submit your first request below."
          />
          <div v-else class="company-list">
            <div
              v-for="company in sortedCompanies"
              :key="company.id"
              class="company-row"
              :class="{ 'company-row--active': isCompanySelected(company.company) }"
            >
              <div class="company-row__toggle">
                <AppCheckbox
                  :model-value="isCompanySelected(company.company)"
                  :label="company.company"
                  @update:model-value="toggleCompany(company.company)"
                />
              </div>
              <AppSelect
                class="company-row__priority"
                :model-value="draft.company_priorities[company.company] ?? (isCompanySelected(company.company) ? 'normal' : 'hidden')"
                :options="companyPriorityOptions"
                @update:model-value="setCompanyPriority(company.company, String($event || 'hidden'))"
              />
              <span class="company-row__meta">
                {{ company.connector }} · tier {{ company.tier }} · {{ company.country }}
              </span>
            </div>
          </div>
        </AppCard>

        <AppCard class="companies-panel" title="Request a company" subtitle="Use this when the company you want is not in the current catalog.">
          <div class="app-form-grid">
            <AppInput v-model="requestCompanyName" label="Company name" name="companyName" placeholder="OpenAI" />
            <AppInput
              v-model="requestCareerUrl"
              :spellcheck="false"
              autocomplete="url"
              label="Career URL"
              name="careerUrl"
              placeholder="https://..."
              type="url"
            />
            <AppSelect
              :model-value="requestConnector"
              label="Suggested connector"
              :options="connectorOptions"
              @update:model-value="requestConnector = String($event || 'greenhouse')"
            />
            <AppInput v-model="requestIdentifier" label="External identifier" name="externalIdentifier" placeholder="openai" />
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
        <AppCard class="companies-panel" title="Your requests" subtitle="Track approvals and rejections without needing direct admin help.">
          <AppTable class="companies-request-table" :columns="requestColumns" :has-rows="requests.length > 0" empty-message="No company requests yet.">
            <tr v-for="request in requests" :key="request.id">
              <td class="app-table__copy">
                <strong>{{ request.company_name }}</strong>
                <p>{{ request.connector_suggestion || "No connector hint" }}</p>
              </td>
              <td>
                <AppBadge :tone="requestStatusTone(request.status)">
                  {{ request.status }}
                </AppBadge>
              </td>
              <td>{{ formatDate(request.created_at) }}</td>
            </tr>
          </AppTable>
        </AppCard>
      </AppGrid>
    </PageSection>
  </AppPage>
</template>

<style scoped>
.companies-page {
  --page-gap: var(--space-5);
}

.companies-summary-section {
  padding-top: 0;
  padding-bottom: 0;
}

.companies-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
}

.companies-summary__copy {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-3);
}

.companies-summary__copy strong {
  font-family: var(--font-display);
  font-size: clamp(1.5rem, 2vw, 1.85rem);
  line-height: 1;
  letter-spacing: -0.03em;
}

.companies-summary__copy span {
  color: var(--color-text-muted);
  font-size: 0.95rem;
}

.companies-summary__copy span::before {
  content: "•";
  margin-right: var(--space-3);
  color: var(--color-border-strong);
}

.companies-grid {
  align-items: stretch;
}

.companies-panel {
  min-height: 100%;
}

.companies-panel :deep(.app-card__header) {
  padding: clamp(var(--space-6), 3vw, 2.25rem) clamp(var(--space-6), 4vw, 2.5rem) 0;
}

.companies-panel :deep(.app-card__header-copy) {
  gap: var(--space-3);
}

.companies-panel :deep(.app-card__title) {
  font-size: clamp(1.625rem, 2.3vw, 2rem);
  letter-spacing: -0.03em;
}

.companies-panel :deep(.app-card__subtitle) {
  max-width: 42ch;
  font-size: 0.98rem;
}

.companies-panel :deep(.app-card__body) {
  align-content: start;
  gap: var(--space-6);
  padding: var(--space-6) clamp(var(--space-6), 4vw, 2.5rem) clamp(var(--space-6), 4vw, 2.25rem);
}

.companies-panel :deep(.app-form-grid) {
  gap: var(--space-5);
}

.companies-panel :deep(.app-field__label) {
  font-size: 0.95rem;
}

.companies-panel :deep(.app-input),
.companies-panel :deep(.app-select),
.companies-panel :deep(.app-textarea) {
  min-height: 3.5rem;
  border-radius: 1.125rem;
  padding-inline: 1.125rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.companies-panel :deep(.app-textarea) {
  min-height: 7.5rem;
  padding-block: 1rem;
}

.companies-panel :deep(.app-input:hover),
.companies-panel :deep(.app-select:hover),
.companies-panel :deep(.app-textarea:hover) {
  border-color: var(--color-border-strong);
}

.companies-panel :deep(.app-input:focus),
.companies-panel :deep(.app-select:focus),
.companies-panel :deep(.app-textarea:focus) {
  background: rgba(255, 255, 255, 0.98);
}

.company-list {
  display: grid;
  gap: var(--space-4);
}

.company-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(180px, 220px) auto;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(246, 249, 253, 0.96));
  box-shadow: 0 12px 26px rgba(15, 29, 58, 0.04);
  transition:
    transform var(--transition-fast),
    border-color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.company-row:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 255, 0.16);
  box-shadow: 0 16px 32px rgba(15, 29, 58, 0.06);
}

.company-row--active {
  border-color: rgba(37, 99, 255, 0.16);
  background: linear-gradient(180deg, rgba(37, 99, 255, 0.08), rgba(255, 255, 255, 0.96));
}

.company-row__toggle {
  min-width: 0;
}

.company-row__toggle :deep(.app-checkbox) {
  gap: var(--space-3);
  min-height: auto;
}

.company-row__toggle :deep(.app-checkbox span:last-child) {
  display: inline-block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 1rem;
  font-weight: 600;
}

.company-row__priority {
  min-width: 0;
}

.company-row__meta {
  color: var(--color-text-muted);
  font-size: 0.95rem;
  line-height: 1.5;
  white-space: nowrap;
}

.companies-request-table {
  overflow: hidden;
}

.companies-request-table :deep(table) {
  min-width: 100%;
  border-collapse: separate;
  border-spacing: 0 var(--space-3);
}

.companies-request-table :deep(th) {
  padding: 0 var(--space-4) var(--space-2);
}

.companies-request-table :deep(tbody td) {
  padding: var(--space-5) var(--space-4);
  border-top: 1px solid rgba(15, 29, 58, 0.08);
  border-bottom: 1px solid rgba(15, 29, 58, 0.08);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(246, 249, 253, 0.98));
  vertical-align: middle;
}

.companies-request-table :deep(tbody td:first-child) {
  padding-left: var(--space-5);
  border-left: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg) 0 0 var(--radius-lg);
}

.companies-request-table :deep(tbody td:last-child) {
  padding-right: var(--space-5);
  border-right: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: 0 var(--radius-lg) var(--radius-lg) 0;
}

.companies-request-table :deep(.app-table__copy strong) {
  display: block;
  font-size: 1rem;
  line-height: 1.35;
}

.companies-request-table :deep(tbody td p) {
  margin: var(--space-2) 0 0;
  font-size: 0.95rem;
}

@media (max-width: 1279px) {
  .company-row {
    grid-template-columns: minmax(0, 1fr);
  }

  .company-row__meta {
    white-space: normal;
  }
}

@media (max-width: 767px) {
  .companies-summary {
    padding: var(--space-4);
  }

  .companies-summary__copy {
    gap: var(--space-2);
  }

  .companies-summary__copy span::before {
    margin-right: var(--space-2);
  }

  .companies-panel :deep(.app-card__header) {
    padding: var(--space-5) var(--space-5) 0;
  }

  .companies-panel :deep(.app-card__body) {
    padding: var(--space-5);
  }

  .company-row {
    padding: var(--space-4);
  }
}
</style>
