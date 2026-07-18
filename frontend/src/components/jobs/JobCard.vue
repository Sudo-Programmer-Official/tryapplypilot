<script setup lang="ts">
import { Bookmark, ExternalLink } from "lucide-vue-next";

import AppBadge from "../ui/AppBadge.vue";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";
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
  <AppCard class="job-card">
    <div class="job-card__header">
      <span class="job-card__mark" :style="companyMarkStyle(job.company)">{{ getInitials(job.company) }}</span>
      <div>
        <h3>{{ job.title }}</h3>
        <p>{{ job.company }}</p>
      </div>
      <MatchIndicator :score="job.match_score" />
    </div>

    <div class="job-card__meta">
      <AppBadge tone="success">{{ job.freshness_label }}</AppBadge>
      <AppBadge tone="neutral">{{ job.remote_policy }}</AppBadge>
      <AppBadge tone="neutral">{{ job.location || job.country_display }}</AppBadge>
    </div>

    <div class="job-card__skills">
      <AppBadge v-for="skill in job.why.slice(0, 4)" :key="skill" tone="neutral" size="sm">{{ skill }}</AppBadge>
    </div>

    <div class="job-card__actions">
      <AppIconButton :label="saved ? 'Remove saved job' : 'Save job'" @click="$emit('toggle-save', job.id)">
        <Bookmark :fill="saved ? 'currentColor' : 'none'" />
      </AppIconButton>
      <AppButton block :href="job.apply_url" target="_blank" rel="noreferrer">
        <span class="job-card__apply-link">
          Apply
          <ExternalLink />
        </span>
      </AppButton>
    </div>
  </AppCard>
</template>

<style scoped>
.job-card__header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--content-gap);
  align-items: center;
}

.job-card__mark {
  display: grid;
  place-items: center;
  width: 2.8rem;
  height: 2.8rem;
  border-radius: 0.9rem;
  font-weight: 700;
}

.job-card h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--type-title);
  line-height: 1.2;
}

.job-card p {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
  font-size: var(--type-small);
}

.job-card__meta,
.job-card__skills,
.job-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--content-gap);
}

.job-card__actions {
  align-items: center;
}

.job-card__apply-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
}
</style>
