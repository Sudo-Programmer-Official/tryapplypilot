<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { fetchUserApplications } from "../../api/user.api";
import ApplicationPackageDrawer from "../../components/application-intelligence/ApplicationPackageDrawer.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import type { ApplicationRecord, ApplicationTask } from "../../types";
import { companyMarkStyle, formatDate, formatDateTime, getInitials } from "../../utils/format";

type ApplicationQueue = "all" | "ready_to_apply" | "active" | "closed";

const route = useRoute();
const router = useRouter();
const applications = ref<ApplicationRecord[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const activeQueue = ref<ApplicationQueue>("all");

const queueTabs = computed(() => [
  { value: "all" as const, label: "All", count: applications.value.length },
  {
    value: "ready_to_apply" as const,
    label: "Ready",
    count: applications.value.filter((item) => item.status === "ready_to_apply").length,
  },
  {
    value: "active" as const,
    label: "Active",
    count: applications.value.filter((item) => isActiveStatus(item.status)).length,
  },
  {
    value: "closed" as const,
    label: "Closed",
    count: applications.value.filter((item) => isClosedStatus(item.status)).length,
  },
]);

const focusedApplicationId = computed(() => {
  const value = route.query.application;
  return typeof value === "string" ? value : "";
});
const selectedApplication = computed(
  () => applications.value.find((item) => item.application_id === focusedApplicationId.value) ?? null,
);

const filteredApplications = computed(() =>
  applications.value.filter((item) => matchesQueue(item.status, activeQueue.value)),
);

const pendingTaskCount = computed(() =>
  applications.value.reduce(
    (total, item) => total + item.tasks.filter((task) => task.status === "pending" || task.status === "in_progress").length,
    0,
  ),
);

const submittedCount = computed(() => applications.value.filter((item) => item.status === "applied").length);

function isClosedStatus(status: string): boolean {
  return status === "accepted" || status === "rejected" || status === "withdrawn";
}

function isActiveStatus(status: string): boolean {
  return status === "applied" || status === "interviewing" || status === "offer";
}

function matchesQueue(status: string, queue: ApplicationQueue): boolean {
  if (queue === "all") {
    return true;
  }
  if (queue === "ready_to_apply") {
    return status === "ready_to_apply";
  }
  if (queue === "active") {
    return isActiveStatus(status);
  }
  return isClosedStatus(status);
}

function statusLabel(status: string): string {
  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function statusTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "ready_to_apply" || status === "accepted") {
    return "success";
  }
  if (status === "offer" || status === "interviewing") {
    return "info";
  }
  if (status === "rejected" || status === "withdrawn") {
    return "danger";
  }
  if (status === "applied") {
    return "warning";
  }
  return "neutral";
}

function decisionTone(decision: string): "success" | "warning" | "neutral" {
  if (decision === "APPLY_NOW") {
    return "success";
  }
  if (decision === "REVIEW") {
    return "warning";
  }
  return "neutral";
}

function pendingTasks(item: ApplicationRecord): ApplicationTask[] {
  return item.tasks.filter((task) => task.status === "pending" || task.status === "in_progress");
}

function nextDueTask(item: ApplicationRecord): ApplicationTask | null {
  const dueTasks = pendingTasks(item).filter((task) => task.due_at);
  if (dueTasks.length === 0) {
    return null;
  }
  return [...dueTasks].sort((left, right) => String(left.due_at).localeCompare(String(right.due_at)))[0] ?? null;
}

function latestTimelineLabel(item: ApplicationRecord): string {
  if (item.timeline.length === 0) {
    return "No timeline updates yet.";
  }
  const latest = item.timeline[item.timeline.length - 1];
  return latest.occurred_at ? `${latest.label} · ${formatDateTime(latest.occurred_at)}` : latest.label;
}

function resumeLabel(item: ApplicationRecord): string {
  const resumeArtifact = item.artifacts.find((artifact) => artifact.kind === "resume");
  if (resumeArtifact?.file_name) {
    return resumeArtifact.file_name;
  }
  if (resumeArtifact?.label) {
    return resumeArtifact.label;
  }
  return item.resume_version_id;
}

function sortApplications(items: ApplicationRecord[]): ApplicationRecord[] {
  return [...items].sort((left, right) => {
    const leftKey = left.updated_at || left.created_at || "";
    const rightKey = right.updated_at || right.created_at || "";
    return rightKey.localeCompare(leftKey) || right.application_id.localeCompare(left.application_id);
  });
}

async function openApplication(applicationId: string): Promise<void> {
  await router.replace({
    query: {
      ...route.query,
      application: applicationId,
    },
  });
}

async function closeApplication(): Promise<void> {
  const nextQuery = { ...route.query };
  delete nextQuery.application;
  await router.replace({ query: nextQuery });
}

function handleApplicationUpdated(updated: ApplicationRecord): void {
  const next = applications.value.map((item) => (item.application_id === updated.application_id ? updated : item));
  applications.value = sortApplications(next);
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const payload = await fetchUserApplications();
    applications.value = sortApplications(payload.items);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load application packages.";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppPage>
    <PageHeader
      title="Applications"
      description="Turn approved resume versions into reviewable application packages and keep submission state, tasks, and evidence in one workspace."
    >
      <template #actions>
        <AppBadge tone="info">{{ applications.length }} packages</AppBadge>
      </template>
    </PageHeader>

    <PageSection>
      <AppGrid columns="4" class="applications-metrics">
        <AppCard title="Ready to apply" subtitle="Packages prepared from approved resume versions.">
          <div class="applications-metric">
            <strong>{{ queueTabs[1].count }}</strong>
            <p>Review the package, open the official apply link, and record the submission when done.</p>
          </div>
        </AppCard>

        <AppCard title="Submitted" subtitle="Applications already recorded in the workflow history.">
          <div class="applications-metric">
            <strong>{{ submittedCount }}</strong>
            <p>Submission dates and confirmation details stay attached to the job and resume version.</p>
          </div>
        </AppCard>

        <AppCard title="Active" subtitle="In-flight applications still moving through the funnel.">
          <div class="applications-metric">
            <strong>{{ queueTabs[2].count }}</strong>
            <p>Interview, offer, and follow-up states remain in one timeline instead of scattered notes.</p>
          </div>
        </AppCard>

        <AppCard title="Pending tasks" subtitle="Workflow items generated from package and timeline state.">
          <div class="applications-metric">
            <strong>{{ pendingTaskCount }}</strong>
            <p>Deadlines, assessments, and follow-ups surface as explicit tasks instead of memory work.</p>
          </div>
        </AppCard>
      </AppGrid>
    </PageSection>

    <PageSection>
      <AppCard title="Queue" subtitle="Filter the workspace by package readiness and downstream application state.">
        <div class="applications-filters">
          <button
            v-for="queue in queueTabs"
            :key="queue.value"
            class="applications-filter-chip"
            :class="{ 'applications-filter-chip--active': activeQueue === queue.value }"
            type="button"
            @click="activeQueue = queue.value"
          >
            <span>{{ queue.label }}</span>
            <strong>{{ queue.count }}</strong>
          </button>
        </div>
      </AppCard>
    </PageSection>

    <PageSection v-if="loading" class="applications-state">
      <AppGrid columns="1">
        <AppEmptyState title="Loading applications" description="Refreshing application packages and workflow state." />
      </AppGrid>
    </PageSection>

    <PageSection v-else-if="error" class="applications-state">
      <AppGrid columns="1">
        <AppEmptyState title="Applications unavailable" :description="error" />
      </AppGrid>
    </PageSection>

    <PageSection v-else-if="filteredApplications.length === 0" class="applications-state">
      <AppGrid columns="1">
        <AppEmptyState
          title="No application packages yet"
          description="Generate a resume version from a high-match job, then build an application package from that approved draft."
        />
      </AppGrid>
    </PageSection>

    <PageSection v-else>
      <AppGrid columns="2" class="applications-grid">
        <AppCard
          v-for="item in filteredApplications"
          :key="item.application_id"
          class="application-card"
          :class="{ 'application-card--focused': focusedApplicationId === item.application_id }"
        >
          <template #header>
            <div class="application-card__header">
              <div class="application-card__identity">
                <span class="application-card__mark" :style="companyMarkStyle(item.company)">{{ getInitials(item.company) }}</span>
                <div class="application-card__copy">
                  <p class="application-card__company">{{ item.company }}</p>
                  <h3>{{ item.title }}</h3>
                  <p class="application-card__summary">{{ latestTimelineLabel(item) }}</p>
                </div>
              </div>
              <div class="application-card__badges">
                <AppBadge :tone="statusTone(item.status)">{{ statusLabel(item.status) }}</AppBadge>
                <AppBadge :tone="decisionTone(item.decision)">{{ item.decision || "Tracked" }}</AppBadge>
                <AppBadge v-if="item.match_score !== null" tone="primary">{{ item.match_score }}% match</AppBadge>
              </div>
            </div>
          </template>

          <div class="application-card__meta-grid">
            <div class="application-card__meta">
              <span class="application-card__meta-label">Resume</span>
              <strong>{{ resumeLabel(item) }}</strong>
            </div>
            <div class="application-card__meta">
              <span class="application-card__meta-label">Portal</span>
              <strong>{{ item.structured_metadata.application_portal || item.submission.portal || "Direct apply" }}</strong>
            </div>
            <div class="application-card__meta">
              <span class="application-card__meta-label">Created</span>
              <strong>{{ formatDate(item.created_at) }}</strong>
            </div>
            <div class="application-card__meta">
              <span class="application-card__meta-label">Applied</span>
              <strong>{{ formatDate(item.applied_at) }}</strong>
            </div>
          </div>

          <div class="application-card__workflow">
            <div class="application-card__workflow-section">
              <div class="application-card__workflow-header">
                <strong>Next tasks</strong>
                <AppBadge tone="neutral" size="sm">{{ pendingTasks(item).length }} open</AppBadge>
              </div>
              <ul v-if="pendingTasks(item).length > 0" class="application-card__task-list">
                <li v-for="task in pendingTasks(item).slice(0, 3)" :key="task.task_id" class="application-card__task-item">
                  <div>
                    <span>{{ task.label }}</span>
                    <p>{{ task.detail || task.category }}</p>
                  </div>
                  <AppBadge :tone="task.status === 'in_progress' ? 'info' : 'warning'" size="sm">
                    {{ statusLabel(task.status) }}
                  </AppBadge>
                </li>
              </ul>
              <p v-else class="application-card__helper">No open workflow tasks on this package.</p>
            </div>

            <div class="application-card__workflow-section">
              <div class="application-card__workflow-header">
                <strong>Package status</strong>
                <AppBadge tone="info" size="sm">{{ item.artifacts.length }} artifacts</AppBadge>
              </div>
              <p class="application-card__helper">
                {{ item.answers.length }} saved answers · {{ item.notes.length }} notes ·
                {{ nextDueTask(item)?.due_at ? `Next due ${formatDateTime(nextDueTask(item)?.due_at)}` : "No due date set" }}
              </p>
              <p
                v-if="item.structured_metadata.recruiter_name || item.structured_metadata.deadline"
                class="application-card__helper"
              >
                {{
                  item.structured_metadata.recruiter_name
                    ? `Recruiter: ${item.structured_metadata.recruiter_name}`
                    : `Deadline: ${formatDateTime(item.structured_metadata.deadline)}`
                }}
              </p>
            </div>
          </div>

          <template #footer>
            <div class="application-card__actions">
              <AppButton variant="secondary" @click="openApplication(item.application_id)">Manage package</AppButton>
              <AppButton :href="item.apply_url" target="_blank" rel="noreferrer">Open apply link</AppButton>
              <AppButton
                v-if="item.submission.submitted_url"
                variant="secondary"
                :href="item.submission.submitted_url"
                target="_blank"
                rel="noreferrer"
              >
                Open submission
              </AppButton>
            </div>
          </template>
        </AppCard>
      </AppGrid>
    </PageSection>

    <ApplicationPackageDrawer
      :open="Boolean(selectedApplication)"
      :application="selectedApplication"
      @close="closeApplication"
      @updated="handleApplicationUpdated"
    />
  </AppPage>
</template>

<style scoped>
.applications-metrics,
.applications-grid {
  align-items: stretch;
}

.applications-metric,
.applications-filters,
.application-card,
.application-card__header,
.application-card__identity,
.application-card__badges,
.application-card__meta-grid,
.application-card__workflow,
.application-card__workflow-header,
.application-card__actions {
  display: flex;
  gap: var(--space-4);
}

.applications-metric,
.application-card,
.application-card__copy,
.application-card__meta,
.application-card__workflow-section {
  display: grid;
  gap: var(--space-3);
}

.applications-metric strong {
  font-family: var(--font-display);
  font-size: clamp(1.9rem, 3vw, 2.4rem);
  letter-spacing: -0.04em;
}

.applications-metric p,
.application-card__summary,
.application-card__helper,
.application-card__task-item p {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.6;
}

.applications-filters {
  flex-wrap: wrap;
}

.applications-filter-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.74);
  color: var(--color-text);
  font: inherit;
  cursor: pointer;
  transition:
    transform var(--transition-fast),
    border-color var(--transition-fast),
    background var(--transition-fast);
}

.applications-filter-chip:hover {
  transform: translateY(-1px);
}

.applications-filter-chip--active {
  border-color: rgba(37, 99, 255, 0.22);
  background: var(--color-primary-soft);
}

.application-card {
  height: 100%;
}

.application-card--focused {
  border: 1px solid rgba(37, 99, 255, 0.22);
  box-shadow: 0 18px 40px rgba(37, 99, 255, 0.12);
}

.application-card__header,
.application-card__actions {
  justify-content: space-between;
  align-items: flex-start;
}

.application-card__identity {
  align-items: flex-start;
}

.application-card__mark {
  display: grid;
  place-items: center;
  width: 3rem;
  height: 3rem;
  border-radius: 1rem;
  font-weight: 700;
  flex-shrink: 0;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.42);
}

.application-card__copy {
  min-width: 0;
}

.application-card__company,
.application-card__meta-label {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--type-caption);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.application-card h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(1.35rem, 2vw, 1.7rem);
  letter-spacing: -0.03em;
  line-height: 1.2;
}

.application-card__badges,
.application-card__meta-grid {
  flex-wrap: wrap;
}

.application-card__meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  padding: var(--space-4);
  border-radius: 1.25rem;
  background: rgba(247, 249, 252, 0.9);
  border: 1px solid rgba(15, 29, 58, 0.08);
}

.application-card__meta strong,
.application-card__workflow-header strong,
.application-card__task-item span {
  font-weight: 600;
}

.application-card__workflow {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.application-card__workflow-section {
  padding: var(--space-4);
  border-radius: 1.25rem;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(246, 249, 253, 0.96));
  border: 1px solid rgba(15, 29, 58, 0.08);
}

.application-card__task-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: var(--space-3);
}

.application-card__task-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.applications-state {
  padding: 0;
}

@media (max-width: 1023px) {
  .applications-metrics,
  .applications-grid,
  .application-card__workflow {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .application-card__header,
  .application-card__actions,
  .application-card__task-item {
    flex-direction: column;
    align-items: stretch;
  }

  .application-card__meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>
