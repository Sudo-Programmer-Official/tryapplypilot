<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import ConnectorHealthTable from "../../components/admin/ConnectorHealthTable.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppTable from "../../components/ui/AppTable.vue";
import { fetchCatalogCompanies } from "../../api/companies.api";
import { fetchConnectorSources } from "../../api/connectors.api";
import type { CompanyPreference, SourceStatus, TableColumn } from "../../types";
import { formatCompactNumber, formatDateTime, formatDurationSeconds, formatPercent } from "../../utils/format";

const sources = ref<SourceStatus[]>([]);
const companies = ref<CompanyPreference[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const layerLabels: Record<SourceStatus["layer"], string> = {
  official_ats: "Official ATS",
  company_careers: "Company Careers",
  job_aggregator: "Job Aggregators",
  discovery_agent: "Discovery Agent",
};

const roadmapLabels: Record<SourceStatus["admin_status"], string> = {
  live: "Live",
  beta: "Beta",
  planned: "Planned",
  disabled: "Disabled",
};

const roadmapTones: Record<SourceStatus["admin_status"], "success" | "warning" | "info" | "neutral"> = {
  live: "success",
  beta: "warning",
  planned: "info",
  disabled: "neutral",
};

const layerConfidence: Record<SourceStatus["layer"], { stars: number; label: string; tone: "success" | "primary" | "warning" | "info" }> = {
  official_ats: { stars: 5, label: "Official ATS", tone: "success" },
  company_careers: { stars: 4, label: "Company careers", tone: "primary" },
  job_aggregator: { stars: 3, label: "Aggregator", tone: "warning" },
  discovery_agent: { stars: 2, label: "Discovery", tone: "info" },
};

const companyCoverageColumns: TableColumn[] = [
  { key: "company", label: "Company" },
  { key: "connector", label: "Connector" },
  { key: "coverage", label: "Coverage" },
  { key: "confidence", label: "Confidence" },
  { key: "roleFamilies", label: "Role Families" },
];

const sourceByConnector = computed(() => new Map(sources.value.map((source) => [source.connector_key, source])));

function coveragePercent(enabledCount: number, totalCount: number): number {
  if (totalCount <= 0) {
    return 0;
  }
  return (enabledCount / totalCount) * 100;
}

function confidenceBadge(source: SourceStatus | undefined): string {
  if (!source) {
    return "Unassigned";
  }
  const confidence = layerConfidence[source.layer];
  return `${"★".repeat(confidence.stars)}${"☆".repeat(5 - confidence.stars)} ${confidence.label}`;
}

function companyCoverageState(company: CompanyPreference, source: SourceStatus | undefined): {
  label: string;
  tone: "success" | "warning" | "info" | "neutral";
} {
  if (!source) {
    return { label: "No connector", tone: "neutral" };
  }
  if (company.enabled && source.admin_status === "live") {
    return { label: "Monitored", tone: "success" };
  }
  if (company.enabled && source.admin_status === "beta") {
    return { label: "Development", tone: "warning" };
  }
  if (source.admin_status === "planned") {
    return { label: "Planned", tone: "info" };
  }
  if (!company.enabled) {
    return { label: "Catalog Only", tone: "neutral" };
  }
  return { label: roadmapLabels[source.admin_status], tone: roadmapTones[source.admin_status] };
}

const maturitySummary = computed(() => ({
  totalSources: sources.value.length,
  implemented: sources.value.filter((source) => source.admin_status === "live").length,
  inProgress: sources.value.filter((source) => source.admin_status === "beta").length,
  planned: sources.value.filter((source) => source.admin_status === "planned").length,
  liveCompanies: sources.value.reduce((total, source) => total + source.companies_enabled, 0),
  jobsCollected: sources.value.reduce((total, source) => total + source.jobs_collected, 0),
}));

const layerCards = computed(() =>
  Object.entries(layerLabels).map(([layer, label]) => {
    const layerSources = sources.value.filter((source) => source.layer === layer);
    return {
      layer,
      label,
      live: layerSources.filter((source) => source.admin_status === "live").length,
      total: layerSources.length,
      beta: layerSources.filter((source) => source.admin_status === "beta").length,
      planned: layerSources.filter((source) => source.admin_status === "planned").length,
      companies: layerSources.reduce((total, source) => total + source.companies_enabled, 0),
      jobs: layerSources.reduce((total, source) => total + source.jobs_collected, 0),
    };
  }),
);

const connectorCards = computed(() =>
  [...sources.value]
    .sort((left, right) => {
      const layerCompare = left.layer.localeCompare(right.layer);
      if (layerCompare !== 0) {
        return layerCompare;
      }
      const statusOrder = { live: 0, beta: 1, planned: 2, disabled: 3 };
      const statusCompare = statusOrder[left.admin_status] - statusOrder[right.admin_status];
      if (statusCompare !== 0) {
        return statusCompare;
      }
      return left.source.localeCompare(right.source);
    })
    .map((source) => {
      const connectorCoverage = coveragePercent(source.companies_enabled, source.catalog_company_count);
      const confidence = layerConfidence[source.layer];
      return {
        id: source.id,
        source: source.source,
        state: source.state,
        layerLabel: layerLabels[source.layer],
        roadmapLabel: roadmapLabels[source.admin_status],
        roadmapTone: roadmapTones[source.admin_status],
        confidenceLabel: `${"★".repeat(confidence.stars)}${"☆".repeat(5 - confidence.stars)}`,
        enabledCompanies: source.companies_enabled,
        allCompanies: source.catalog_company_count,
        coveragePercent: connectorCoverage,
        cadence: source.cadence_minutes,
        newJobsToday: source.new_jobs_today,
        jobsCollected: source.jobs_collected,
        averageRuntime: source.average_runtime_seconds,
        nextScheduledPoll: source.next_scheduled_poll,
        lastSuccess: source.last_successful_sync,
      };
    }),
);

const companyCoverageRows = computed(() =>
  [...companies.value]
    .map((company) => {
      const source = sourceByConnector.value.get(company.connector);
      const coverageState = companyCoverageState(company, source);
      return {
        id: company.id,
        company: company.company,
        connectorName: source?.source ?? company.connector,
        connectorLayer: source ? layerLabels[source.layer] : "Unknown",
        confidence: confidenceBadge(source),
        coverageState,
        roleFamilies: company.role_families.join(", "),
        priority: company.priority,
        tier: company.tier,
      };
    })
    .sort((left, right) => left.priority - right.priority || left.tier - right.tier || left.company.localeCompare(right.company)),
);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [sourcesPayload, companiesPayload] = await Promise.all([fetchConnectorSources(), fetchCatalogCompanies()]);
    sources.value = sourcesPayload.items;
    companies.value = companiesPayload.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load connector status.";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppPage>
    <PageHeader
      title="Connectors"
      description="Run the internet job discovery roadmap as an operations dashboard: layer maturity, connector coverage, and company support in one place."
    />

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Connector data unavailable" :description="error" />
      </AppGrid>
    </PageSection>

    <template v-else>
      <PageSection>
        <AppGrid columns="4">
          <AppCard title="Total Sources" subtitle="All registered connectors in the discovery engine.">
            <div class="metric-card">
              <strong>{{ maturitySummary.totalSources }}</strong>
              <p>{{ maturitySummary.implemented }} live · {{ maturitySummary.inProgress }} in progress · {{ maturitySummary.planned }} planned</p>
            </div>
          </AppCard>
          <AppCard title="Implemented" subtitle="Connectors already live in production.">
            <div class="metric-card">
              <strong>{{ maturitySummary.implemented }}</strong>
              <p>{{ maturitySummary.liveCompanies }} enabled company boards actively monitored.</p>
            </div>
          </AppCard>
          <AppCard title="In Progress" subtitle="Connectors in active development or beta.">
            <div class="metric-card">
              <strong>{{ maturitySummary.inProgress }}</strong>
              <p>Admin roadmap items that can graduate without scheduler redesign.</p>
            </div>
          </AppCard>
          <AppCard title="Jobs Collected" subtitle="Connector throughput across the latest operating window.">
            <div class="metric-card">
              <strong>{{ formatCompactNumber(maturitySummary.jobsCollected) }}</strong>
              <p>Collected from live and seeded sources across the discovery engine.</p>
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection>
        <AppGrid columns="4">
          <AppCard
            v-for="layer in layerCards"
            :key="layer.layer"
            :title="layer.label"
            :subtitle="`Live: ${layer.live} / ${layer.total}`"
          >
            <div class="layer-card">
              <div>
                <span class="eyebrow">Connectors</span>
                <strong>{{ layer.total }}</strong>
              </div>
              <div>
                <span class="eyebrow">In progress</span>
                <strong>{{ layer.beta }}</strong>
              </div>
              <div>
                <span class="eyebrow">Planned</span>
                <strong>{{ layer.planned }}</strong>
              </div>
              <div>
                <span class="eyebrow">Companies live</span>
                <strong>{{ layer.companies }}</strong>
              </div>
              <div>
                <span class="eyebrow">Jobs collected</span>
                <strong>{{ formatCompactNumber(layer.jobs) }}</strong>
              </div>
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection>
        <AppGrid columns="4">
          <AppCard
            v-for="card in connectorCards"
            :key="card.id"
            :title="card.source"
            :subtitle="`${card.layerLabel} · ${card.enabledCompanies}/${card.allCompanies} enabled companies`"
          >
            <div class="connector-card__stats">
              <div>
                <span class="eyebrow">Roadmap</span>
                <AppBadge :tone="card.roadmapTone">{{ card.roadmapLabel }}</AppBadge>
              </div>
              <div>
                <span class="eyebrow">Confidence</span>
                <strong>{{ card.confidenceLabel }}</strong>
              </div>
              <div>
                <span class="eyebrow">Last success</span>
                <strong>{{ formatDateTime(card.lastSuccess) }}</strong>
              </div>
              <div>
                <span class="eyebrow">Next poll</span>
                <strong>{{ formatDateTime(card.nextScheduledPoll) }}</strong>
              </div>
              <div>
                <span class="eyebrow">Jobs collected</span>
                <strong>{{ card.jobsCollected }}</strong>
              </div>
              <div>
                <span class="eyebrow">Avg runtime</span>
                <strong>{{ formatDurationSeconds(card.averageRuntime) }}</strong>
              </div>
              <div>
                <span class="eyebrow">New today</span>
                <strong>{{ card.newJobsToday }}</strong>
              </div>
              <div>
                <span class="eyebrow">Coverage</span>
                <strong>{{ card.enabledCompanies }}/{{ card.allCompanies }} · {{ formatPercent(card.coveragePercent) }}</strong>
              </div>
              <div>
                <span class="eyebrow">Cadence</span>
                <strong>Every {{ card.cadence }} min</strong>
              </div>
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection>
        <AppGrid columns="1">
          <ConnectorHealthTable :sources="sources" />
        </AppGrid>
      </PageSection>

      <PageSection>
        <AppGrid columns="1">
          <AppCard title="Coverage" subtitle="Company-by-company checklist showing which opportunities are already monitorable and which remain roadmap items.">
            <AppTable :columns="companyCoverageColumns" :has-rows="companyCoverageRows.length > 0" empty-message="No companies in the catalog yet.">
              <tr v-for="row in companyCoverageRows" :key="row.id">
                <td>
                  <strong>{{ row.company }}</strong>
                </td>
                <td>
                  <strong>{{ row.connectorName }}</strong>
                  <p>{{ row.connectorLayer }}</p>
                </td>
                <td>
                  <AppBadge :tone="row.coverageState.tone">{{ row.coverageState.label }}</AppBadge>
                </td>
                <td>{{ row.confidence }}</td>
                <td>{{ row.roleFamilies }}</td>
              </tr>
            </AppTable>
          </AppCard>
        </AppGrid>
      </PageSection>
    </template>
  </AppPage>
</template>

<style scoped>
.metric-card,
.layer-card,
.connector-card__stats {
  display: grid;
  gap: var(--content-gap);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.metric-card {
  grid-template-columns: 1fr;
}

.metric-card strong {
  font-family: var(--font-display);
  font-size: clamp(2rem, 4vw, 3rem);
  line-height: 1;
}

.metric-card p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
  line-height: 1.6;
}

.connector-card__stats strong {
  display: block;
  margin-top: var(--space-2);
}
</style>
