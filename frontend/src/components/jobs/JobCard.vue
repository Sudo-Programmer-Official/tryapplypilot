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
.job-card {
  height: 100%;
}

.job-card :deep(.app-card__body) {
  height: 100%;
  padding: var(--space-6);
  gap: var(--space-5);
}

.job-card__header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--space-4);
  align-items: start;
}

.job-card__header > div {
  min-width: 0;
}

.job-card__mark {
  display: grid;
  place-items: center;
  width: 3.25rem;
  height: 3.25rem;
  border-radius: 1rem;
  font-weight: 700;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.4);
}

.job-card :deep(.match-indicator) {
  width: 4.5rem;
  height: 4.5rem;
  flex-shrink: 0;
}

.job-card h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(1.35rem, 2vw, 1.65rem);
  line-height: 1.15;
  letter-spacing: -0.03em;
  text-wrap: balance;
}

.job-card p {
  margin: var(--space-2) 0 0;
  color: var(--color-text-muted);
  font-size: 0.95rem;
}

.job-card__meta,
.job-card__skills,
.job-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.job-card__actions {
  margin-top: auto;
  align-items: center;
  justify-content: space-between;
}

.job-card__meta :deep(.app-badge),
.job-card__skills :deep(.app-badge) {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.job-card__apply-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
}

@media (max-width: 767px) {
  .job-card :deep(.app-card__body) {
    padding: var(--space-5);
  }

  .job-card__header {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .job-card :deep(.match-indicator) {
    grid-column: 2;
    justify-self: start;
  }

  .job-card__actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
