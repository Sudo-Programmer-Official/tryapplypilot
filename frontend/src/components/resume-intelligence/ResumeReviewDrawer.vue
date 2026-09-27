<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ArrowRight, ExternalLink, ShieldCheck, Sparkles } from "lucide-vue-next";

import {
  buildUserApplicationPackage,
  fetchUserResumeIntelligenceVersionContent,
  finalizeUserResumeIntelligenceReview,
} from "../../api/user.api";
import { useToast } from "../../composables/useToast";
import type { ResumeChange, ResumeIntelligenceAnalysis, ResumeVersionRecord } from "../../types";
import AppBadge from "../ui/AppBadge.vue";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";
import AppDrawer from "../ui/AppDrawer.vue";
import AppEmptyState from "../ui/AppEmptyState.vue";
import AppProgress from "../ui/AppProgress.vue";
import AppSkeleton from "../ui/AppSkeleton.vue";
import AppTextArea from "../ui/AppTextArea.vue";

const props = defineProps<{
  open: boolean;
  loading: boolean;
  error: string | null;
  analysis: ResumeIntelligenceAnalysis | null;
}>();

const emit = defineEmits<{
  (event: "close"): void;
}>();

type LocalDecision = "pending" | "approved" | "rejected";

interface LocalChangeReview {
  decision: LocalDecision;
  text: string;
}

const router = useRouter();
const { pushToast } = useToast();
const localReviews = ref<Record<string, LocalChangeReview>>({});
const finalizing = ref(false);
const downloading = ref(false);
const buildingPackage = ref(false);
const generatedVersion = ref<ResumeVersionRecord | null>(null);

watch(
  () => props.analysis,
  (analysis) => {
    const next: Record<string, LocalChangeReview> = {};
    for (const change of analysis?.change_set.changes ?? []) {
      next[change.change_id] = {
        decision: "pending",
        text: change.suggested_text,
      };
    }
    localReviews.value = next;
    generatedVersion.value = null;
  },
  { immediate: true },
);

const approvedCount = computed(() =>
  Object.values(localReviews.value).filter((item) => item.decision === "approved").length,
);

const rejectedCount = computed(() =>
  Object.values(localReviews.value).filter((item) => item.decision === "rejected").length,
);

const pendingCount = computed(() =>
  Object.values(localReviews.value).filter((item) => item.decision === "pending").length,
);

const readyChangeCount = computed(() => props.analysis?.change_set.changes.length ?? 0);
const canFinalize = computed(() => {
  if (!props.analysis || finalizing.value) {
    return false;
  }
  if (props.analysis.change_set.status === "blocked") {
    return false;
  }
  return true;
});

function reviewState(change: ResumeChange): LocalChangeReview {
  return (
    localReviews.value[change.change_id] ?? {
      decision: "pending",
      text: change.suggested_text,
    }
  );
}

function setDecision(changeId: string, decision: LocalDecision): void {
  const current = localReviews.value[changeId];
  if (!current) {
    return;
  }
  localReviews.value = {
    ...localReviews.value,
    [changeId]: {
      ...current,
      decision,
    },
  };
}

function updateText(changeId: string, value: string): void {
  const current = localReviews.value[changeId];
  if (!current) {
    return;
  }
  localReviews.value = {
    ...localReviews.value,
    [changeId]: {
      ...current,
      text: value,
    },
  };
}

function resetChange(change: ResumeChange): void {
  localReviews.value = {
    ...localReviews.value,
    [change.change_id]: {
      decision: "pending",
      text: change.suggested_text,
    },
  };
}

function scoreTone(before: number, after: number): "success" | "warning" | "neutral" {
  if (after > before) {
    return "success";
  }
  if (after < before) {
    return "warning";
  }
  return "neutral";
}

function decisionTone(decision: LocalDecision): "neutral" | "success" | "danger" {
  if (decision === "approved") {
    return "success";
  }
  if (decision === "rejected") {
    return "danger";
  }
  return "neutral";
}

function verdictTone(verdict: string): "success" | "warning" | "danger" | "info" {
  if (verdict === "ready_for_review" || verdict === "strong_current_resume") {
    return "success";
  }
  if (verdict === "review_with_risks") {
    return "warning";
  }
  if (verdict === "blocked") {
    return "danger";
  }
  return "info";
}

function verdictLabel(verdict: string): string {
  if (verdict === "ready_for_review") {
    return "Ready for review";
  }
  if (verdict === "review_with_risks") {
    return "Review with risks";
  }
  if (verdict === "strong_current_resume") {
    return "Strong current resume";
  }
  if (verdict === "blocked") {
    return "Blocked";
  }
  return "In review";
}

function riskTone(level: string): "neutral" | "warning" | "danger" {
  if (level === "high") {
    return "danger";
  }
  if (level === "medium") {
    return "warning";
  }
  return "neutral";
}

async function finalizeDraft(): Promise<void> {
  if (!props.analysis) {
    return;
  }
  finalizing.value = true;
  try {
    const payload = await finalizeUserResumeIntelligenceReview(props.analysis.job.job_id, {
      reviews: Object.entries(localReviews.value).map(([changeId, review]) => ({
        change_id: changeId,
        decision: review.decision,
        edited_text: review.text,
      })),
    });
    generatedVersion.value = payload.item;
    pushToast("Resume version created", `${payload.item.file_name} is ready to download.`, "success");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to finalize resume review.";
    pushToast("Resume finalization failed", message, "error");
  } finally {
    finalizing.value = false;
  }
}

async function downloadGeneratedPdf(): Promise<void> {
  if (!generatedVersion.value) {
    return;
  }
  downloading.value = true;
  try {
    const payload = await fetchUserResumeIntelligenceVersionContent(generatedVersion.value.version_id);
    const binary = window.atob(payload.item.content_base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    const blob = new Blob([bytes], { type: payload.item.mime_type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = payload.item.file_name;
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to download generated PDF.";
    pushToast("Download failed", message, "error");
  } finally {
    downloading.value = false;
  }
}

async function buildApplicationPackage(): Promise<void> {
  if (!props.analysis || !generatedVersion.value) {
    return;
  }
  buildingPackage.value = true;
  try {
    const payload = await buildUserApplicationPackage(props.analysis.job.job_id, {
      resume_version_id: generatedVersion.value.version_id,
      notes: `Built from ${generatedVersion.value.file_name} after resume review.`,
    });
    pushToast("Application package ready", `${payload.item.company} is now tracked in Applications.`, "success");
    emit("close");
    await router.push({
      path: "/user/applications",
      query: { application: payload.item.application_id },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to build application package.";
    pushToast("Package build failed", message, "error");
  } finally {
    buildingPackage.value = false;
  }
}
</script>

<template>
  <AppDrawer
    :open="open"
    side="right"
    width="lg"
    title="Resume review"
    :description="analysis ? `${analysis.job.company} · ${analysis.job.title}` : 'Inspect critique scores and evidence-backed changes.'"
    @close="$emit('close')"
  >
    <div class="resume-review-drawer">
      <div v-if="loading" class="resume-review-loading">
        <AppSkeleton class="resume-review-skeleton resume-review-skeleton--hero" />
        <AppSkeleton class="resume-review-skeleton resume-review-skeleton--panel" />
        <AppSkeleton class="resume-review-skeleton resume-review-skeleton--panel" />
      </div>

      <AppEmptyState
        v-else-if="error"
        title="Resume analysis unavailable"
        :description="error"
      />

      <AppEmptyState
        v-else-if="!analysis"
        title="No analysis loaded"
        description="Choose a job to inspect the selected resume, critique, and proposed changes."
      />

      <template v-else>
        <AppCard class="resume-review-hero">
          <div class="resume-review-hero__header">
            <div>
              <p class="resume-review-eyebrow">Selected resume</p>
              <h3>{{ analysis.selection.display_name || "No resume selected" }}</h3>
              <p class="resume-review-hero__copy">
                {{ analysis.selection.reason_summary[0]?.detail || analysis.change_set.summary }}
              </p>
            </div>
            <AppBadge :tone="verdictTone(analysis.critique.verdict)">
              {{ verdictLabel(analysis.critique.verdict) }}
            </AppBadge>
          </div>

          <div class="resume-review-hero__stats">
            <div class="resume-review-score">
              <AppProgress :value="analysis.critique.overall_before" :size="124" label="Current" />
              <ArrowRight class="resume-review-score__arrow" />
              <AppProgress :value="analysis.critique.overall_after" :size="124" label="Proposed" />
            </div>
            <div class="resume-review-summary">
              <div class="resume-review-summary__chips">
                <AppBadge tone="primary">{{ readyChangeCount }} suggested</AppBadge>
                <AppBadge tone="success">{{ approvedCount }} approved</AppBadge>
                <AppBadge tone="danger">{{ rejectedCount }} rejected</AppBadge>
                <AppBadge tone="neutral">{{ pendingCount }} pending</AppBadge>
              </div>
              <p>{{ analysis.critique.summary }}</p>
              <div class="resume-review-summary__actions">
                <AppButton :href="analysis.job.apply_url" target="_blank" rel="noreferrer">
                  <span class="resume-review-apply-link">
                    Open job
                    <ExternalLink />
                  </span>
                </AppButton>
                <AppButton variant="secondary" :disabled="!canFinalize" @click="finalizeDraft">
                  {{ finalizing ? "Generating PDF..." : "Generate final PDF" }}
                </AppButton>
                <AppButton v-if="generatedVersion" variant="success" :disabled="downloading" @click="downloadGeneratedPdf">
                  {{ downloading ? "Preparing..." : "Download PDF" }}
                </AppButton>
              </div>
            </div>
          </div>
        </AppCard>

        <AppCard
          v-if="generatedVersion"
          title="Generated version"
          subtitle="This saved draft is versioned against the selected resume and target job."
        >
          <div class="resume-review-generated">
            <AppBadge tone="success">{{ generatedVersion.status }}</AppBadge>
            <AppBadge tone="neutral">{{ generatedVersion.file_name }}</AppBadge>
            <AppBadge tone="neutral">{{ generatedVersion.accepted_changes.length }} accepted</AppBadge>
            <AppBadge tone="neutral">{{ generatedVersion.rejected_changes.length }} not applied</AppBadge>
          </div>
          <div class="resume-review-generated__actions">
            <p class="resume-review-generated__copy">
              Use this approved resume version to create the first tracked application package for this job.
            </p>
            <AppButton variant="secondary" :disabled="buildingPackage" @click="buildApplicationPackage">
              {{ buildingPackage ? "Building package..." : "Build application package" }}
            </AppButton>
          </div>
        </AppCard>

        <AppCard title="Critique" subtitle="Deterministic scoring compares the current resume against the proposed draft.">
          <div class="resume-review-dimensions">
            <article v-for="dimension in analysis.critique.dimensions" :key="dimension.label" class="resume-review-dimension">
              <div class="resume-review-dimension__header">
                <strong>{{ dimension.label }}</strong>
                <AppBadge :tone="scoreTone(dimension.before, dimension.after)">
                  {{ dimension.before }}% → {{ dimension.after }}%
                </AppBadge>
              </div>
              <p>{{ dimension.rationale }}</p>
            </article>
          </div>

          <div class="resume-review-columns">
            <div class="resume-review-column">
              <div class="resume-review-column__title">
                <ShieldCheck />
                <strong>Strengths</strong>
              </div>
              <ul class="resume-review-list">
                <li v-for="item in analysis.critique.strengths" :key="item">{{ item }}</li>
              </ul>
            </div>

            <div class="resume-review-column">
              <div class="resume-review-column__title">
                <Sparkles />
                <strong>Issues</strong>
              </div>
              <ul class="resume-review-list">
                <li v-for="item in analysis.critique.issues" :key="item">{{ item }}</li>
              </ul>
            </div>
          </div>
        </AppCard>

        <AppCard
          title="Requirement coverage"
          subtitle="Weak and blocked areas are shown separately so unsupported requirements never slip into the draft."
        >
          <div class="resume-review-requirements">
            <div class="resume-review-requirements__group">
              <span class="resume-review-eyebrow">Weak but supported</span>
              <div class="resume-review-chip-list">
                <AppBadge
                  v-for="item in analysis.gap_analysis.weak_requirements"
                  :key="item.label"
                  tone="warning"
                  size="sm"
                >
                  {{ item.label }}
                </AppBadge>
              </div>
            </div>
            <div class="resume-review-requirements__group">
              <span class="resume-review-eyebrow">Blocked for now</span>
              <div class="resume-review-chip-list">
                <AppBadge
                  v-for="item in analysis.change_set.blocked_requirements"
                  :key="item"
                  tone="danger"
                  size="sm"
                >
                  {{ item }}
                </AppBadge>
              </div>
            </div>
          </div>
        </AppCard>

        <AppCard
          title="Suggested changes"
          subtitle="Approve, reject, or edit each evidence-backed change before finalizing the versioned draft."
        >
          <AppEmptyState
            v-if="analysis.change_set.changes.length === 0"
            title="No changes recommended"
            :description="analysis.change_set.summary"
          />

          <div v-else class="resume-review-change-list">
            <article
              v-for="change in analysis.change_set.changes"
              :key="change.change_id"
              class="resume-review-change-card"
            >
              <div class="resume-review-change-card__header">
                <div>
                  <strong>{{ change.section }} · {{ change.entry_id }}</strong>
                  <p>{{ change.rationale }}</p>
                </div>
                <div class="resume-review-change-card__badges">
                  <AppBadge :tone="decisionTone(reviewState(change).decision)">
                    {{ reviewState(change).decision }}
                  </AppBadge>
                  <AppBadge :tone="riskTone(change.risk_level)" size="sm">
                    {{ change.risk_level }} risk
                  </AppBadge>
                  <AppBadge tone="neutral" size="sm">
                    {{ change.confidence }}% confidence
                  </AppBadge>
                </div>
              </div>

              <div class="resume-review-change-card__grid">
                <div class="resume-review-change-card__panel">
                  <span class="resume-review-eyebrow">Original</span>
                  <p>{{ change.original_text }}</p>
                </div>
                <div class="resume-review-change-card__panel resume-review-change-card__panel--suggested">
                  <span class="resume-review-eyebrow">Suggested</span>
                  <AppTextArea
                    :model-value="reviewState(change).text"
                    label=""
                    :rows="6"
                    hint="Edit wording here before generating the versioned PDF draft."
                    @update:model-value="updateText(change.change_id, String($event ?? ''))"
                  />
                </div>
              </div>

              <div class="resume-review-change-card__meta">
                <div class="resume-review-chip-list">
                  <AppBadge v-for="requirement in change.job_requirements" :key="requirement" tone="primary" size="sm">
                    {{ requirement }}
                  </AppBadge>
                </div>
                <div class="resume-review-chip-list">
                  <AppBadge v-for="evidence in change.evidence" :key="`${change.change_id}-${evidence.source_id}`" tone="info" size="sm">
                    {{ evidence.source_type }}
                  </AppBadge>
                </div>
              </div>

              <div class="resume-review-evidence">
                <article
                  v-for="evidence in change.evidence"
                  :key="`${change.change_id}-${evidence.source_id}-excerpt`"
                  class="resume-review-evidence__card"
                >
                  <span class="resume-review-eyebrow">{{ evidence.source_type }} · {{ Math.round(evidence.confidence * 100) }}%</span>
                  <p>{{ evidence.excerpt }}</p>
                </article>
              </div>

              <div class="resume-review-change-card__actions">
                <AppButton variant="success" @click="setDecision(change.change_id, 'approved')">Approve</AppButton>
                <AppButton variant="danger" @click="setDecision(change.change_id, 'rejected')">Reject</AppButton>
                <AppButton variant="secondary" @click="resetChange(change)">Reset</AppButton>
              </div>
            </article>
          </div>
        </AppCard>
      </template>
    </div>
  </AppDrawer>
</template>

<style scoped>
.resume-review-drawer {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-5);
}

.resume-review-loading {
  display: grid;
  gap: var(--space-4);
}

.resume-review-skeleton--hero {
  min-height: 18rem;
  border-radius: 1.75rem;
}

.resume-review-skeleton--panel {
  min-height: 12rem;
  border-radius: 1.5rem;
}

.resume-review-hero,
.resume-review-dimension,
.resume-review-change-card,
.resume-review-evidence__card {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(246, 249, 253, 0.96));
}

.resume-review-hero__header,
.resume-review-hero__stats,
.resume-review-score,
.resume-review-summary__chips,
.resume-review-summary__actions,
.resume-review-columns,
.resume-review-column__title,
.resume-review-change-card__header,
.resume-review-change-card__badges,
.resume-review-change-card__meta,
.resume-review-change-card__actions,
.resume-review-chip-list,
.resume-review-generated,
.resume-review-generated__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.resume-review-hero__header {
  justify-content: space-between;
  align-items: flex-start;
}

.resume-review-eyebrow {
  color: var(--color-text-muted);
  font-size: var(--type-caption);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.resume-review-hero h3,
.resume-review-column__title strong,
.resume-review-dimension__header strong,
.resume-review-change-card__header strong {
  margin: 0;
  font-family: var(--font-display);
  letter-spacing: -0.03em;
}

.resume-review-hero h3 {
  font-size: clamp(1.55rem, 2vw, 1.9rem);
  margin-top: var(--space-2);
}

.resume-review-hero__copy,
.resume-review-summary p,
.resume-review-dimension p,
.resume-review-change-card__header p,
.resume-review-change-card__panel p,
.resume-review-evidence__card p,
.resume-review-list {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.65;
}

.resume-review-hero__stats {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
}

.resume-review-score {
  align-items: center;
}

.resume-review-score__arrow,
.resume-review-apply-link :deep(svg),
.resume-review-column__title :deep(svg) {
  width: 18px;
  height: 18px;
}

.resume-review-summary {
  display: grid;
  gap: var(--space-3);
}

.resume-review-generated__actions {
  margin-top: var(--space-4);
  justify-content: space-between;
  align-items: center;
}

.resume-review-generated__copy {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.6;
}

.resume-review-apply-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.resume-review-dimensions,
.resume-review-change-list,
.resume-review-evidence {
  display: grid;
  gap: var(--space-4);
}

.resume-review-dimension,
.resume-review-change-card,
.resume-review-evidence__card {
  border: 1px solid rgba(15, 29, 58, 0.08);
  border-radius: 1.5rem;
  padding: var(--space-5);
  box-shadow: 0 12px 26px rgba(15, 29, 58, 0.04);
}

.resume-review-dimension__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.resume-review-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: var(--space-5);
}

.resume-review-column {
  display: grid;
  gap: var(--space-3);
}

.resume-review-column__title {
  align-items: center;
}

.resume-review-list {
  padding-left: 1rem;
}

.resume-review-requirements {
  display: grid;
  gap: var(--space-4);
}

.resume-review-requirements__group {
  display: grid;
  gap: var(--space-3);
}

.resume-review-change-card {
  display: grid;
  gap: var(--space-4);
}

.resume-review-change-card__header {
  justify-content: space-between;
  align-items: flex-start;
}

.resume-review-change-card__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.resume-review-change-card__panel {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: 1.25rem;
  background: rgba(247, 249, 252, 0.9);
  border: 1px solid rgba(15, 29, 58, 0.08);
}

.resume-review-change-card__panel--suggested {
  background: rgba(239, 248, 244, 0.92);
}

.resume-review-evidence {
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
}

.resume-review-evidence__card {
  padding: var(--space-4);
}

@media (max-width: 1023px) {
  .resume-review-hero__stats,
  .resume-review-columns,
  .resume-review-change-card__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .resume-review-drawer {
    padding: var(--space-4);
  }

  .resume-review-hero__header,
  .resume-review-change-card__header,
  .resume-review-change-card__actions,
  .resume-review-generated__actions {
    flex-direction: column;
    align-items: stretch;
  }

  .resume-review-score {
    justify-content: center;
  }
}
</style>
