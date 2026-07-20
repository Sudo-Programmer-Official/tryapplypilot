<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppCheckbox from "../../components/ui/AppCheckbox.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppSelect from "../../components/ui/AppSelect.vue";
import AppSkeleton from "../../components/ui/AppSkeleton.vue";
import { fetchAdminSettings, saveAdminPreferences } from "../../api/companies.api";
import { connectorOptions } from "../../config/options";
import { useToast } from "../../composables/useToast";
import type { RolePreference, ScoutSettings } from "../../types";
import { joinCsv } from "../../utils/forms";

const { pushToast } = useToast();

const settings = ref<ScoutSettings | null>(null);
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);

function toggleRole(option: RolePreference): void {
  option.enabled = !option.enabled;
}

const defaultUserSettings = computed(() => {
  if (!settings.value) {
    return [];
  }
  return [
    { label: "Minimum match", value: `${settings.value.minimum_match_score}%` },
    { label: "Apply threshold", value: `${settings.value.apply_now_threshold_score}%` },
    { label: "Review threshold", value: `${settings.value.review_threshold_score}%` },
    { label: "Notification freshness", value: `${settings.value.alert_freshness_hours} hours` },
    { label: "Dashboard window", value: `${settings.value.dashboard_freshness_hours} hours` },
    { label: "Default country", value: settings.value.selected_country },
    { label: "Resume variants", value: joinCsv(settings.value.resume_variants) || "Not configured" },
    { label: "Excluded keywords", value: joinCsv(settings.value.excluded_keywords) || "None" },
  ];
});

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
    pushToast("Admin settings saved", "Platform runtime controls are now updated.", "success");
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
  <AppPage class="admin-settings-page">
    <PageHeader title="Settings" description="Control platform-wide runtime behavior, discovery operations, and shared maintenance settings.">
      <template #actions>
        <AppButton :disabled="saving || !settings" @click="persist">{{ saving ? "Saving..." : "Save settings" }}</AppButton>
      </template>
    </PageHeader>

    <PageSection v-if="error">
      <AppGrid columns="1">
        <AppCard title="Settings unavailable" :subtitle="error" />
      </AppGrid>
    </PageSection>

    <PageSection v-else-if="loading">
      <AppGrid columns="2">
        <AppCard v-for="index in 2" :key="index" class="admin-settings-loading-card" title="Loading settings">
          <div class="admin-settings-loading-card__stack">
            <AppSkeleton class="admin-settings-loading-card__line admin-settings-loading-card__line--short" />
            <AppSkeleton v-for="row in 4" :key="row" class="admin-settings-loading-card__line" />
          </div>
        </AppCard>
      </AppGrid>
    </PageSection>

    <template v-else-if="settings">
      <PageSection>
        <AppGrid columns="2">
          <AppCard title="Platform runtime" subtitle="These settings affect connector orchestration and platform-wide scheduling for every user.">
            <div class="app-form-grid">
              <AppSelect
                :model-value="settings.primary_connector"
                label="Primary connector"
                :options="connectorOptions"
                @update:model-value="settings.primary_connector = $event"
              />
              <AppInput
                :model-value="settings.polling_interval_minutes"
                label="Polling interval"
                type="number"
                :min="1"
                @update:model-value="settings.polling_interval_minutes = Number($event) || 5"
              />
            </div>
          </AppCard>

          <AppCard title="Discovery engine" subtitle="These values shape startup backfills, initial syncs, and shared discovery operations across the platform.">
            <div class="app-form-grid">
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
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection>
        <AppGrid columns="2">
          <AppCard title="Shared option sets" subtitle="These are platform-level choices exposed across onboarding, catalog management, and user preference flows.">
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

          <AppCard title="Default user settings" subtitle="Applied only to newly created accounts. Existing users keep their own preferences.">
            <div class="app-stack app-stack--content">
              <AppBadge tone="info">Read only</AppBadge>
              <div class="admin-settings__default-list">
                <div v-for="item in defaultUserSettings" :key="item.label" class="admin-settings__default-row">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>
            </div>
          </AppCard>
        </AppGrid>
      </PageSection>

      <PageSection>
        <AppGrid columns="1">
          <AppCard title="Experience and work modes" subtitle="Platform-defined option pools available inside user preference and onboarding flows.">
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

<style scoped>
.admin-settings-page {
  --page-gap: var(--space-5);
}

.admin-settings__default-list {
  display: grid;
  gap: 0.875rem;
}

.admin-settings-loading-card__stack {
  display: grid;
  gap: var(--space-3);
}

.admin-settings-loading-card__line {
  min-height: 1rem;
}

.admin-settings-loading-card__line--short {
  max-width: 42%;
}

.admin-settings__default-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 0.875rem;
  border-bottom: 1px solid var(--color-border);
}

.admin-settings__default-row:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.admin-settings__default-row span {
  color: var(--color-text-muted);
}

.admin-settings__default-row strong {
  max-width: 16rem;
  text-align: right;
}
</style>
