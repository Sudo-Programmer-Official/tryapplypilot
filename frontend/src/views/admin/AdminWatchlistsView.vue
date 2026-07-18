<script setup lang="ts">
import { onMounted, ref } from "vue";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppCheckbox from "../../components/ui/AppCheckbox.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import { fetchCatalogWatchlists, saveWatchlist } from "../../api/companies.api";
import { useToast } from "../../composables/useToast";
import type { Watchlist } from "../../types";

const { pushToast } = useToast();

const watchlists = ref<Watchlist[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const savingWatchlistId = ref<string | null>(null);

function blankWatchlist(): Watchlist {
  return {
    id: "",
    name: "",
    enabled: true,
    terms: [],
  };
}

function serializeTerms(watchlist: Watchlist): string {
  return watchlist.terms.map((term) => `${term.company ? `${term.company}: ` : ""}${term.term}`).join("\n");
}

function parseTerms(value: string): Watchlist["terms"] {
  return value
    .split("\n")
    .map((line, index) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [companyPart, ...termParts] = line.split(":");
      const hasCompany = termParts.length > 0;
      return {
        id: `draft-${index}`,
        company: hasCompany ? companyPart.trim() : "",
        term: (hasCompany ? termParts.join(":") : companyPart).trim(),
        enabled: true,
      };
    });
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const payload = await fetchCatalogWatchlists();
    watchlists.value = payload.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load watchlists.";
  } finally {
    loading.value = false;
  }
}

function addWatchlist(): void {
  watchlists.value = [blankWatchlist(), ...watchlists.value];
}

async function persistWatchlist(index: number): Promise<void> {
  const watchlist = watchlists.value[index];
  savingWatchlistId.value = watchlist.id || `draft-${index}`;
  try {
    const payload = await saveWatchlist(watchlist);
    watchlists.value[index] = payload.item;
    pushToast("Watchlist saved", `${payload.item.name} is updated.`, "success");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to save watchlist.";
    pushToast("Watchlist save failed", message, "error");
  } finally {
    savingWatchlistId.value = null;
  }
}

onMounted(load);
</script>

<template>
  <AppPage>
    <PageHeader title="Watchlists" description="Maintain reusable watchlists that job seekers can opt into from their workspace.">
      <template #actions>
        <AppButton @click="addWatchlist">Add watchlist</AppButton>
      </template>
    </PageHeader>

    <AppCard v-if="error" title="Watchlists unavailable" :subtitle="error" />

    <AppGrid v-else columns="3">
      <AppCard
        v-for="(watchlist, index) in watchlists"
        :key="watchlist.id || `draft-${index}`"
        :title="watchlist.name || 'New watchlist draft'"
        :subtitle="`${watchlist.terms.length} terms`"
      >
        <div class="app-form-grid">
          <AppInput v-model="watchlist.name" label="Watchlist name" placeholder="Azure AI" />
          <AppCheckbox :model-value="watchlist.enabled" label="Enabled" @update:model-value="watchlist.enabled = $event" />
          <AppTextArea
            :model-value="serializeTerms(watchlist)"
            label="Terms"
            placeholder="Microsoft: Copilot&#10;OpenAI: Platform"
            hint="Use one term per line. Prefix with `Company:` when you want a company-scoped term."
            :rows="5"
            @update:model-value="watchlist.terms = parseTerms($event)"
          />
          <AppButton :disabled="savingWatchlistId === (watchlist.id || `draft-${index}`)" @click="persistWatchlist(index)">
            {{ savingWatchlistId === (watchlist.id || `draft-${index}`) ? "Saving..." : "Save watchlist" }}
          </AppButton>
        </div>
      </AppCard>
    </AppGrid>
  </AppPage>
</template>
