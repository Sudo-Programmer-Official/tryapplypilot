<script setup lang="ts">
import { computed } from "vue";
import { Bookmark, ExternalLink, MapPin } from "lucide-vue-next";

import AppBadge from "../ui/AppBadge.vue";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";
import AppIconButton from "../ui/AppIconButton.vue";
import type { JobOpportunity } from "../../types";
import { companyMarkStyle, formatRelativeMinutes, getInitials } from "../../utils/format";

const props = defineProps<{
  job: JobOpportunity;
  saved: boolean;
}>();

defineEmits<{
  (event: "toggle-save", jobId: string): void;
}>();

const freshnessTone = computed(() => {
  if (props.job.freshness_tone === "fresh") {
    return "success";
  }
  if (props.job.freshness_tone === "aging") {
    return "warning";
  }
  return "danger";
});

const decisionTone = computed(() => {
  if (props.job.decision === "APPLY_NOW") {
    return "success";
  }
  if (props.job.decision === "REVIEW") {
    return "warning";
  }
  return "neutral";
});

const decisionLabel = computed(() => {
  if (props.job.decision === "APPLY_NOW") {
    return "Apply now";
  }
  if (props.job.decision === "REVIEW") {
    return "Review";
  }
  return "Ignore";
});
</script>

<template>
  <AppCard class="job-row" :padded="false">
    <article class="job-row__body card-content">
      <div class="job-row__primary">
        <div class="job-row__identity">
          <span class="job-row__mark" :style="companyMarkStyle(job.company)">{{ getInitials(job.company) }}</span>
          <div class="job-row__copy">
            <p class="job-row__company">{{ job.company }} · {{ job.source }}</p>
            <h3>{{ job.title }}</h3>
            <div class="job-row__detail-row">
              <AppBadge :tone="freshnessTone" size="sm">Posted {{ formatRelativeMinutes(job.posted_minutes_ago) }}</AppBadge>
              <AppBadge :tone="decisionTone" size="sm">{{ decisionLabel }}</AppBadge>
            </div>
            <span class="job-row__meta">
              <MapPin class="job-row__meta-icon" />
              {{ job.location || job.country_display }} · {{ job.remote_policy }}
            </span>
            <div class="job-row__skills">
              <AppBadge v-for="skill in job.why.slice(0, 4)" :key="skill" tone="neutral" size="sm">{{ skill }}</AppBadge>
            </div>
          </div>
        </div>
      </div>

      <div class="job-row__aside">
        <div class="job-row__score">
          <strong>{{ job.match_score }}%</strong>
          <span>Match</span>
        </div>
        <div class="job-row__actions">
          <AppIconButton size="sm" :label="saved ? 'Remove saved job' : 'Save job'" @click="$emit('toggle-save', job.id)">
            <Bookmark :fill="saved ? 'currentColor' : 'none'" />
          </AppIconButton>
          <AppButton size="sm" :href="job.apply_url" target="_blank" rel="noreferrer">
            <span class="job-row__apply-link">
              Apply
              <ExternalLink />
            </span>
          </AppButton>
        </div>
      </div>
    </article>
  </AppCard>
</template>

<style scoped>
.job-row__body {
  display: grid;
  gap: var(--space-5);
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  padding: var(--space-5);
}

.job-row__primary,
.job-row__copy {
  min-width: 0;
}

.job-row__identity {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
}

.job-row__mark {
  display: grid;
  place-items: center;
  width: 3.1rem;
  height: 3.1rem;
  border-radius: 1rem;
  font-weight: 700;
  flex-shrink: 0;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.42);
}

.job-row__copy {
  display: grid;
  gap: var(--space-3);
}

.job-row__company {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.9rem;
  font-weight: 600;
}

.job-row__detail-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.job-row h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(1.3rem, 1.8vw, 1.7rem);
  line-height: 1.16;
  letter-spacing: -0.03em;
  text-wrap: balance;
}

.job-row__meta {
  color: var(--color-text-muted);
  font-size: 0.95rem;
}

.job-row__meta {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.job-row__meta-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.job-row__skills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.job-row__aside {
  display: grid;
  gap: var(--space-4);
  justify-items: end;
}

.job-row__score {
  display: grid;
  justify-items: center;
  min-width: 5.5rem;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(34, 179, 91, 0.12), rgba(255, 255, 255, 0.96));
  border: 1px solid rgba(34, 179, 91, 0.14);
}

.job-row__score strong {
  font-family: var(--font-display);
  font-size: 1.35rem;
  line-height: 1;
  letter-spacing: -0.03em;
}

.job-row__score span {
  margin-top: var(--space-1);
  color: var(--color-text-muted);
  font-size: var(--type-caption);
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.job-row__actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.job-row__apply-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

@media (max-width: 1023px) {
  .job-row__body {
    grid-template-columns: 1fr;
  }

  .job-row__aside {
    justify-items: start;
  }
}

@media (max-width: 767px) {
  .job-row__body {
    padding: var(--space-4);
    gap: var(--space-4);
  }

  .job-row__identity {
    gap: var(--space-3);
  }

  .job-row__actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
