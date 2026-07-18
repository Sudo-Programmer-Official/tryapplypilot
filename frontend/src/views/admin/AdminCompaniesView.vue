<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

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
import AppTable from "../../components/ui/AppTable.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import { fetchCatalogCompanies, importRecommendedCompanies, saveCompany } from "../../api/companies.api";
import { fetchConnectorSources } from "../../api/connectors.api";
import { fetchAdminJobs } from "../../api/jobs.api";
import { connectorOptions, countryOptions } from "../../config/options";
import { useToast } from "../../composables/useToast";
import type { CompanyPreference, JobOpportunity, SourceStatus, TableColumn } from "../../types";
import { formatRelativeMinutes, sourceStatusTone } from "../../utils/format";
import { joinCsv, parseCsv } from "../../utils/forms";

const { pushToast } = useToast();

const companies = ref<CompanyPreference[]>([]);
const jobs = ref<JobOpportunity[]>([]);
const sources = ref<SourceStatus[]>([]);
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
  { key: "jobs", label: "Jobs" },
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

function connectorSourceName(key: string): string {
  if (key === "company-api") {
    return "Company APIs";
  }
  return connectorLabel(key);
}

function connectorSnapshot(company: CompanyPreference): SourceStatus | undefined {
  return sources.value.find((source) => source.source === connectorSourceName(company.connector));
}

function companyJobCount(companyName: string): number {
  return jobs.value.filter((job) => job.company === companyName).length;
}

function companyStatus(company: CompanyPreference): { label: string; tone: "neutral" | "success" | "warning" | "danger" } {
  if (!company.enabled) {
    return { label: "Disabled", tone: "neutral" };
  }
  const snapshot = connectorSnapshot(company);
  const status = snapshot ? sourceStatusTone(snapshot) : "inactive";
  if (status === "healthy") {
    return { label: "Healthy", tone: "success" };
  }
  if (status === "warning") {
    return { label: "Lagging", tone: "warning" };
  }
  if (status === "failed") {
    return { label: "Degraded", tone: "danger" };
  }
  return { label: "Pending", tone: "neutral" };
}

function companyLastSync(company: CompanyPreference): string {
  const snapshot = connectorSnapshot(company);
  if (!snapshot || snapshot.last_run_minutes_ago === null) {
    return "Waiting";
  }
  return formatRelativeMinutes(snapshot.last_run_minutes_ago);
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

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [companiesPayload, jobsPayload, sourcesPayload] = await Promise.all([
      fetchCatalogCompanies(),
      fetchAdminJobs(),
      fetchConnectorSources(),
    ]);
    companies.value = companiesPayload.items;
    jobs.value = jobsPayload.items;
    sources.value = sourcesPayload.items;
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
    pushToast("Catalog refreshed", "Loaded the latest company, job, and connector snapshots.", "success");
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
    await refreshSnapshot();
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
  <AppPage>
    <PageHeader
      title="Company Catalog"
      description="Seed the catalog once, scan the catalog in a table, and only open the drawer when something actually needs editing."
    >
      <template #actions>
        <div class="app-actions-row catalog-actions">
          <AppButton variant="secondary" :disabled="refreshing" @click="refreshSnapshot">
            {{ refreshing ? "Refreshing..." : "Refresh Snapshot" }}
          </AppButton>
          <AppButton variant="secondary" :disabled="importing" @click="importDefaults">
            {{ importing ? "Importing..." : "Import Recommended Companies" }}
          </AppButton>
          <AppButton @click="openCreateDrawer">Add Company</AppButton>
        </div>
      </template>
    </PageHeader>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppCard title="Catalog unavailable" :subtitle="error" />
      </AppGrid>
    </PageSection>

    <template v-else>
      <PageSection>
        <AppGrid columns="1">
          <AppCard title="Catalog companies" :subtitle="`${companies.length} companies in the current catalog.`">
            <div class="app-form-grid">
              <AppInput v-model="search" label="Search" placeholder="Search company, connector, or identifier" />
            </div>

            <AppEmptyState
              v-if="!loading && filteredCompanies.length === 0"
              title="No companies in the catalog"
              description="Import the recommended defaults to seed the catalog, then edit only what needs to change."
            >
              <template #actions>
                <AppButton :disabled="importing" @click="importDefaults">Import Recommended Companies</AppButton>
              </template>
            </AppEmptyState>

            <AppTable v-else :columns="columns" :has-rows="filteredCompanies.length > 0" empty-message="No companies match the current search.">
              <tr v-for="company in filteredCompanies" :key="company.id || company.company">
                <td>
                  <div class="company-cell">
                    <strong>{{ company.company }}</strong>
                    <span>{{ company.career_url || "Career URL will be generated from connector defaults." }}</span>
                  </div>
                </td>
                <td>{{ connectorLabel(company.connector) }}</td>
                <td>
                  <AppBadge :tone="companyStatus(company).tone">
                    {{ companyStatus(company).label }}
                  </AppBadge>
                </td>
                <td>{{ companyJobCount(company.company) }}</td>
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
    </template>
  </AppPage>
</template>

<style scoped>
.catalog-actions {
  justify-content: flex-end;
}

.company-cell {
  display: grid;
  gap: var(--space-1);
}

.company-cell span {
  color: var(--color-text-muted);
  font-size: 0.88rem;
}

td {
  padding: var(--space-4) 0;
  border-top: 1px solid var(--color-border);
  vertical-align: top;
}

@media (max-width: 767px) {
  .catalog-actions {
    justify-content: flex-start;
  }
}
</style>
