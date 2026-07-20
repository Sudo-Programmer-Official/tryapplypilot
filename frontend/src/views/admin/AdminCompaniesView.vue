<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { fetchCatalogCompanies, importRecommendedCompanies, saveCompany } from "../../api/companies.api";
import { fetchAdminConnectorsWorkspace } from "../../api/connectors.api";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppCheckbox from "../../components/ui/AppCheckbox.vue";
import AppDrawer from "../../components/ui/AppDrawer.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppSelect from "../../components/ui/AppSelect.vue";
import AppSkeleton from "../../components/ui/AppSkeleton.vue";
import AppTable from "../../components/ui/AppTable.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import { connectorOptions, countryOptions } from "../../config/options";
import { useToast } from "../../composables/useToast";
import type { AdminConnectorWorkspaceCompany, CompanyPreference, TableColumn } from "../../types";
import { formatCompactNumber, formatDateTime } from "../../utils/format";
import { joinCsv, parseCsv } from "../../utils/forms";

const { pushToast } = useToast();

const companies = ref<CompanyPreference[]>([]);
const workspaceCompanies = ref<AdminConnectorWorkspaceCompany[]>([]);
const loading = ref(true);
const importing = ref(false);
const refreshing = ref(false);
const saving = ref(false);
const error = ref<string | null>(null);
const search = ref("");

const drawerOpen = ref(false);
const draft = ref<CompanyPreference>(blankCompany());

const columns: TableColumn[] = [
  { key: "company", label: "Company" },
  { key: "connector", label: "Connector" },
  { key: "status", label: "Status" },
  { key: "jobs", label: "Inventory" },
  { key: "lastSync", label: "Last Sync" },
  { key: "actions", label: "Actions" },
];

function blankCompany(): CompanyPreference {
  return {
    id: "",
    company: "",
    enabled: true,
    tier: 3,
    priority: 999,
    connector: "company-api",
    poll_interval_minutes: 5,
    country: "US",
    career_url: "",
    external_identifier: "",
    role_families: [],
  };
}

function cloneCompany(company: CompanyPreference): CompanyPreference {
  return {
    ...company,
    role_families: [...company.role_families],
  };
}

function connectorLabel(key: string): string {
  return connectorOptions.find((option) => option.value === key)?.label ?? key;
}

function workspaceSnapshot(company: CompanyPreference): AdminConnectorWorkspaceCompany | undefined {
  return workspaceCompanies.value.find((item) => item.id === company.id || item.company === company.company);
}

function companyInventoryCount(company: CompanyPreference): number {
  const snapshot = workspaceSnapshot(company);
  if (!snapshot) {
    return 0;
  }
  return snapshot.active_jobs + snapshot.stale_jobs;
}

function companyStatus(company: CompanyPreference): { label: string; tone: "neutral" | "success" | "warning" | "danger" } {
  if (!company.enabled) {
    return { label: "Disabled", tone: "neutral" };
  }
  const snapshot = workspaceSnapshot(company);
  if (!snapshot) {
    return { label: "Pending", tone: "neutral" };
  }
  if (snapshot.validation_status === "failed" || snapshot.recent_failures > 0) {
    return { label: "Needs attention", tone: "danger" };
  }
  if (snapshot.monitoring_reason === "monitored") {
    return { label: "Healthy", tone: "success" };
  }
  if (snapshot.validation_status === "pending" || snapshot.monitoring_state === "planned") {
    return { label: "Pending", tone: "warning" };
  }
  return { label: "Catalog only", tone: "neutral" };
}

function companyLastSync(company: CompanyPreference): string {
  const snapshot = workspaceSnapshot(company);
  return formatDateTime(snapshot?.last_successful_sync);
}

const filteredCompanies = computed(() =>
  companies.value
    .filter((company) => {
      const query = search.value.trim().toLowerCase();
      if (!query) {
        return true;
      }
      return `${company.company} ${company.connector} ${company.external_identifier}`.toLowerCase().includes(query);
    })
    .sort((left, right) => {
      if (left.enabled !== right.enabled) {
        return left.enabled ? -1 : 1;
      }
      return left.tier - right.tier || left.priority - right.priority || left.company.localeCompare(right.company);
    }),
);

const enabledCount = computed(() => companies.value.filter((company) => company.enabled).length);
const monitoredCount = computed(
  () => workspaceCompanies.value.filter((company) => company.monitoring_reason === "monitored" && company.enabled).length,
);
const activeInventoryCount = computed(() =>
  workspaceCompanies.value.reduce((total, company) => total + company.active_jobs + company.stale_jobs, 0),
);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [companiesPayload, workspacePayload] = await Promise.all([fetchCatalogCompanies(), fetchAdminConnectorsWorkspace()]);
    companies.value = companiesPayload.items;
    workspaceCompanies.value = workspacePayload.companies;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load company catalog.";
  } finally {
    loading.value = false;
  }
}

async function refreshSnapshot(): Promise<void> {
  refreshing.value = true;
  try {
    await load();
    pushToast("Catalog refreshed", "Loaded the latest catalog and connector inventory snapshot.", "success");
  } finally {
    refreshing.value = false;
  }
}

function openCreateDrawer(): void {
  draft.value = blankCompany();
  drawerOpen.value = true;
}

function openEditDrawer(company: CompanyPreference): void {
  draft.value = cloneCompany(company);
  drawerOpen.value = true;
}

async function saveDraft(): Promise<void> {
  saving.value = true;
  try {
    const payload = await saveCompany(draft.value);
    const index = companies.value.findIndex((item) => item.id === payload.item.id);
    if (index === -1) {
      companies.value = [payload.item, ...companies.value];
    } else {
      companies.value.splice(index, 1, payload.item);
    }
    drawerOpen.value = false;
    pushToast("Company saved", `${payload.item.company} is updated in the catalog.`, "success");
    await load();
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to save company.";
    pushToast("Company save failed", message, "error");
  } finally {
    saving.value = false;
  }
}

async function importDefaults(): Promise<void> {
  importing.value = true;
  try {
    const payload = await importRecommendedCompanies();
    companies.value = payload.items;
    pushToast(
      "Recommended companies imported",
      `${payload.summary.count} companies loaded. ${payload.summary.enabled_count} enabled for the first live validation pass.`,
      "success",
    );
    await load();
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to import recommended companies.";
    pushToast("Import failed", message, "error");
  } finally {
    importing.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppPage class="admin-catalog-page">
    <PageHeader
      title="Company Catalog"
      description="Manage the catalog with aggregated inventory counts and connector health, without loading raw job records into the page."
    >
      <template #actions>
        <div class="app-actions-row catalog-actions">
          <AppButton variant="secondary" :disabled="refreshing" @click="refreshSnapshot">
            {{ refreshing ? "Refreshing..." : "Refresh snapshot" }}
          </AppButton>
          <AppButton variant="secondary" :disabled="importing" @click="importDefaults">
            {{ importing ? "Importing..." : "Import recommended" }}
          </AppButton>
          <AppButton @click="openCreateDrawer">Add company</AppButton>
        </div>
      </template>
    </PageHeader>

    <PageSection class="admin-catalog-page__summary-section">
      <div class="admin-catalog-summary surface-card">
        <div class="admin-catalog-summary__item">
          <strong>{{ formatCompactNumber(companies.length) }}</strong>
          <span>catalog companies</span>
        </div>
        <div class="admin-catalog-summary__item">
          <strong>{{ formatCompactNumber(enabledCount) }}</strong>
          <span>enabled now</span>
        </div>
        <div class="admin-catalog-summary__item">
          <strong>{{ formatCompactNumber(monitoredCount) }}</strong>
          <span>actively monitored</span>
        </div>
        <div class="admin-catalog-summary__item">
          <strong>{{ formatCompactNumber(activeInventoryCount) }}</strong>
          <span>jobs in active inventory</span>
        </div>
      </div>
    </PageSection>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Catalog unavailable" :description="error" />
      </AppGrid>
    </PageSection>

    <PageSection v-else>
      <AppGrid columns="1">
        <AppCard class="admin-catalog-panel" title="Catalog companies" :subtitle="`${companies.length} companies in the current catalog.`">
          <div class="admin-catalog-toolbar">
            <AppInput v-model="search" label="Search" placeholder="Search company, connector, or identifier" />
          </div>

          <div v-if="loading" class="admin-catalog-loading">
            <div v-for="index in 4" :key="index" class="admin-catalog-loading__row">
              <AppSkeleton class="admin-catalog-loading__title" />
              <AppSkeleton class="admin-catalog-loading__meta" />
            </div>
          </div>

          <AppEmptyState
            v-else-if="filteredCompanies.length === 0"
            title="No companies in the catalog"
            description="Import the recommended defaults to seed the catalog, then edit only what needs to change."
          >
            <template #actions>
              <AppButton :disabled="importing" @click="importDefaults">Import recommended companies</AppButton>
            </template>
          </AppEmptyState>

          <AppTable
            v-else
            :columns="columns"
            :has-rows="filteredCompanies.length > 0"
            empty-message="No companies match the current search."
          >
            <tr v-for="company in filteredCompanies" :key="company.id || company.company">
              <td>
                <div class="company-cell">
                  <strong>{{ company.company }}</strong>
                  <span>{{ company.career_url || "Career URL will be generated from connector defaults." }}</span>
                </div>
              </td>
              <td>
                <div class="company-meta">
                  <strong>{{ connectorLabel(company.connector) }}</strong>
                  <span>tier {{ company.tier }} · priority {{ company.priority }}</span>
                </div>
              </td>
              <td>
                <AppBadge :tone="companyStatus(company).tone">
                  {{ companyStatus(company).label }}
                </AppBadge>
              </td>
              <td>
                <div class="company-meta">
                  <strong>{{ formatCompactNumber(companyInventoryCount(company)) }}</strong>
                  <span>active + stale</span>
                </div>
              </td>
              <td>{{ companyLastSync(company) }}</td>
              <td>
                <AppButton size="sm" variant="secondary" @click="openEditDrawer(company)">Edit</AppButton>
              </td>
            </tr>
          </AppTable>
        </AppCard>
      </AppGrid>
    </PageSection>

    <AppDrawer
      :open="drawerOpen"
      title="Edit company"
      description="Career URL, connector, priority, and role families live here so the table stays clean."
      side="right"
      width="lg"
      @close="drawerOpen = false"
    >
      <div class="app-form-grid">
        <AppInput v-model="draft.company" label="Company" placeholder="Microsoft" />
        <AppInput v-model="draft.career_url" label="Career URL" placeholder="https://..." />
        <AppInput v-model="draft.external_identifier" label="External identifier" placeholder="microsoft" />
        <AppSelect
          :model-value="draft.connector"
          label="Connector"
          :options="connectorOptions"
          @update:model-value="draft.connector = $event"
        />
        <AppSelect
          :model-value="draft.country"
          label="Country"
          :options="countryOptions"
          @update:model-value="draft.country = $event"
        />
        <AppInput
          :model-value="draft.priority"
          label="Priority"
          type="number"
          :min="1"
          :max="999"
          @update:model-value="draft.priority = Number($event) || 1"
        />
        <AppInput
          :model-value="draft.tier"
          label="Tier"
          type="number"
          :min="1"
          :max="3"
          @update:model-value="draft.tier = Number($event) || 1"
        />
        <AppInput
          :model-value="draft.poll_interval_minutes"
          label="Poll interval"
          type="number"
          :min="1"
          @update:model-value="draft.poll_interval_minutes = Number($event) || 5"
        />
        <AppTextArea
          :model-value="joinCsv(draft.role_families)"
          label="Role families"
          placeholder="Core Engineering, Backend, AI"
          :rows="4"
          @update:model-value="draft.role_families = parseCsv($event)"
        />
        <AppCheckbox :model-value="draft.enabled" label="Enabled" @update:model-value="draft.enabled = $event" />
        <div class="app-actions-row">
          <AppButton variant="secondary" @click="drawerOpen = false">Cancel</AppButton>
          <AppButton :disabled="saving" @click="saveDraft">{{ saving ? "Saving..." : "Save company" }}</AppButton>
        </div>
      </div>
    </AppDrawer>
  </AppPage>
</template>

<style scoped>
.admin-catalog-page {
  --page-gap: var(--space-5);
}

.catalog-actions {
  justify-content: flex-end;
}

.admin-catalog-page__summary-section {
  margin-bottom: calc(var(--space-2) * -1);
}

.admin-catalog-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
  padding: clamp(var(--space-4), 2vw, var(--space-5));
}

.admin-catalog-summary__item {
  display: grid;
  gap: var(--space-2);
}

.admin-catalog-summary__item strong {
  font-family: var(--font-display);
  font-size: clamp(1.25rem, 1.9vw, 1.5rem);
  letter-spacing: -0.03em;
}

.admin-catalog-summary__item span,
.company-cell span,
.company-meta span {
  color: var(--color-text-muted);
  font-size: 0.92rem;
  line-height: 1.5;
}

.admin-catalog-panel :deep(.app-card__header) {
  padding: clamp(var(--space-6), 3vw, 2.25rem) clamp(var(--space-6), 4vw, 2.5rem) 0;
}

.admin-catalog-panel :deep(.app-card__body) {
  padding: var(--space-5) clamp(var(--space-6), 4vw, 2.5rem) clamp(var(--space-6), 4vw, 2.25rem);
}

.admin-catalog-toolbar {
  margin-bottom: var(--space-5);
}

.admin-catalog-loading {
  display: grid;
  gap: var(--space-4);
}

.admin-catalog-loading__row {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-5);
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(246, 249, 253, 0.98));
}

.admin-catalog-loading__title {
  min-height: 1.25rem;
  max-width: 32%;
}

.admin-catalog-loading__meta {
  min-height: 1rem;
}

.company-cell,
.company-meta {
  display: grid;
  gap: var(--space-1);
}

@media (max-width: 1023px) {
  .admin-catalog-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .catalog-actions {
    justify-content: flex-start;
  }

  .admin-catalog-summary {
    grid-template-columns: 1fr;
  }
}
</style>
