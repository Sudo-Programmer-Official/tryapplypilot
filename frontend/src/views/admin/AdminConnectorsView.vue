<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import ConnectorHealthTable from "../../components/admin/ConnectorHealthTable.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import { fetchCatalogCompanies } from "../../api/companies.api";
import { fetchConnectorSources } from "../../api/connectors.api";
import type { CompanyPreference, SourceStatus } from "../../types";
import { formatDateTime, formatDurationSeconds } from "../../utils/format";

const sources = ref<SourceStatus[]>([]);
const companies = ref<CompanyPreference[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const connectorCards = computed(() =>
  sources.value.map((source) => {
    const coverage = companies.value.filter((company) => company.connector === source.source);
    return {
      id: source.id,
      source: source.source,
      state: source.state,
      enabledCompanies: coverage.filter((company) => company.enabled).length,
      allCompanies: coverage.length,
      cadence: source.cadence_minutes,
      newJobsToday: source.new_jobs_today,
      jobsCollected: source.jobs_collected,
      averageRuntime: source.average_runtime_seconds,
      nextScheduledPoll: source.next_scheduled_poll,
      lastSuccess: source.last_successful_sync,
    };
  }),
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
      description="Track source health, cadence, and company coverage so expansion stays data-driven instead of hardcoded."
    />

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppEmptyState title="Connector data unavailable" :description="error" />
      </AppGrid>
    </PageSection>

    <template v-else>
      <PageSection>
        <AppGrid columns="4">
          <AppCard
            v-for="card in connectorCards"
            :key="card.id"
            :title="card.source"
            :subtitle="`${card.enabledCompanies}/${card.allCompanies} enabled companies`"
          >
            <div class="connector-card__stats">
              <div>
                <span class="eyebrow">Last success</span>
                <strong>{{ formatDateTime(card.lastSuccess) }}</strong>
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
                <span class="eyebrow">Next poll</span>
                <strong>{{ formatDateTime(card.nextScheduledPoll) }}</strong>
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
    </template>
  </AppPage>
</template>

<style scoped>
.connector-card__stats {
  display: grid;
  gap: var(--content-gap);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.connector-card__stats strong {
  display: block;
  margin-top: var(--space-2);
}
</style>
