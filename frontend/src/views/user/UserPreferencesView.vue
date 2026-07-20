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
import {
  companyPriorityOptions,
  companySizeOptions,
  countryOptions,
  experienceLevelOptions,
  freshnessOptions,
  industryOptions,
  jobTypeOptions,
  notificationFrequencyOptions,
  notificationRuleOptions,
  remotePreferenceOptions,
  resumeStrategyOptions,
  searchWindowOptions,
  skillImportanceOptions,
  travelPreferenceOptions,
  visaStatusOptions,
  workArrangementOptions,
} from "../../config/options";
import { fetchUserCompanies } from "../../api/user.api";
import { useAuth } from "../../composables/useAuth";
import { usePreferences } from "../../composables/usePreferences";
import { useToast } from "../../composables/useToast";
import type { CompanyPreference, CompanyPriorityLevel } from "../../types";
import { joinCsv, parseCsv, toggleStringValue } from "../../utils/forms";

const auth = useAuth();
const { pushToast } = useToast();
const { draft, saving, savePreferences: persistPreferences, reset } = usePreferences(auth.user);

const companies = ref<CompanyPreference[]>([]);
const companiesLoading = ref(true);

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

const excludedKeywordsText = computed({
  get: () => joinCsv(draft.value.excluded_keywords),
  set: (value: string) => {
    draft.value.excluded_keywords = parseCsv(value);
  },
});

const prioritizedCompanies = computed(() =>
  [...companies.value].sort((left, right) => {
    const rank = (companyName: string) => {
      const priority = draft.value.company_priorities[companyName] ?? "hidden";
      if (priority === "dream") {
        return 0;
      }
      if (priority === "high") {
        return 1;
      }
      if (priority === "normal") {
        return 2;
      }
      return 3;
    };
    return rank(left.company) - rank(right.company) || left.company.localeCompare(right.company);
  }),
);

const manualResumeOptions = computed(() => {
  const profileResumeOptions = (auth.user.value?.profile.resume_library ?? [])
    .map((entry) => String(entry.display_name ?? "").trim())
    .filter(Boolean);
  const explicitSelections = draft.value.preferred_resume_variants.filter(Boolean);
  const fallback = ["Backend", "Platform", "General", "ML", "Frontend"];
  return Array.from(new Set([...profileResumeOptions, ...explicitSelections, ...fallback]));
});

function toggleListValue(
  field:
    | "work_arrangements"
    | "experience_levels"
    | "job_types"
    | "company_sizes"
    | "industries"
    | "notification_rules"
    | "preferred_resume_variants",
  value: string,
): void {
  const nextValues = toggleStringValue(draft.value[field], value);
  switch (field) {
    case "work_arrangements":
      draft.value.work_arrangements = nextValues;
      break;
    case "experience_levels":
      draft.value.experience_levels = nextValues;
      break;
    case "job_types":
      draft.value.job_types = nextValues;
      break;
    case "company_sizes":
      draft.value.company_sizes = nextValues;
      break;
    case "industries":
      draft.value.industries = nextValues;
      break;
    case "notification_rules":
      draft.value.notification_rules = nextValues;
      break;
    case "preferred_resume_variants":
      draft.value.preferred_resume_variants = nextValues;
      break;
  }
}

function setCompanyPriority(companyName: string, priority: string): void {
  draft.value.company_priorities = {
    ...draft.value.company_priorities,
    [companyName]: (priority || "hidden") as CompanyPriorityLevel,
  };
  draft.value.preferred_companies = Object.entries(draft.value.company_priorities)
    .filter(([, value]) => value !== "hidden")
    .map(([company]) => company);
}

function companyPriority(companyName: string): CompanyPriorityLevel {
  return draft.value.company_priorities[companyName] ?? "hidden";
}

function addSkillPriority(): void {
  draft.value.skill_priorities = [...draft.value.skill_priorities, { skill: "", weight: 3 }];
}

function removeSkillPriority(index: number): void {
  draft.value.skill_priorities = draft.value.skill_priorities.filter((_, current) => current !== index);
}

function updateSkillName(index: number, value: string | number): void {
  draft.value.skill_priorities[index].skill = String(value ?? "");
}

function updateSkillWeight(index: number, value: string): void {
  draft.value.skill_priorities[index].weight = Number(value) || 3;
}

async function loadCompanies(): Promise<void> {
  companiesLoading.value = true;
  try {
    const payload = await fetchUserCompanies();
    companies.value = payload.items;
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to load company priorities.";
    pushToast("Company catalog unavailable", message, "error");
  } finally {
    companiesLoading.value = false;
  }
}

async function saveUserPreferences(): Promise<void> {
  await persistPreferences(auth.setUser);
  pushToast("Preferences saved", "Your matching profile and alert rules will be used on the next poll cycle.", "success");
}

onMounted(loadCompanies);
</script>

<template>
  <AppPage>
    <PageHeader
      title="Preferences"
      description="This page is the source of truth for your matching profile. Update your intent here and the next scoring cycle will use it."
    >
      <template #actions>
        <div class="app-actions-row">
          <AppButton variant="secondary" @click="reset">Reset</AppButton>
          <AppButton :disabled="saving" @click="saveUserPreferences">{{ saving ? "Saving..." : "Save preferences" }}</AppButton>
        </div>
      </template>
    </PageHeader>

    <PageSection>
      <AppGrid columns="2">
      <AppCard title="Search territory" subtitle="These filters define where and how you want to work before deeper scoring begins.">
        <div class="app-form-grid">
          <AppSelect
            :model-value="draft.country"
            label="Country"
            :options="countryOptions"
            @update:model-value="draft.country = String($event || 'US')"
          />
          <AppTextArea
            v-model="locationsText"
            label="Locations"
            placeholder="Seattle, Redmond, Bellevue, Remote (US), New York"
            hint="Comma-separated values. Matching uses OR logic across locations."
            :rows="4"
          />
          <AppSelect
            :model-value="draft.remote_preference"
            label="Remote preference"
            :options="remotePreferenceOptions"
            @update:model-value="draft.remote_preference = String($event || 'mostly_remote')"
          />
          <AppSelect
            :model-value="draft.travel_preference"
            label="Travel preference"
            :options="travelPreferenceOptions"
            @update:model-value="draft.travel_preference = String($event || 'up_to_10')"
          />
          <AppSelect
            :model-value="draft.freshness_hours"
            label="Notification freshness"
            :options="freshnessOptions"
            @update:model-value="draft.freshness_hours = Number($event) || 24"
          />
          <AppSelect
            :model-value="draft.search_window_hours"
            label="Dashboard search window"
            :options="searchWindowOptions"
            @update:model-value="draft.search_window_hours = Number($event) || 24 * 7"
          />
          <AppInput
            :model-value="draft.minimum_match_score"
            label="Minimum match score"
            type="number"
            :min="0"
            :max="100"
            @update:model-value="draft.minimum_match_score = Number($event) || 0"
          />
          <AppInput
            :model-value="draft.minimum_salary ?? ''"
            label="Minimum salary"
            type="number"
            :min="0"
            @update:model-value="draft.minimum_salary = Number.isFinite(Number($event)) && Number($event) > 0 ? Number($event) : null"
          />
          <AppInput
            :model-value="draft.desired_salary ?? ''"
            label="Desired salary"
            type="number"
            :min="0"
            @update:model-value="draft.desired_salary = Number.isFinite(Number($event)) && Number($event) > 0 ? Number($event) : null"
          />
          <AppInput
            :model-value="draft.years_of_experience ?? ''"
            label="Years of experience"
            type="number"
            :min="0"
            :max="60"
            @update:model-value="draft.years_of_experience = Number.isFinite(Number($event)) && Number($event) >= 0 ? Number($event) : null"
          />
          <AppSelect
            :model-value="draft.visa_status"
            label="Visa status"
            :options="visaStatusOptions"
            @update:model-value="draft.visa_status = String($event || '')"
          />
        </div>
      </AppCard>

      <AppCard title="Role and level" subtitle="Give the matcher clear intent about titles, seniority, and employment types.">
        <div class="app-form-grid">
          <AppTextArea
            v-model="rolesText"
            label="Preferred roles"
            placeholder="Senior Software Engineer, Backend Engineer, AI Engineer"
            hint="Comma-separated titles or role families."
            :rows="4"
          />
          <div class="preference-cluster">
            <h4>Job types</h4>
            <div class="preference-option-grid">
              <AppCheckbox
                v-for="option in jobTypeOptions"
                :key="option.value"
                :model-value="draft.job_types.includes(String(option.value))"
                :label="option.label"
                @update:model-value="toggleListValue('job_types', String(option.value))"
              />
            </div>
          </div>
          <div class="preference-cluster">
            <h4>Work arrangement</h4>
            <div class="preference-option-grid">
              <AppCheckbox
                v-for="option in workArrangementOptions"
                :key="option"
                :model-value="draft.work_arrangements.includes(option)"
                :label="option"
                @update:model-value="toggleListValue('work_arrangements', option)"
              />
            </div>
          </div>
          <div class="preference-cluster">
            <h4>Seniority</h4>
            <div class="preference-option-grid">
              <AppCheckbox
                v-for="option in experienceLevelOptions"
                :key="option"
                :model-value="draft.experience_levels.includes(option)"
                :label="option"
                @update:model-value="toggleListValue('experience_levels', option)"
              />
            </div>
          </div>
        </div>
      </AppCard>
      </AppGrid>
    </PageSection>

    <PageSection>
      <AppGrid columns="2">
      <AppCard title="Industry fit" subtitle="Use these to express the kind of companies and sectors you want ranked higher.">
        <div class="app-form-grid">
          <div class="preference-cluster">
            <h4>Company size</h4>
            <div class="preference-option-grid">
              <AppCheckbox
                v-for="option in companySizeOptions"
                :key="option.value"
                :model-value="draft.company_sizes.includes(String(option.value))"
                :label="option.label"
                @update:model-value="toggleListValue('company_sizes', String(option.value))"
              />
            </div>
          </div>
          <div class="preference-cluster">
            <h4>Industries</h4>
            <div class="preference-option-grid">
              <AppCheckbox
                v-for="option in industryOptions"
                :key="option.value"
                :model-value="draft.industries.includes(String(option.value))"
                :label="option.label"
                @update:model-value="toggleListValue('industries', String(option.value))"
              />
            </div>
          </div>
        </div>
      </AppCard>

      <AppCard title="Skill importance" subtitle="Weighted skills make your matcher profile more precise than a plain keyword list.">
        <div class="skill-priority-list">
          <div v-for="(entry, index) in draft.skill_priorities" :key="`${entry.skill}-${index}`" class="skill-priority-row">
            <AppInput
              :model-value="entry.skill"
              label="Skill"
              placeholder="Python"
              @update:model-value="updateSkillName(index, $event)"
            />
            <AppSelect
              :model-value="entry.weight"
              label="Weight"
              :options="skillImportanceOptions"
              @update:model-value="updateSkillWeight(index, $event)"
            />
            <AppButton variant="ghost" size="sm" class="skill-priority-remove" @click="removeSkillPriority(index)">Remove</AppButton>
          </div>
          <AppButton variant="secondary" size="sm" @click="addSkillPriority">Add priority skill</AppButton>
        </div>
      </AppCard>
      </AppGrid>
    </PageSection>

    <PageSection>
      <AppGrid columns="2">
      <AppCard title="Company priorities" subtitle="Rank companies explicitly instead of treating every selection the same. Hidden companies stay out of your personalized queue.">
        <div v-if="companiesLoading" class="company-priority-empty">Loading companies…</div>
        <div v-else class="company-priority-list">
          <div v-for="company in prioritizedCompanies" :key="company.id" class="company-priority-row">
            <div>
              <strong>{{ company.company }}</strong>
              <p>{{ company.connector }} · tier {{ company.tier }} · {{ company.country }}</p>
            </div>
            <AppSelect
              :model-value="companyPriority(company.company)"
              :options="companyPriorityOptions"
              @update:model-value="setCompanyPriority(company.company, String($event || 'hidden'))"
            />
          </div>
        </div>
      </AppCard>

      <AppCard title="Notifications and resumes" subtitle="Control how aggressively you want alerts delivered and how resume selection should behave.">
        <div class="app-form-grid">
          <AppSelect
            :model-value="draft.notification_frequency"
            label="Notification frequency"
            :options="notificationFrequencyOptions"
            @update:model-value="draft.notification_frequency = String($event || 'instant')"
          />
          <AppSelect
            :model-value="draft.resume_strategy"
            label="Resume strategy"
            :options="resumeStrategyOptions"
            @update:model-value="draft.resume_strategy = String($event || 'auto')"
          />
          <div class="preference-cluster">
            <h4>Notification rules</h4>
            <div class="preference-option-grid">
              <AppCheckbox
                v-for="option in notificationRuleOptions"
                :key="option.value"
                :model-value="draft.notification_rules.includes(String(option.value))"
                :label="option.label"
                @update:model-value="toggleListValue('notification_rules', String(option.value))"
              />
            </div>
          </div>
          <div v-if="draft.resume_strategy === 'selected_only'" class="preference-cluster">
            <h4>Preferred resumes</h4>
            <div class="preference-option-grid">
              <AppCheckbox
                v-for="resumeName in manualResumeOptions"
                :key="resumeName"
                :model-value="draft.preferred_resume_variants.includes(resumeName)"
                :label="resumeName"
                @update:model-value="toggleListValue('preferred_resume_variants', resumeName)"
              />
            </div>
          </div>
          <AppTextArea
            v-model="excludedKeywordsText"
            label="Excluded keywords"
            placeholder="Sales, Support, Security Clearance, Marketing"
            hint="Comma-separated role or domain terms that should be filtered out early."
            :rows="4"
          />
        </div>
      </AppCard>
      </AppGrid>
    </PageSection>
  </AppPage>
</template>

<style scoped>
.preference-cluster {
  display: grid;
  gap: var(--space-3);
}

.preference-cluster h4 {
  margin: 0;
  font-size: var(--type-small);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.preference-option-grid {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--checkbox-group-gap);
}

.skill-priority-list {
  display: grid;
  gap: var(--space-4);
}

.skill-priority-row {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: minmax(0, 1fr) 140px auto;
  align-items: end;
}

.skill-priority-remove {
  align-self: center;
}

.company-priority-list {
  display: grid;
  gap: var(--space-4);
  max-height: 34rem;
  overflow: auto;
  padding-right: var(--space-2);
}

.company-priority-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: var(--space-4);
  align-items: center;
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.company-priority-row p,
.company-priority-empty {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
}

@media (max-width: 1023px) {
  .skill-priority-row,
  .company-priority-row {
    grid-template-columns: 1fr;
  }
}
</style>
