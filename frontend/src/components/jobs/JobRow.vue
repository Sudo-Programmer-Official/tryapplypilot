<script setup lang="ts">
import { Bookmark, ExternalLink, MapPin } from "lucide-vue-next";

import AppBadge from "../ui/AppBadge.vue";
import AppButton from "../ui/AppButton.vue";
import AppIconButton from "../ui/AppIconButton.vue";
import MatchIndicator from "./MatchIndicator.vue";
import type { JobOpportunity } from "../../types";
import { companyMarkStyle, getInitials } from "../../utils/format";

defineProps<{
  job: JobOpportunity;
  saved: boolean;
}>();

defineEmits<{
  (event: "toggle-save", jobId: string): void;
}>();
</script>

<template>
  <article class="job-row surface-card">
    <div class="job-row__identity">
      <span class="job-row__mark" :style="companyMarkStyle(job.company)">{{ getInitials(job.company) }}</span>
      <div>
        <div class="job-row__title-row">
          <h3>{{ job.title }}</h3>
          <AppBadge tone="success" size="sm">{{ job.freshness_label }}</AppBadge>
        </div>
        <p>{{ job.company }} · {{ job.source }}</p>
        <span class="job-row__meta"><MapPin :size="14" /> {{ job.location || job.country_display }} ({{ job.remote_policy }})</span>
      </div>
    </div>

    <div class="job-row__match">
      <MatchIndicator :score="job.match_score" />
      <div class="job-row__skills">
        <AppBadge v-for="skill in job.why.slice(0, 3)" :key="skill" tone="neutral" size="sm">{{ skill }}</AppBadge>
      </div>
    </div>

    <div class="job-row__actions">
      <AppIconButton :label="saved ? 'Remove saved job' : 'Save job'" @click="$emit('toggle-save', job.id)">
        <Bookmark :size="18" :fill="saved ? 'currentColor' : 'none'" />
      </AppIconButton>
      <AppButton :href="job.apply_url" target="_blank" rel="noreferrer">
        <span class="job-row__apply-link">
          Apply
          <ExternalLink :size="16" />
        </span>
      </AppButton>
    </div>
  </article>
</template>

<style scoped>
.job-row {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4);
  grid-template-columns: minmax(0, 1.6fr) auto auto;
  align-items: center;
}

.job-row__identity {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
}

.job-row__mark {
  display: grid;
  place-items: center;
  width: 3rem;
  height: 3rem;
  border-radius: 1rem;
  font-weight: 700;
}

.job-row__title-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.job-row h3 {
  margin: 0;
  font-size: 1.05rem;
}

.job-row p,
.job-row__meta {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
  font-size: 0.92rem;
}

.job-row__meta {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.job-row__match {
  display: grid;
  gap: var(--space-3);
  justify-items: center;
}

.job-row__skills {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-2);
}

.job-row__actions {
  display: grid;
  gap: var(--space-3);
}

.job-row__apply-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

@media (max-width: 1023px) {
  .job-row {
    grid-template-columns: 1fr;
  }

  .job-row__match,
  .job-row__actions {
    justify-items: start;
  }
}
</style>
