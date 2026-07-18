<script setup lang="ts">
import { onMounted, ref } from "vue";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppCheckbox from "../../components/ui/AppCheckbox.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppSelect from "../../components/ui/AppSelect.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import { fetchCatalogCompanies, saveCompany } from "../../api/companies.api";
import { connectorOptions, countryOptions } from "../../config/options";
import { useToast } from "../../composables/useToast";
import type { CompanyPreference } from "../../types";
import { joinCsv, parseCsv } from "../../utils/forms";

const { pushToast } = useToast();

const companies = ref<CompanyPreference[]>([]);
const loading = ref(true);
const savingCompanyId = ref<string | null>(null);
const error = ref<string | null>(null);

function blankCompany(): CompanyPreference {
  return {
    id: "",
    company: "",
    enabled: true,
    tier: 1,
    priority: 90,
    connector: "greenhouse",
    poll_interval_minutes: 5,
    country: "US",
    career_url: "",
    external_identifier: "",
    role_families: [],
  };
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const payload = await fetchCatalogCompanies();
    companies.value = payload.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load companies.";
  } finally {
    loading.value = false;
  }
}

function addCompany(): void {
  companies.value = [blankCompany(), ...companies.value];
}

async function persistCompany(index: number): Promise<void> {
  const company = companies.value[index];
  savingCompanyId.value = company.id || `draft-${index}`;
  try {
    const payload = await saveCompany(company);
    companies.value[index] = payload.item;
    pushToast("Company saved", `${payload.item.company} is updated in the catalog.`, "success");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to save company.";
    pushToast("Company save failed", message, "error");
  } finally {
    savingCompanyId.value = null;
  }
}

onMounted(load);
</script>

<template>
  <AppPage>
    <PageHeader title="Companies" description="Manage the DB-backed company catalog instead of relying on environment variables.">
      <template #actions>
        <AppButton @click="addCompany">Add company</AppButton>
      </template>
    </PageHeader>

    <AppCard v-if="error" title="Companies unavailable" :subtitle="error" />

    <AppGrid v-else columns="3">
      <AppCard
        v-for="(company, index) in companies"
        :key="company.id || `draft-${index}`"
        :title="company.company || 'New company draft'"
        :subtitle="`${company.connector} · poll ${company.poll_interval_minutes} min`"
      >
        <div class="app-form-grid">
          <AppInput v-model="company.company" label="Company" placeholder="Microsoft" />
          <AppInput v-model="company.career_url" label="Career URL" placeholder="https://..." />
          <AppInput v-model="company.external_identifier" label="External identifier" placeholder="microsoft" />
          <AppSelect
            :model-value="company.connector"
            label="Connector"
            :options="connectorOptions"
            @update:model-value="company.connector = $event"
          />
          <AppSelect
            :model-value="company.country"
            label="Country"
            :options="countryOptions"
            @update:model-value="company.country = $event"
          />
          <AppInput
            :model-value="company.priority"
            label="Priority"
            type="number"
            :min="1"
            :max="100"
            @update:model-value="company.priority = Number($event) || 0"
          />
          <AppInput
            :model-value="company.tier"
            label="Tier"
            type="number"
            :min="1"
            :max="5"
            @update:model-value="company.tier = Number($event) || 1"
          />
          <AppInput
            :model-value="company.poll_interval_minutes"
            label="Poll interval"
            type="number"
            :min="1"
            @update:model-value="company.poll_interval_minutes = Number($event) || 5"
          />
          <AppTextArea
            :model-value="joinCsv(company.role_families)"
            label="Role families"
            placeholder="Software Engineer, Backend Engineer, Platform Engineer"
            :rows="3"
            @update:model-value="company.role_families = parseCsv($event)"
          />
          <AppCheckbox :model-value="company.enabled" label="Enabled" @update:model-value="company.enabled = $event" />
          <AppButton :disabled="savingCompanyId === (company.id || `draft-${index}`)" @click="persistCompany(index)">
            {{ savingCompanyId === (company.id || `draft-${index}`) ? "Saving..." : "Save company" }}
          </AppButton>
        </div>
      </AppCard>
    </AppGrid>
  </AppPage>
</template>
