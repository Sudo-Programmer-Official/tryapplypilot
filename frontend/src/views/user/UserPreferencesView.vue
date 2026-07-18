<script setup lang="ts">
import { computed } from "vue";

import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppCheckbox from "../../components/ui/AppCheckbox.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppSelect from "../../components/ui/AppSelect.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import { useAuth } from "../../composables/useAuth";
import { usePreferences } from "../../composables/usePreferences";
import { useToast } from "../../composables/useToast";
import { countryOptions, experienceLevelOptions, freshnessOptions, notificationFrequencyOptions, workArrangementOptions } from "../../config/options";
import { joinCsv, parseCsv, toggleStringValue } from "../../utils/forms";

const auth = useAuth();
const { pushToast } = useToast();
const { draft, saving, savePreferences: persistPreferences, reset } = usePreferences(auth.user);

const locationsText = computed({
  get: () => joinCsv(draft.value.locations),
  set: (value: string) => {
    draft.value.locations = parseCsv(value);
  },
});

const rolesText = computed({
  get: () => joinCsv(draft.value.preferred_roles),
  set: (value: string) => {
    draft.value.preferred_roles = parseCsv(value);
  },
});

const skillsText = computed({
  get: () => joinCsv(draft.value.skills),
  set: (value: string) => {
    draft.value.skills = parseCsv(value);
  },
});

function toggleWorkArrangement(option: string): void {
  draft.value.work_arrangements = toggleStringValue(draft.value.work_arrangements, option);
}

function toggleExperienceLevel(option: string): void {
  draft.value.experience_levels = toggleStringValue(draft.value.experience_levels, option);
}

async function saveUserPreferences(): Promise<void> {
  await persistPreferences(auth.setUser);
  pushToast("Preferences saved", "Your filters will be used on the next poll cycle.", "success");
}
</script>

<template>
  <AppPage>
    <PageHeader
      title="Preferences"
      description="Set the countries, locations, roles, and thresholds that define what counts as a high-fit opportunity for you."
    >
      <template #actions>
        <div class="app-actions-row">
          <AppButton variant="secondary" @click="reset">Reset</AppButton>
          <AppButton :disabled="saving" @click="saveUserPreferences">{{ saving ? "Saving..." : "Save preferences" }}</AppButton>
        </div>
      </template>
    </PageHeader>

    <AppGrid as="section" columns="2">
      <AppCard title="Location and thresholds" subtitle="Use these settings to limit notifications before scoring and delivery.">
        <div class="app-form-grid">
          <AppSelect
            :model-value="draft.country"
            label="Country"
            :options="countryOptions"
            @update:model-value="draft.country = $event"
          />
          <AppTextArea
            v-model="locationsText"
            label="Locations"
            placeholder="Seattle, Redmond, New York, Remote"
            hint="Use comma-separated values. Matching uses OR logic across locations."
            :rows="3"
          />
          <AppSelect
            :model-value="draft.freshness_hours"
            label="Alert freshness"
            :options="freshnessOptions"
            @update:model-value="draft.freshness_hours = Number($event) || 6"
          />
          <AppInput
            :model-value="draft.minimum_match_score"
            label="Minimum match score"
            type="number"
            :min="0"
            :max="100"
            @update:model-value="draft.minimum_match_score = Number($event) || 0"
          />
          <AppSelect
            :model-value="draft.notification_frequency"
            label="Notification frequency"
            :options="notificationFrequencyOptions"
            @update:model-value="draft.notification_frequency = String($event || 'instant')"
          />
        </div>
      </AppCard>

      <AppCard title="Role focus" subtitle="Give the matcher clear intent about what roles and skills matter most.">
        <div class="app-form-grid">
          <AppTextArea
            v-model="rolesText"
            label="Preferred roles"
            placeholder="Senior Software Engineer, Backend Engineer, AI Engineer"
            hint="Comma-separated titles or role families."
            :rows="4"
          />
          <AppTextArea
            v-model="skillsText"
            label="Priority skills"
            placeholder="Python, distributed systems, ML platform, LLMs"
            hint="These strengthen the score explanation and ranking."
            :rows="4"
          />
        </div>
      </AppCard>
    </AppGrid>

    <AppGrid as="section" columns="2">
      <AppCard title="Work arrangement" subtitle="Choose which workplace models should stay in your radar.">
        <div class="app-actions-row">
          <AppCheckbox
            v-for="option in workArrangementOptions"
            :key="option"
            :model-value="draft.work_arrangements.includes(option)"
            :label="option"
            @update:model-value="toggleWorkArrangement(option)"
          />
        </div>
      </AppCard>

      <AppCard title="Experience level" subtitle="Keep the alerts aligned with the level you want to target right now.">
        <div class="app-actions-row">
          <AppCheckbox
            v-for="option in experienceLevelOptions"
            :key="option"
            :model-value="draft.experience_levels.includes(option)"
            :label="option"
            @update:model-value="toggleExperienceLevel(option)"
          />
        </div>
      </AppCard>
    </AppGrid>
  </AppPage>
</template>
