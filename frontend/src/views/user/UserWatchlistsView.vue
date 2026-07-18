<script setup lang="ts">
import { onMounted, ref } from "vue";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppCheckbox from "../../components/ui/AppCheckbox.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import { createUserWatchlist, deleteUserWatchlist, fetchUserWatchlists, updateUserWatchlist } from "../../api/user.api";
import { useToast } from "../../composables/useToast";
import type { Watchlist } from "../../types";

const { pushToast } = useToast();

const watchlists = ref<Watchlist[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const savingWatchlistId = ref<string | null>(null);
const deletingWatchlistId = ref<string | null>(null);

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
    .map((line) => line.trim())
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
    const payload = await fetchUserWatchlists();
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
  const watchlistKey = watchlist.id || `draft-${index}`;
  savingWatchlistId.value = watchlistKey;
  try {
    const payload = watchlist.id ? await updateUserWatchlist(watchlist) : await createUserWatchlist(watchlist);
    watchlists.value[index] = payload.item;
    pushToast("Watchlist saved", `${payload.item.name} is ready for the next poll cycle.`, "success");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to save watchlist.";
    pushToast("Watchlist save failed", message, "error");
  } finally {
    savingWatchlistId.value = null;
  }
}

async function removeWatchlist(index: number): Promise<void> {
  const watchlist = watchlists.value[index];
  const watchlistKey = watchlist.id || `draft-${index}`;
  if (!watchlist.id) {
    watchlists.value.splice(index, 1);
    return;
  }

  deletingWatchlistId.value = watchlistKey;
  try {
    await deleteUserWatchlist(watchlist.id);
    watchlists.value.splice(index, 1);
    pushToast("Watchlist deleted", `${watchlist.name} is removed from your account.`, "success");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to delete watchlist.";
    pushToast("Delete failed", message, "error");
  } finally {
    deletingWatchlistId.value = null;
  }
}

onMounted(load);
</script>

<template>
  <AppPage>
    <PageHeader
      title="Watchlists"
      description="Create personal company and keyword watchlists that stay attached to your account instead of onboarding state."
    >
      <template #actions>
        <AppButton @click="addWatchlist">Add watchlist</AppButton>
      </template>
    </PageHeader>

    <AppEmptyState v-if="error" title="Watchlists unavailable" :description="error" />
    <AppEmptyState
      v-else-if="!loading && watchlists.length === 0"
      title="No watchlists yet"
      description="Create your first personal watchlist to monitor a narrow set of teams, skills, or companies."
    />

    <AppGrid v-else columns="3">
      <AppCard
        v-for="(watchlist, index) in watchlists"
        :key="watchlist.id || `draft-${index}`"
        :title="watchlist.name || 'New watchlist draft'"
        :subtitle="`${watchlist.terms.length} terms`"
      >
        <div class="app-form-grid">
          <AppInput v-model="watchlist.name" label="Watchlist name" placeholder="AI platform targets" />
          <AppCheckbox :model-value="watchlist.enabled" label="Enabled" @update:model-value="watchlist.enabled = $event" />
          <AppTextArea
            :model-value="serializeTerms(watchlist)"
            label="Terms"
            placeholder="Databricks: Lakeflow&#10;OpenAI: Agents&#10;Platform"
            hint="Use one term per line. Prefix with `Company:` when the term should apply only to a specific company."
            :rows="5"
            @update:model-value="watchlist.terms = parseTerms($event)"
          />
          <div class="app-actions-row">
            <AppButton :disabled="savingWatchlistId === (watchlist.id || `draft-${index}`)" @click="persistWatchlist(index)">
              {{ savingWatchlistId === (watchlist.id || `draft-${index}`) ? "Saving..." : "Save watchlist" }}
            </AppButton>
            <AppButton variant="secondary" :disabled="deletingWatchlistId === (watchlist.id || `draft-${index}`)" @click="removeWatchlist(index)">
              {{ deletingWatchlistId === (watchlist.id || `draft-${index}`) ? "Deleting..." : "Delete" }}
            </AppButton>
          </div>
        </div>
      </AppCard>
    </AppGrid>
  </AppPage>
</template>
