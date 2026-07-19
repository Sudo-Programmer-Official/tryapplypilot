<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  fetchAdminConnectorsWorkspace,
  fetchConnectorCompanyErrors,
  fetchConnectorCompanyJobs,
  runConnectorNow,
  runMaintenanceNow,
  setConnectorCompanyMonitoring,
  validateConnectorCompany,
} from "../../api/connectors.api";
import { saveCompany } from "../../api/companies.api";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppDrawer from "../../components/ui/AppDrawer.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppSelect from "../../components/ui/AppSelect.vue";
import AppTable from "../../components/ui/AppTable.vue";
import { connectorOptions, countryOptions } from "../../config/options";
import { useToast } from "../../composables/useToast";
import type {
  AdminConnectorWorkspaceCompany,
  AdminConnectorWorkspaceConnector,
  AdminConnectorsWorkspace,
  CompanyPreference,
  ConnectorCompanyErrorRecord,
  ConnectorCompanyJobRecord,
  TableColumn,
} from "../../types";
import { formatCompactNumber, formatDateTime, formatDurationSeconds, formatFileSize, formatPercent, sourceStatusTone } from "../../utils/format";

type TabKey = "overview" | "connectors" | "companies" | "coverage" | "lifecycle" | "database" | "roadmap" | "history";
type DrawerMode = "edit" | "jobs" | "errors";

const { pushToast } = useToast();

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "overview", label: "Overview" },
  { key: "connectors", label: "Connectors" },
  { key: "companies", label: "Companies" },
  { key: "coverage", label: "Coverage Gaps" },
  { key: "lifecycle", label: "Lifecycle" },
  { key: "database", label: "Database" },
  { key: "roadmap", label: "Roadmap" },
  { key: "history", label: "Run History" },
];

const activeTab = ref<TabKey>("overview");
const workspace = ref<AdminConnectorsWorkspace | null>(null);
const loading = ref(true);
const refreshing = ref(false);
const runningMaintenance = ref(false);
const error = ref<string | null>(null);

const connectorFilter = ref("all");
const layerFilter = ref("all");
const healthFilter = ref("all");
const roadmapFilter = ref("all");
const monitoringFilter = ref("all");
const companySearch = ref("");
const historyFilter = ref("all");

const drawerOpen = ref(false);
const drawerMode = ref<DrawerMode>("edit");
const drawerTitle = ref("");
const editing = ref(false);
const drawerDraft = ref<CompanyPreference | null>(null);
const drawerJobs = ref<ConnectorCompanyJobRecord[]>([]);
const drawerErrors = ref<ConnectorCompanyErrorRecord[]>([]);
const drawerLoading = ref(false);

const connectorColumns: TableColumn[] = [
  { key: "connector", label: "Connector" },
  { key: "health", label: "Health" },
  { key: "coverage", label: "Coverage" },
  { key: "inventory", label: "Inventory" },
  { key: "throughput", label: "Throughput" },
  { key: "actions", label: "Actions" },
];

const companyColumns: TableColumn[] = [
  { key: "company", label: "Company" },
  { key: "monitoring", label: "Monitoring" },
  { key: "validation", label: "Validation" },
  { key: "inventory", label: "Inventory" },
  { key: "sync", label: "Last Sync" },
  { key: "actions", label: "Actions" },
];

const connectorFilterOptions = [
  { label: "All connectors", value: "all" },
];

const layerFilterOptions = [
  { label: "All layers", value: "all" },
  { label: "Official ATS", value: "official_ats" },
  { label: "Company careers", value: "company_careers" },
  { label: "Job aggregators", value: "job_aggregator" },
  { label: "Discovery agents", value: "discovery_agent" },
];

const roadmapFilterOptions = [
  { label: "All roadmap states", value: "all" },
  { label: "Live", value: "live" },
  { label: "Beta", value: "beta" },
  { label: "Planned", value: "planned" },
  { label: "Disabled", value: "disabled" },
];

const healthFilterOptions = [
  { label: "All health states", value: "all" },
  { label: "Healthy", value: "healthy" },
  { label: "Lagging", value: "lagging" },
  { label: "Degraded", value: "degraded" },
];

const monitoringFilterOptions = [
  { label: "All monitoring states", value: "all" },
  { label: "Monitored", value: "monitored" },
  { label: "Disabled", value: "disabled" },
  { label: "Missing identifier", value: "missing_identifier" },
  { label: "Invalid board", value: "invalid_board" },
  { label: "Validation failed", value: "validation_failed" },
  { label: "Planned", value: "planned" },
  { label: "Connector unavailable", value: "connector_unavailable" },
];

const historyFilterOptions = [
  { label: "All runs", value: "all" },
  { label: "Succeeded", value: "succeeded" },
  { label: "Failed", value: "failed" },
  { label: "Running", value: "running" },
];

const coverageColumns: TableColumn[] = [
  { key: "company", label: "Company" },
  { key: "connector", label: "Connector" },
  { key: "gap", label: "Gap" },
  { key: "action", label: "Recommended Action" },
];

const roadmapColumns: TableColumn[] = [
  { key: "connector", label: "Connector" },
  { key: "layer", label: "Layer" },
  { key: "status", label: "Roadmap" },
  { key: "quality", label: "Quality" },
  { key: "coverage", label: "Coverage" },
];

const historyColumns: TableColumn[] = [
  { key: "run", label: "Run" },
  { key: "company", label: "Company" },
  { key: "status", label: "Status" },
  { key: "throughput", label: "Throughput" },
  { key: "alerts", label: "Alerts" },
  { key: "timing", label: "Timing" },
];

function blankDraft(company: AdminConnectorWorkspaceCompany): CompanyPreference {
  return {
    id: company.id,
    company: company.company,
    enabled: company.enabled,
    tier: company.tier,
    priority: company.priority,
    connector: company.connector,
    poll_interval_minutes: company.poll_interval_minutes,
    country: company.country,
    career_url: company.career_url,
    external_identifier: company.external_identifier,
    role_families: [...company.role_families],
  };
}

function roadmapTone(status: string): "success" | "warning" | "info" | "neutral" {
  if (status === "live") {
    return "success";
  }
  if (status === "beta") {
    return "warning";
  }
  if (status === "planned") {
    return "info";
  }
  return "neutral";
}

function monitoringTone(reason: string): "success" | "warning" | "info" | "neutral" | "danger" {
  if (reason === "monitored") {
    return "success";
  }
  if (reason === "disabled") {
    return "neutral";
  }
  if (reason === "planned") {
    return "info";
  }
  if (reason === "missing_identifier" || reason === "invalid_board") {
    return "warning";
  }
  return "danger";
}

function validationTone(status: string): "success" | "warning" | "info" | "neutral" | "danger" {
  if (status === "passed") {
    return "success";
  }
  if (status === "pending") {
    return "info";
  }
  return "danger";
}

function readinessTone(status: string): "success" | "warning" | "danger" {
  if (status === "ready") {
    return "success";
  }
  if (status === "pending") {
    return "warning";
  }
  return "danger";
}

function connectorTone(connector: AdminConnectorWorkspaceConnector): "success" | "warning" | "danger" | "neutral" {
  const tone = sourceStatusTone(connector);
  if (tone === "healthy") {
    return "success";
  }
  if (tone === "warning") {
    return "warning";
  }
  if (tone === "failed") {
    return "danger";
  }
  return "neutral";
}

function qualityTone(grade: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (grade.startsWith("A") || grade.startsWith("B")) {
    return "success";
  }
  if (grade.startsWith("C")) {
    return "warning";
  }
  if (grade === "Planned") {
    return "info";
  }
  if (grade === "Disabled") {
    return "neutral";
  }
  return "danger";
}

function layerLabel(layer: string): string {
  if (layer === "official_ats") {
    return "Official ATS";
  }
  if (layer === "company_careers") {
    return "Company Careers";
  }
  if (layer === "job_aggregator") {
    return "Job Aggregators";
  }
  return "Discovery Agent";
}

function connectorLabel(value: string): string {
  return connectorOptions.find((option) => option.value === value)?.label ?? value;
}

function monitoringLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function trendWidth(value: number, maxValue: number): string {
  if (value <= 0 || maxValue <= 0) {
    return "0%";
  }
  return `${Math.max(10, Math.round((value / maxValue) * 100))}%`;
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    workspace.value = await fetchAdminConnectorsWorkspace();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load connector workspace.";
  } finally {
    loading.value = false;
  }
}

async function refreshWorkspace(message = "Connector workspace refreshed."): Promise<void> {
  refreshing.value = true;
  try {
    workspace.value = await fetchAdminConnectorsWorkspace();
    pushToast("Workspace refreshed", message, "success");
  } catch (err) {
    const messageText = err instanceof Error ? err.message : "Failed to refresh connector workspace.";
    pushToast("Refresh failed", messageText, "error");
  } finally {
    refreshing.value = false;
  }
}

async function handleRunMaintenance(): Promise<void> {
  runningMaintenance.value = true;
  try {
    await runMaintenanceNow();
    await refreshWorkspace("Lifecycle maintenance completed and metrics were refreshed.");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to run maintenance.";
    pushToast("Maintenance failed", message, "error");
  } finally {
    runningMaintenance.value = false;
  }
}

async function handleRunConnector(connectorKey: string): Promise<void> {
  try {
    await runConnectorNow(connectorKey);
    await refreshWorkspace(`${connectorLabel(connectorKey)} was triggered immediately.`);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to run connector.";
    pushToast("Connector run failed", message, "error");
  }
}

async function handleValidate(companyId: string): Promise<void> {
  try {
    await validateConnectorCompany(companyId);
    await refreshWorkspace("Connector validation finished.");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to validate company.";
    pushToast("Validation failed", message, "error");
  }
}

async function handleToggleMonitoring(company: AdminConnectorWorkspaceCompany): Promise<void> {
  try {
    await setConnectorCompanyMonitoring(company.id, !company.enabled);
    await refreshWorkspace(`${company.company} monitoring was updated.`);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to update monitoring.";
    pushToast("Monitoring update failed", message, "error");
  }
}

function openEditDrawer(company: AdminConnectorWorkspaceCompany): void {
  drawerMode.value = "edit";
  drawerTitle.value = `Edit ${company.company}`;
  drawerDraft.value = blankDraft(company);
  drawerJobs.value = [];
  drawerErrors.value = [];
  drawerOpen.value = true;
}

async function openJobsDrawer(company: AdminConnectorWorkspaceCompany): Promise<void> {
  drawerMode.value = "jobs";
  drawerTitle.value = `${company.company} jobs`;
  drawerDraft.value = null;
  drawerJobs.value = [];
  drawerErrors.value = [];
  drawerLoading.value = true;
  drawerOpen.value = true;
  try {
    const payload = await fetchConnectorCompanyJobs(company.id);
    drawerJobs.value = payload.items;
  } finally {
    drawerLoading.value = false;
  }
}

async function openErrorsDrawer(company: AdminConnectorWorkspaceCompany): Promise<void> {
  drawerMode.value = "errors";
  drawerTitle.value = `${company.company} connector errors`;
  drawerDraft.value = null;
  drawerJobs.value = [];
  drawerErrors.value = [];
  drawerLoading.value = true;
  drawerOpen.value = true;
  try {
    const payload = await fetchConnectorCompanyErrors(company.id);
    drawerErrors.value = payload.items;
  } finally {
    drawerLoading.value = false;
  }
}

async function saveDraft(): Promise<void> {
  if (!drawerDraft.value) {
    return;
  }
  editing.value = true;
  try {
    await saveCompany(drawerDraft.value);
    drawerOpen.value = false;
    await refreshWorkspace(`${drawerDraft.value.company} was updated.`);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to save company.";
    pushToast("Save failed", message, "error");
  } finally {
    editing.value = false;
  }
}

const connectors = computed(() => workspace.value?.connectors ?? []);
const companies = computed(() => workspace.value?.companies ?? []);
const coverageGaps = computed(() => workspace.value?.coverage_gaps ?? []);
const runHistory = computed(() => workspace.value?.run_history ?? []);
const roadmap = computed(() => workspace.value?.roadmap ?? []);
const trendPoints = computed(() => workspace.value?.overview.trends ?? []);
const aiCoverage = computed(() => workspace.value?.overview.ai_coverage ?? null);
const qualityLeaders = computed(() =>
  [...connectors.value]
    .filter((connector) => connector.admin_status !== "planned")
    .sort((left, right) => right.quality_score - left.quality_score)
    .slice(0, 6),
);
const trendMaxima = computed(() => ({
  jobsInserted: Math.max(...trendPoints.value.map((point) => point.jobs_inserted), 1),
  alertsSent: Math.max(...trendPoints.value.map((point) => point.alerts_sent), 1),
  failures: Math.max(...trendPoints.value.map((point) => point.failures), 1),
  runtime: Math.max(...trendPoints.value.map((point) => point.average_runtime_seconds ?? 0), 1),
}));
const connectorSelectOptions = computed(() => [
  ...connectorFilterOptions,
  ...connectors.value.map((connector) => ({
    label: connector.source,
    value: connector.connector_key,
  })),
]);

const filteredConnectors = computed(() =>
  connectors.value.filter((connector) => {
    if (connectorFilter.value !== "all" && connector.connector_key !== connectorFilter.value) {
      return false;
    }
    if (layerFilter.value !== "all" && connector.layer !== layerFilter.value) {
      return false;
    }
    if (healthFilter.value !== "all" && connector.state !== healthFilter.value) {
      return false;
    }
    if (roadmapFilter.value !== "all" && connector.admin_status !== roadmapFilter.value) {
      return false;
    }
    return true;
  }),
);

const filteredCompanies = computed(() =>
  companies.value.filter((company) => {
    const query = companySearch.value.trim().toLowerCase();
    if (query && !`${company.company} ${company.connector} ${company.external_identifier}`.toLowerCase().includes(query)) {
      return false;
    }
    if (connectorFilter.value !== "all" && company.connector !== connectorFilter.value) {
      return false;
    }
    if (layerFilter.value !== "all" && company.layer !== layerFilter.value) {
      return false;
    }
    if (roadmapFilter.value !== "all" && company.roadmap_status !== roadmapFilter.value) {
      return false;
    }
    if (monitoringFilter.value !== "all" && company.monitoring_reason !== monitoringFilter.value) {
      return false;
    }
    return true;
  }),
);

const filteredCoverageGaps = computed(() =>
  coverageGaps.value.filter((gap) => {
    if (connectorFilter.value !== "all" && gap.connector !== connectorFilter.value) {
      return false;
    }
    if (roadmapFilter.value !== "all" && gap.roadmap_status !== roadmapFilter.value) {
      return false;
    }
    return true;
  }),
);

const filteredRunHistory = computed(() =>
  runHistory.value.filter((item) => {
    if (connectorFilter.value !== "all" && item.connector_group !== connectorFilter.value) {
      return false;
    }
    if (historyFilter.value !== "all" && item.run_status !== historyFilter.value) {
      return false;
    }
    return true;
  }),
);

onMounted(load);
</script>

<template>
  <AppPage>
    <PageHeader
      title="Admin Connectors"
      description="Operate connector coverage, lifecycle health, and database inventory from one control surface."
    >
      <template #actions>
        <div class="app-actions-row connectors-actions">
          <AppButton variant="secondary" :disabled="refreshing" @click="refreshWorkspace()">
            {{ refreshing ? "Refreshing..." : "Refresh Workspace" }}
          </AppButton>
          <AppButton variant="secondary" :disabled="runningMaintenance" @click="handleRunMaintenance">
            {{ runningMaintenance ? "Running..." : "Run Maintenance" }}
          </AppButton>
        </div>
      </template>
    </PageHeader>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Connector workspace unavailable" :description="error" />
      </AppGrid>
    </PageSection>

    <template v-else-if="workspace">
      <PageSection>
        <div class="tab-strip">
          <AppButton
            v-for="tab in tabs"
            :key="tab.key"
            :variant="activeTab === tab.key ? 'primary' : 'secondary'"
            size="sm"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
          </AppButton>
        </div>
      </PageSection>

      <PageSection>
        <AppGrid columns="4">
          <AppCard title="Active Inventory" subtitle="Jobs still considered live and alert-eligible.">
            <div class="metric-card">
              <strong>{{ formatCompactNumber(workspace.overview.inventory.active) }}</strong>
              <p>{{ formatCompactNumber(workspace.overview.inventory.new_today) }} new today · {{ formatCompactNumber(workspace.overview.inventory.stale) }} stale</p>
            </div>
          </AppCard>
          <AppCard title="Closed / Archived" subtitle="Lifecycle backlog after repeated absence or source closure.">
            <div class="metric-card">
              <strong>{{ formatCompactNumber(workspace.overview.inventory.closed + workspace.overview.inventory.archived) }}</strong>
              <p>{{ formatCompactNumber(workspace.overview.inventory.closed) }} closed · {{ formatCompactNumber(workspace.overview.inventory.archived) }} archived</p>
            </div>
          </AppCard>
          <AppCard title="Collected Lifetime" subtitle="Throughput independent from current active inventory.">
            <div class="metric-card">
              <strong>{{ formatCompactNumber(workspace.overview.inventory.collected_lifetime) }}</strong>
              <p>Total insert volume across all connector runs.</p>
            </div>
          </AppCard>
          <AppCard title="Coverage Gaps" subtitle="Catalog companies that still cannot be monitored cleanly.">
            <div class="metric-card">
              <strong>{{ formatCompactNumber(workspace.overview.coverage_gaps) }}</strong>
              <p>{{ workspace.overview.monitored_companies }}/{{ workspace.overview.catalog_companies }} companies actively monitorable.</p>
            </div>
          </AppCard>
          <AppCard title="Alerts Today" subtitle="Successful user-facing notifications delivered today.">
            <div class="metric-card">
              <strong>{{ formatCompactNumber(workspace.overview.kpis.alerts_sent_today) }}</strong>
              <p>{{ formatCompactNumber(workspace.overview.kpis.connector_failures_today) }} connector failures today.</p>
            </div>
          </AppCard>
          <AppCard title="Average Quality" subtitle="Coverage, reliability, and freshness blended into one connector grade.">
            <div class="metric-card">
              <strong>{{ workspace.overview.kpis.average_quality_score }}</strong>
              <p>{{ formatPercent(workspace.overview.kpis.coverage_percent) }} catalog coverage · {{ workspace.overview.kpis.connectors_live }} live connectors.</p>
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection v-if="activeTab === 'overview'">
        <AppGrid columns="2">
          <AppCard title="Connector Maturity" subtitle="Live inventory, roadmap coverage, and current runtime health.">
            <div class="overview-grid">
              <div>
                <span class="eyebrow">Connectors</span>
                <strong>{{ workspace.overview.connectors_total }}</strong>
                <p>{{ workspace.overview.connectors_live }} live · {{ workspace.overview.connectors_beta }} beta · {{ workspace.overview.connectors_planned }} planned</p>
              </div>
              <div>
                <span class="eyebrow">Quality</span>
                <strong>{{ workspace.overview.kpis.average_quality_score }}</strong>
                <p>{{ formatPercent(workspace.overview.kpis.coverage_percent) }} coverage · {{ workspace.overview.kpis.jobs_added_today }} new jobs today.</p>
              </div>
            </div>
          </AppCard>
          <AppCard title="Lifecycle Service" subtitle="Background reconciliation for stale, closed, archived, and deleted jobs.">
            <div class="overview-grid">
              <div>
                <span class="eyebrow">Maintenance</span>
                <strong>{{ workspace.lifecycle.maintenance?.running ? "Running" : "Stopped" }}</strong>
                <p>Every {{ workspace.lifecycle.settings.maintenance_interval_minutes }} minutes · batch {{ workspace.lifecycle.settings.cleanup_batch_size }}</p>
              </div>
              <div>
                <span class="eyebrow">Last Maintenance</span>
                <strong>{{ formatDateTime(workspace.lifecycle.maintenance?.last_run) }}</strong>
                <p>{{ workspace.lifecycle.maintenance?.archived_jobs ?? 0 }} archived · {{ workspace.lifecycle.maintenance?.deleted_jobs ?? 0 }} deleted in the latest cycle.</p>
              </div>
            </div>
          </AppCard>
          <AppCard title="Connector Quality" subtitle="The highest-confidence connectors to scale next.">
            <div class="drawer-list compact-list">
              <article v-for="connector in qualityLeaders" :key="connector.id" class="drawer-list__item">
                <div class="list-heading">
                  <strong>{{ connector.source }}</strong>
                  <AppBadge :tone="qualityTone(connector.quality_grade)">{{ connector.quality_grade }}</AppBadge>
                </div>
                <p>{{ formatPercent(connector.coverage_percent) }} coverage · {{ formatPercent(connector.reliability_percent) }} reliability · {{ formatPercent(connector.uptime_percent) }} uptime</p>
                <p>{{ connector.jobs_inserted_today }} new today · {{ connector.alerts_sent_today }} alerts · {{ connector.retries_today }} retries</p>
              </article>
            </div>
          </AppCard>
          <AppCard title="AI Coverage" subtitle="Curated AI company collections tracked by the connector platform.">
            <div v-if="aiCoverage" class="drawer-list compact-list">
              <article class="drawer-list__item">
                <strong>{{ aiCoverage.covered }}/{{ aiCoverage.total }} covered</strong>
                <p>{{ aiCoverage.planned }} planned · {{ aiCoverage.missing }} missing or operator-blocked.</p>
              </article>
              <article v-for="collection in aiCoverage.collections" :key="collection.name" class="drawer-list__item">
                <div class="list-heading">
                  <strong>{{ collection.name }}</strong>
                  <AppBadge :tone="collection.covered === collection.total ? 'success' : collection.covered > 0 ? 'warning' : 'info'">
                    {{ collection.covered }}/{{ collection.total }}
                  </AppBadge>
                </div>
                <p>{{ collection.covered }} covered · {{ collection.planned }} planned · {{ collection.missing }} missing</p>
              </article>
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection v-if="activeTab === 'overview'">
        <AppGrid columns="1">
          <AppCard title="Daily Trends" subtitle="Jobs/day, alerts/day, failures/day, and runtime trends for the last 14 days.">
            <div class="trend-grid">
              <article v-for="point in trendPoints" :key="point.date" class="trend-card">
                <div class="list-heading">
                  <strong>{{ point.label }}</strong>
                  <span class="eyebrow">{{ point.jobs_inserted }} new</span>
                </div>
                <div class="trend-row">
                  <span>Jobs</span>
                  <div class="trend-bar">
                    <span class="trend-bar__fill trend-bar__fill--jobs" :style="{ width: trendWidth(point.jobs_inserted, trendMaxima.jobsInserted) }" />
                  </div>
                </div>
                <div class="trend-row">
                  <span>Alerts</span>
                  <div class="trend-bar">
                    <span class="trend-bar__fill trend-bar__fill--alerts" :style="{ width: trendWidth(point.alerts_sent, trendMaxima.alertsSent) }" />
                  </div>
                </div>
                <div class="trend-row">
                  <span>Failures</span>
                  <div class="trend-bar">
                    <span class="trend-bar__fill trend-bar__fill--failures" :style="{ width: trendWidth(point.failures, trendMaxima.failures) }" />
                  </div>
                </div>
                <p>{{ point.jobs_fetched }} fetched · {{ point.jobs_ignored }} ignored · {{ point.retries }} retries · {{ formatDurationSeconds(point.average_runtime_seconds) }} avg runtime</p>
              </article>
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection v-if="activeTab === 'connectors' || activeTab === 'companies' || activeTab === 'coverage' || activeTab === 'roadmap' || activeTab === 'history'">
        <div class="filter-row">
          <AppSelect v-model="connectorFilter" label="Connector" :options="connectorSelectOptions" />
          <AppSelect v-model="layerFilter" label="Layer" :options="layerFilterOptions" />
          <AppSelect v-model="roadmapFilter" label="Roadmap" :options="roadmapFilterOptions" />
          <AppSelect v-if="activeTab === 'connectors'" v-model="healthFilter" label="Health" :options="healthFilterOptions" />
          <AppSelect v-if="activeTab === 'companies'" v-model="monitoringFilter" label="Monitoring" :options="monitoringFilterOptions" />
          <AppSelect v-if="activeTab === 'history'" v-model="historyFilter" label="Run status" :options="historyFilterOptions" />
          <AppInput v-if="activeTab === 'companies'" v-model="companySearch" label="Search" placeholder="Search companies or board ids" />
        </div>
      </PageSection>

      <PageSection v-if="activeTab === 'connectors'">
        <AppGrid columns="1">
          <AppCard title="Connector Operations" subtitle="Health, coverage, lifecycle inventory, and targeted operator controls per connector.">
            <AppTable :columns="connectorColumns" :has-rows="filteredConnectors.length > 0" empty-message="No connectors match the current filters.">
              <tr v-for="connector in filteredConnectors" :key="connector.id">
                <td>
                  <strong>{{ connector.source }}</strong>
                  <p>{{ layerLabel(connector.layer) }} · every {{ connector.cadence_minutes }} min</p>
                </td>
                <td>
                  <AppBadge :tone="connectorTone(connector)">{{ connector.state }}</AppBadge>
                  <AppBadge :tone="qualityTone(connector.quality_grade)">{{ connector.quality_grade }}</AppBadge>
                  <p>{{ formatPercent(connector.reliability_percent) }} reliability · {{ formatPercent(connector.uptime_percent) }} uptime</p>
                </td>
                <td>
                  <strong>{{ connector.companies_enabled }}/{{ connector.catalog_company_count }} · {{ formatPercent(connector.coverage_percent) }}</strong>
                  <p>{{ connector.companies_scanned_today }} scanned · {{ connector.jobs_fetched_today }} fetched · {{ connector.jobs_inserted_today }} inserted</p>
                </td>
                <td>
                  <strong>{{ connector.active_jobs }} active</strong>
                  <p>{{ connector.stale_jobs }} stale · {{ connector.closed_jobs }} closed · {{ connector.archived_jobs }} archived</p>
                </td>
                <td>
                  <strong>{{ formatDateTime(connector.last_successful_sync) }}</strong>
                  <p>{{ connector.jobs_updated_today }} updated · {{ connector.jobs_ignored_today }} ignored · {{ connector.alerts_sent_today }} alerts · {{ connector.failed_runs_today }} failures today</p>
                  <p>{{ formatDurationSeconds(connector.average_runtime_seconds_14d ?? connector.average_runtime_seconds) }} avg runtime · {{ connector.retries_today }} retries</p>
                </td>
                <td>
                  <div class="inline-actions">
                    <AppButton size="sm" @click="handleRunConnector(connector.connector_key)">Run Now</AppButton>
                  </div>
                </td>
              </tr>
            </AppTable>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection v-if="activeTab === 'companies'">
        <AppGrid columns="1">
          <AppCard title="Company Coverage" subtitle="Operator controls for board validation, monitoring state, identifiers, jobs, and recent connector failures.">
            <AppTable :columns="companyColumns" :has-rows="filteredCompanies.length > 0" empty-message="No companies match the current filters.">
              <tr v-for="company in filteredCompanies" :key="company.id">
                <td>
                  <strong>{{ company.company }}</strong>
                  <p>{{ connectorLabel(company.connector) }} · {{ company.external_identifier || "no board id" }}</p>
                  <p v-if="company.ai_collections.length > 0">{{ company.ai_collections.join(" · ") }}</p>
                </td>
                <td>
                  <AppBadge :tone="monitoringTone(company.monitoring_reason)">{{ monitoringLabel(company.monitoring_reason) }}</AppBadge>
                  <p>{{ company.monitoring_detail }}</p>
                </td>
                <td>
                  <AppBadge :tone="validationTone(company.validation_status)">{{ company.validation_status }}</AppBadge>
                  <AppBadge :tone="readinessTone(company.production_readiness_status)">
                    {{ company.production_readiness_status }}
                  </AppBadge>
                  <p>{{ company.validation_message }}</p>
                  <p>
                    {{ company.production_readiness_summary }}
                    · {{ company.production_readiness_pending }} pending
                    · {{ company.production_readiness_blocked }} blocked
                  </p>
                </td>
                <td>
                  <strong>{{ company.active_jobs }} active</strong>
                  <p>{{ company.stale_jobs }} stale · {{ company.closed_jobs }} closed · {{ company.archived_jobs }} archived</p>
                </td>
                <td>
                  <strong>{{ formatDateTime(company.last_successful_sync) }}</strong>
                  <p>{{ company.recent_failures }} failures in 7 days</p>
                </td>
                <td>
                  <div class="inline-actions inline-actions--wrap">
                    <AppButton size="sm" variant="secondary" @click="handleValidate(company.id)">Validate</AppButton>
                    <AppButton size="sm" variant="secondary" @click="handleToggleMonitoring(company)">
                      {{ company.enabled ? "Disable" : "Enable" }}
                    </AppButton>
                    <AppButton size="sm" variant="secondary" @click="openEditDrawer(company)">Edit</AppButton>
                    <AppButton size="sm" variant="secondary" @click="openJobsDrawer(company)">Inspect Jobs</AppButton>
                    <AppButton size="sm" variant="secondary" @click="openErrorsDrawer(company)">View Errors</AppButton>
                  </div>
                </td>
              </tr>
            </AppTable>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection v-if="activeTab === 'coverage'">
        <AppGrid columns="1">
          <AppCard title="Coverage Gap Queue" subtitle="Every planned or catalog-only company with the missing capability and the exact next action to unblock monitoring.">
            <AppTable :columns="coverageColumns" :has-rows="filteredCoverageGaps.length > 0" empty-message="No coverage gaps under the current filters.">
              <tr v-for="gap in filteredCoverageGaps" :key="gap.company_id">
                <td>
                  <strong>{{ gap.company }}</strong>
                  <p>Tier {{ gap.tier }} · priority {{ gap.priority }}</p>
                </td>
                <td>
                  <strong>{{ connectorLabel(gap.connector) }}</strong>
                  <p><AppBadge :tone="roadmapTone(gap.roadmap_status)">{{ gap.roadmap_status }}</AppBadge></p>
                </td>
                <td>
                  <AppBadge :tone="monitoringTone(gap.missing_capability)">{{ monitoringLabel(gap.missing_capability) }}</AppBadge>
                  <p>{{ gap.detail }}</p>
                </td>
                <td>{{ gap.recommended_action }}</td>
              </tr>
            </AppTable>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection v-if="activeTab === 'lifecycle'">
        <AppGrid columns="4">
          <AppCard title="Stale Threshold" subtitle="Missed successful polls before a job is marked stale.">
            <div class="metric-card">
              <strong>{{ workspace.lifecycle.settings.stale_after_missed_syncs }}</strong>
              <p>Jobs remain active until this threshold is crossed.</p>
            </div>
          </AppCard>
          <AppCard title="Close Threshold" subtitle="Missed successful polls before the job is considered closed.">
            <div class="metric-card">
              <strong>{{ workspace.lifecycle.settings.closed_after_missed_syncs }}</strong>
              <p>Repeated absences move jobs from stale into closed.</p>
            </div>
          </AppCard>
          <AppCard title="Archive Window" subtitle="Days after closure before jobs are archived.">
            <div class="metric-card">
              <strong>{{ workspace.lifecycle.settings.archive_after_days }}</strong>
              <p>Closed inventory remains queryable until archival.</p>
            </div>
          </AppCard>
          <AppCard title="Delete Window" subtitle="Days archived before unreferenced jobs are hard-deleted.">
            <div class="metric-card">
              <strong>{{ workspace.lifecycle.settings.delete_after_days }}</strong>
              <p>Saved or alerted jobs are preserved beyond cleanup.</p>
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection v-if="activeTab === 'database'">
        <AppGrid columns="4">
          <AppCard title="Jobs Rows" subtitle="Current rows in the jobs table.">
            <div class="metric-card">
              <strong>{{ formatCompactNumber(workspace.database.jobs_rows) }}</strong>
              <p>{{ formatCompactNumber(workspace.database.active_inventory) }} active · {{ formatCompactNumber(workspace.database.archived_inventory) }} archived</p>
            </div>
          </AppCard>
          <AppCard title="Connector Runs" subtitle="Run history records powering operator diagnostics.">
            <div class="metric-card">
              <strong>{{ formatCompactNumber(workspace.database.connector_runs_rows) }}</strong>
              <p>{{ formatCompactNumber(workspace.database.collected_lifetime) }} inserted over lifetime.</p>
            </div>
          </AppCard>
          <AppCard title="Notification Rows" subtitle="Alert records retained for delivery analytics and history.">
            <div class="metric-card">
              <strong>{{ formatCompactNumber(workspace.database.user_alerts_rows + workspace.database.alerts_rows) }}</strong>
              <p>{{ workspace.database.user_alerts_rows }} user alerts · {{ workspace.database.alerts_rows }} legacy alerts</p>
            </div>
          </AppCard>
          <AppCard title="Storage Estimate" subtitle="Approximate footprint of the operational job radar tables.">
            <div class="metric-card">
              <strong>{{ formatFileSize(workspace.database.estimated_storage_bytes ?? 0) }}</strong>
              <p>{{ workspace.database.job_matches_rows }} match rows · {{ workspace.database.saved_jobs_rows }} saved jobs</p>
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection v-if="activeTab === 'roadmap'">
        <AppGrid columns="1">
          <AppCard title="Connector Roadmap" subtitle="Coverage percentage and maturity per discovery source.">
            <AppTable :columns="roadmapColumns" :has-rows="roadmap.length > 0" empty-message="No roadmap entries available.">
              <tr v-for="item in roadmap" :key="item.connector_key">
                <td>{{ item.source }}</td>
                <td>{{ layerLabel(item.layer) }}</td>
                <td><AppBadge :tone="roadmapTone(item.roadmap_status)">{{ item.roadmap_status }}</AppBadge></td>
                <td>
                  <AppBadge :tone="qualityTone(item.quality_grade)">{{ item.quality_grade }}</AppBadge>
                  <p>{{ formatPercent(item.reliability_percent) }} reliability · score {{ item.quality_score }}</p>
                </td>
                <td>{{ item.companies_enabled }}/{{ item.catalog_company_count }} · {{ formatPercent(item.coverage_percent) }}</td>
              </tr>
            </AppTable>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection v-if="activeTab === 'history'">
        <AppGrid columns="1">
          <AppCard title="Run History" subtitle="Recent connector executions with throughput, alert delivery, and failure detail.">
            <AppTable :columns="historyColumns" :has-rows="filteredRunHistory.length > 0" empty-message="No run history matches the current filters.">
              <tr v-for="item in filteredRunHistory" :key="item.run_id">
                <td>
                  <strong>{{ connectorLabel(item.connector_group) }}</strong>
                  <p>{{ item.trigger }} · {{ formatDateTime(item.started_at) }}</p>
                  <p>{{ item.companies_scanned }} company scanned</p>
                </td>
                <td>
                  <strong>{{ item.company_name || "Connector-wide" }}</strong>
                  <p>{{ item.connector_key }}</p>
                </td>
                <td>
                  <AppBadge :tone="item.run_status === 'succeeded' ? 'success' : item.run_status === 'failed' ? 'danger' : 'warning'">
                    {{ item.run_status }}
                  </AppBadge>
                  <p>{{ item.error_message || "No connector error." }}</p>
                </td>
                <td>
                  <strong>{{ item.jobs_fetched }} fetched</strong>
                  <p>{{ item.jobs_inserted }} inserted · {{ item.jobs_updated }} updated · {{ item.jobs_ignored }} ignored</p>
                  <p>{{ item.jobs_closed }} closed · {{ item.jobs_archived }} archived · {{ item.jobs_matched }} matched</p>
                </td>
                <td>
                  <strong>{{ item.alerts_sent }} sent</strong>
                  <p>{{ item.alerts_failed }} failed · {{ item.retries }} retries</p>
                </td>
                <td>
                  <strong>{{ formatDurationSeconds(item.duration_seconds) }}</strong>
                  <p>{{ formatDateTime(item.finished_at) }}</p>
                </td>
              </tr>
            </AppTable>
          </AppCard>
        </AppGrid>
      </PageSection>
    </template>

    <AppDrawer :open="drawerOpen" side="right" width="lg" :title="drawerTitle" @close="drawerOpen = false">
      <div v-if="drawerMode === 'edit' && drawerDraft" class="drawer-stack">
        <AppInput v-model="drawerDraft.company" label="Company" />
        <AppSelect v-model="drawerDraft.connector" label="Connector" :options="connectorOptions" />
        <AppInput v-model="drawerDraft.external_identifier" label="External Identifier" />
        <AppInput v-model="drawerDraft.career_url" label="Career URL" />
        <AppSelect v-model="drawerDraft.country" label="Country" :options="countryOptions" />
        <AppInput v-model.number="drawerDraft.poll_interval_minutes" label="Poll Interval Minutes" type="number" />
        <AppInput v-model.number="drawerDraft.priority" label="Priority" type="number" />
        <AppInput v-model.number="drawerDraft.tier" label="Tier" type="number" />
        <div class="inline-actions">
          <AppButton :disabled="editing" @click="saveDraft">
            {{ editing ? "Saving..." : "Save Company" }}
          </AppButton>
        </div>
      </div>

      <div v-else-if="drawerMode === 'jobs'" class="drawer-stack">
        <AppEmptyState
          v-if="drawerLoading"
          title="Loading jobs"
          description="Fetching the latest company inventory."
        />
        <AppEmptyState
          v-else-if="drawerJobs.length === 0"
          title="No jobs found"
          description="This company has no stored jobs yet."
        />
        <div v-else class="drawer-list">
          <article v-for="job in drawerJobs" :key="job.job_id" class="drawer-list__item">
            <strong>{{ job.title }}</strong>
            <p>{{ job.location }}</p>
            <p>{{ job.lifecycle_status }} · {{ job.source_status }}</p>
            <p>Seen {{ formatDateTime(job.last_seen_at) }}</p>
          </article>
        </div>
      </div>

      <div v-else class="drawer-stack">
        <AppEmptyState
          v-if="drawerLoading"
          title="Loading errors"
          description="Fetching recent connector failures for this company."
        />
        <AppEmptyState
          v-else-if="drawerErrors.length === 0"
          title="No recent connector errors"
          description="The latest runs for this company have not failed."
        />
        <div v-else class="drawer-list">
          <article v-for="item in drawerErrors" :key="item.run_id" class="drawer-list__item">
            <strong>{{ item.connector_key }}</strong>
            <p>{{ formatDateTime(item.started_at) }}</p>
            <p>{{ item.error_message || "Unknown error" }}</p>
          </article>
        </div>
      </div>
    </AppDrawer>
  </AppPage>
</template>

<style scoped>
.connectors-actions,
.filter-row,
.inline-actions {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.tab-strip {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.metric-card,
.overview-grid {
  display: grid;
  gap: var(--content-gap);
}

.metric-card strong {
  font-family: var(--font-display);
  font-size: clamp(2rem, 3vw, 2.75rem);
  line-height: 1;
}

.metric-card p,
.overview-grid p,
.drawer-list__item p,
td p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
  line-height: 1.55;
}

.overview-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.list-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.compact-list {
  padding: 0;
}

.trend-grid {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.trend-card {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface-muted);
}

.trend-row {
  display: grid;
  gap: var(--space-2);
}

.trend-row span:first-child {
  font-size: var(--type-small);
  color: var(--color-text-muted);
}

.trend-bar {
  height: 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-text-muted) 15%, transparent);
  overflow: hidden;
}

.trend-bar__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.trend-bar__fill--jobs {
  background: linear-gradient(90deg, #1d4ed8, #60a5fa);
}

.trend-bar__fill--alerts {
  background: linear-gradient(90deg, #047857, #34d399);
}

.trend-bar__fill--failures {
  background: linear-gradient(90deg, #b91c1c, #fb7185);
}

.drawer-stack {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-5);
}

.drawer-list {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-5);
}

.drawer-list__item {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface-muted);
}

.inline-actions--wrap {
  align-items: flex-start;
}
</style>
