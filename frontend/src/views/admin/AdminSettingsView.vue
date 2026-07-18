<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppCheckbox from "../../components/ui/AppCheckbox.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppSelect from "../../components/ui/AppSelect.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import { fetchAdminSettings, saveAdminPreferences } from "../../api/companies.api";
import { connectorOptions, countryOptions } from "../../config/options";
import { useToast } from "../../composables/useToast";
import type { RolePreference, ScoutSettings } from "../../types";
import { joinCsv, parseCsv } from "../../utils/forms";

const { pushToast } = useToast();

const settings = ref<ScoutSettings | null>(null);
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);

const excludedKeywordsText = computed({
  get: () => joinCsv(settings.value?.excluded_keywords ?? []),
  set: (value: string) => {
    if (settings.value) {
      settings.value.excluded_keywords = parseCsv(value);
    }
  },
});

const resumeVariantsText = computed({
  get: () => joinCsv(settings.value?.resume_variants ?? []),
  set: (value: string) => {
    if (settings.value) {
      settings.value.resume_variants = parseCsv(value);
    }
  },
});

function toggleRole(option: RolePreference): void {
  option.enabled = !option.enabled;
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    settings.value = await fetchAdminSettings();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load admin settings.";
  } finally {
    loading.value = false;
  }
}

async function persist(): Promise<void> {
  if (!settings.value) {
    return;
  }
  saving.value = true;
  try {
    const payload = await saveAdminPreferences(settings.value);
    settings.value = payload.item;
    pushToast("Admin settings saved", "Runtime preferences are now DB-backed and updated.", "success");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to save admin settings.";
    pushToast("Admin settings failed", message, "error");
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppPage>
    <PageHeader title="Settings" description="Control shared runtime behavior, thresholds, and sync settings from the database-backed admin workspace.">
      <template #actions>
        <AppButton :disabled="saving || !settings" @click="persist">{{ saving ? "Saving..." : "Save settings" }}</AppButton>
      </template>
    </PageHeader>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppCard title="Settings unavailable" :subtitle="error" />
      </AppGrid>
    </PageSection>

    <template v-else-if="settings">
      <PageSection>
        <AppGrid columns="2">
          <AppCard title="Runtime thresholds" subtitle="Core values that shape matching and polling behavior.">
            <div class="app-form-grid">
              <AppSelect
                :model-value="settings.primary_connector"
                label="Primary connector"
                :options="connectorOptions"
                @update:model-value="settings.primary_connector = $event"
              />
              <AppSelect
                :model-value="settings.selected_country"
                label="Default country"
                :options="countryOptions"
                @update:model-value="settings.selected_country = $event"
              />
              <AppInput
                :model-value="settings.polling_interval_minutes"
                label="Polling interval"
                type="number"
                :min="1"
                @update:model-value="settings.polling_interval_minutes = Number($event) || 5"
              />
              <AppInput
                :model-value="settings.minimum_match_score"
                label="Minimum match"
                type="number"
                :min="0"
                :max="100"
                @update:model-value="settings.minimum_match_score = Number($event) || 0"
              />
              <AppInput
                :model-value="settings.apply_now_threshold_score"
                label="Apply now threshold"
                type="number"
                :min="0"
                :max="100"
                @update:model-value="settings.apply_now_threshold_score = Number($event) || 0"
              />
              <AppInput
                :model-value="settings.review_threshold_score"
                label="Review threshold"
                type="number"
                :min="0"
                :max="100"
                @update:model-value="settings.review_threshold_score = Number($event) || 0"
              />
              <AppInput
                :model-value="settings.alert_freshness_hours"
                label="Alert freshness"
                type="number"
                :min="1"
                @update:model-value="settings.alert_freshness_hours = Number($event) || 6"
              />
              <AppInput
                :model-value="settings.dashboard_freshness_hours"
                label="Dashboard freshness"
                type="number"
                :min="1"
                @update:model-value="settings.dashboard_freshness_hours = Number($event) || 24"
              />
            </div>
          </AppCard>

          <AppCard title="Sync controls" subtitle="These values shape initial sync behavior and global low-signal suppression, but matching stays user-driven.">
            <div class="app-form-grid">
              <AppTextArea
                v-model="resumeVariantsText"
                label="Resume variants"
                hint="Comma-separated list of preferred resume variants."
                :rows="3"
              />
              <AppInput
                :model-value="settings.initial_alert_window_hours"
                label="Initial alert window"
                type="number"
                :min="0"
                @update:model-value="settings.initial_alert_window_hours = Number($event) || 0"
              />
              <AppInput
                :model-value="settings.initial_sync_openai_job_limit"
                label="Initial OpenAI job limit"
                type="number"
                :min="0"
                @update:model-value="settings.initial_sync_openai_job_limit = Number($event) || 0"
              />
              <AppInput
                :model-value="settings.initial_sync_max_alerts"
                label="Initial sync max alerts"
                type="number"
                :min="0"
                @update:model-value="settings.initial_sync_max_alerts = Number($event) || 0"
              />
              <AppTextArea
                v-model="excludedKeywordsText"
                label="Excluded keywords"
                hint="Comma-separated exclusions used to suppress low-fit roles."
                :rows="3"
              />
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection>
        <AppGrid columns="2">
          <AppCard title="Role families" subtitle="Catalog-level role families exposed to admin and user flows.">
            <div class="app-checkbox-group">
              <AppCheckbox
                v-for="role in settings.role_families"
                :key="role.label"
                :model-value="role.enabled"
                :label="role.label"
                @update:model-value="toggleRole(role)"
              />
            </div>
          </AppCard>

          <AppCard title="Experience and work modes" subtitle="These defaults appear in the shared configuration and onboarding flow.">
            <div class="app-checkbox-group">
              <AppCheckbox
                v-for="role in settings.work_arrangements"
                :key="`work-${role.label}`"
                :model-value="role.enabled"
                :label="role.label"
                @update:model-value="toggleRole(role)"
              />
              <AppCheckbox
                v-for="role in settings.experience_levels"
                :key="`level-${role.label}`"
                :model-value="role.enabled"
                :label="role.label"
                @update:model-value="toggleRole(role)"
              />
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>
    </template>
  </AppPage>
</template>
