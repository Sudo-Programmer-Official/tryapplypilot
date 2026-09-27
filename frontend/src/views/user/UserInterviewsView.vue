<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import {
  addUserInterviewQuestionNote,
  approveUserStory,
  archiveUserStory,
  createUserInterview,
  deleteUserInterview,
  fetchUserApplications,
  fetchUserInterviewPreparation,
  fetchUserInterviewQuestionSets,
  fetchUserInterviewStories,
  fetchUserInterviews,
  fetchUserUpcomingInterviews,
  generateUserInterviewPreparation,
  generateUserInterviewQuestions,
  generateUserInterviewStories,
  regenerateUserInterviewPreparation,
  regenerateUserInterviewQuestions,
  regenerateUserStory,
  submitUserProfileEvolutionAnswer,
  updateUserInterview,
  updateUserInterviewQuestion,
  updateUserInterviewPreparation,
  updateUserStory,
} from "../../api/user.api";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppSelect from "../../components/ui/AppSelect.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import type {
  ApplicationRecord,
  InterviewPreparationItem,
  InterviewPreparationPlan,
  InterviewPreparationRisk,
  InterviewPreparationSection,
  InterviewQuestion,
  InterviewQuestionSet,
  InterviewRecord,
  InterviewStory,
  InterviewStoryGapPrompt,
} from "../../types";
import { companyMarkStyle, formatDateTime, getInitials } from "../../utils/format";

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const savingCreate = ref(false);
const savingDetail = ref(false);
const deleting = ref(false);
const generatingPreparation = ref(false);
const regeneratingPreparation = ref(false);
const savingPreparation = ref(false);
const preparationLoading = ref(false);
const generatingQuestions = ref(false);
const regeneratingQuestions = ref(false);
const questionLoading = ref(false);
const generatingStories = ref(false);
const storyLoading = ref(false);
const savingQuestionId = ref("");
const savingQuestionNoteId = ref("");
const savingStoryId = ref("");
const storyActionId = ref("");
const storyPromptSubmittingId = ref("");
const pageError = ref<string | null>(null);
const formError = ref<string | null>(null);
const preparationError = ref<string | null>(null);
const questionError = ref<string | null>(null);
const storyError = ref<string | null>(null);

const applications = ref<ApplicationRecord[]>([]);
const interviews = ref<InterviewRecord[]>([]);
const upcoming = ref<InterviewRecord[]>([]);
const preparationPlan = ref<InterviewPreparationPlan | null>(null);
const questionSets = ref<InterviewQuestionSet[]>([]);
const currentQuestionSet = ref<InterviewQuestionSet | null>(null);
const interviewStories = ref<InterviewStory[]>([]);
const storyDrafts = ref<Record<string, { title: string; measurableOutcomes: string; lessonsLearned: string; tags: string }>>({});
const storyPromptDrafts = ref<Record<string, string>>({});

const createApplicationId = ref("");
const createInterviewType = ref("technical");
const createInterviewRound = ref("Round 1");
const createInterviewStatus = ref("planned");
const createScheduledStart = ref("");
const createScheduledEnd = ref("");
const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
const createTimezone = ref(browserTimezone);
const createMeetingUrl = ref("");
const createRecruiterName = ref("");
const createRecruiterEmail = ref("");
const createNotes = ref("");
const createInterviewersText = ref("");

const detailInterviewType = ref("technical");
const detailInterviewRound = ref("");
const detailInterviewStatus = ref("planned");
const detailPreparationStatus = ref("not_started");
const detailScheduledStart = ref("");
const detailScheduledEnd = ref("");
const detailTimezone = ref(browserTimezone);
const detailMeetingUrl = ref("");
const detailRecruiterName = ref("");
const detailRecruiterEmail = ref("");
const detailNotes = ref("");
const detailInterviewersText = ref("");
const detailChecklist = ref<InterviewPreparationItem[]>([]);
const selectedQuestionSetId = ref("");
const questionCategoryFilter = ref("all");
const questionPriorityFilter = ref("all");
const questionPreparationFilter = ref("all");
const expandedQuestionIds = ref<string[]>([]);
const questionNoteDrafts = ref<Record<string, string>>({});

const interviewTypeOptions = [
  { label: "Recruiter screen", value: "recruiter_screen" },
  { label: "Hiring manager", value: "hiring_manager" },
  { label: "Technical", value: "technical" },
  { label: "Coding", value: "coding" },
  { label: "System design", value: "system_design" },
  { label: "Behavioral", value: "behavioral" },
  { label: "Panel", value: "panel" },
  { label: "Executive", value: "executive" },
  { label: "Onsite", value: "onsite" },
  { label: "Final", value: "final" },
];

const interviewStatusOptions = [
  { label: "Planned", value: "planned" },
  { label: "Scheduled", value: "scheduled" },
  { label: "Completed", value: "completed" },
  { label: "Cancelled", value: "cancelled" },
  { label: "Rescheduled", value: "rescheduled" },
  { label: "No show", value: "no_show" },
];

const preparationStatusOptions = [
  { label: "Not started", value: "not_started" },
  { label: "In progress", value: "in_progress" },
  { label: "Ready", value: "ready" },
  { label: "Completed", value: "completed" },
];

const checklistStatusOptions = [
  { label: "Pending", value: "pending" },
  { label: "In progress", value: "in_progress" },
  { label: "Completed", value: "completed" },
  { label: "Blocked", value: "blocked" },
  { label: "Skipped", value: "skipped" },
];

const questionPriorityOptions = [
  { label: "Must prepare", value: "must_prepare" },
  { label: "High", value: "high" },
  { label: "Medium", value: "medium" },
  { label: "Low", value: "low" },
];

const questionPreparationStatusOptions = [
  { label: "Not started", value: "not_started" },
  { label: "Reviewing", value: "reviewing" },
  { label: "Prepared", value: "prepared" },
  { label: "Needs practice", value: "needs_practice" },
];

const selectedInterviewId = computed(() => {
  const value = route.query.interview;
  return typeof value === "string" ? value : "";
});

const selectedInterview = computed(
  () => interviews.value.find((item) => item.interview_id === selectedInterviewId.value) ?? null,
);

const applicationsById = computed(() => new Map(applications.value.map((item) => [item.application_id, item])));
const totalCompleted = computed(() => interviews.value.filter((item) => item.interview_status === "completed").length);
const totalScheduled = computed(() => interviews.value.filter((item) => item.interview_status === "scheduled").length);
const totalReady = computed(() => interviews.value.filter((item) => item.preparation_status === "ready").length);
const totalPlans = computed(
  () => interviews.value.filter((item) => Boolean((item.metadata as Record<string, unknown>).preparation_plan_current)).length,
);

const applicationOptions = computed(() =>
  applications.value.map((item) => ({
    label: `${item.company} · ${item.title}`,
    value: item.application_id,
  })),
);

const focusLabels = computed(() => preparationPlan.value?.focus_labels ?? []);
const preparationSections = computed(() => preparationPlan.value?.sections ?? []);
const preparationRisks = computed(() => preparationPlan.value?.risks ?? []);
const questionSetOptions = computed(() =>
  questionSets.value.map((item) => ({
    label: `V${item.version_number} · ${humanize(item.status)} · ${item.questions.length} questions`,
    value: item.question_set_id,
  })),
);
const questionCategoryOptions = computed(() => {
  const categories = new Set<string>();
  for (const item of currentQuestionSet.value?.questions ?? []) {
    if (!item.archived) {
      categories.add(item.category);
    }
  }
  return [
    { label: "All categories", value: "all" },
    ...Array.from(categories).sort().map((item) => ({ label: humanize(item), value: item })),
  ];
});
const filteredQuestions = computed(() => {
  const questions = [...(currentQuestionSet.value?.questions ?? [])]
    .filter((item) => !item.archived && !item.hidden)
    .sort((left, right) => left.sequence_order - right.sequence_order || left.question_id.localeCompare(right.question_id));
  return questions.filter((item) => {
    if (questionCategoryFilter.value !== "all" && item.category !== questionCategoryFilter.value) {
      return false;
    }
    if (questionPriorityFilter.value !== "all" && item.priority !== questionPriorityFilter.value) {
      return false;
    }
    if (questionPreparationFilter.value !== "all" && item.preparation_status !== questionPreparationFilter.value) {
      return false;
    }
    return true;
  });
});
const storyLibrarySummary = computed<Record<string, unknown>>(() => {
  const metadata = selectedInterview.value?.metadata as Record<string, unknown> | undefined;
  const summary = metadata?.story_library_current;
  return summary && typeof summary === "object" ? (summary as Record<string, unknown>) : {};
});
const currentStories = computed(() => {
  const groups = new Map<string, InterviewStory[]>();
  for (const item of interviewStories.value) {
    const entries = groups.get(item.story_group_id) ?? [];
    entries.push(item);
    groups.set(item.story_group_id, entries);
  }
  return Array.from(groups.values())
    .map((items) => {
      const ordered = [...items].sort((left, right) => {
        const statusScore = (value: string) => {
          if (value === "review" || value === "draft" || value === "approved") {
            return 0;
          }
          if (value === "archived") {
            return 2;
          }
          return 1;
        };
        const delta = statusScore(left.status) - statusScore(right.status);
        if (delta !== 0) {
          return delta;
        }
        return parseDateValue(right.updated_at || right.created_at) - parseDateValue(left.updated_at || left.created_at);
      });
      return ordered[0];
    })
    .sort(
      (left, right) =>
        right.quality.overall_score - left.quality.overall_score ||
        parseDateValue(right.updated_at || right.created_at) - parseDateValue(left.updated_at || left.created_at),
    );
});
const uncoveredStoryQuestions = computed(() => {
  const uncoveredIds = stringList(storyLibrarySummary.value.uncovered_question_ids);
  const byId = new Map((currentQuestionSet.value?.questions ?? []).map((item) => [item.question_id, item.question]));
  return uncoveredIds.map((item) => byId.get(item) || item);
});

function parseDateValue(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function sortApplications(items: ApplicationRecord[]): ApplicationRecord[] {
  return [...items].sort((left, right) => parseDateValue(right.updated_at || right.created_at) - parseDateValue(left.updated_at || left.created_at));
}

function sortInterviews(items: InterviewRecord[]): InterviewRecord[] {
  return [...items].sort((left, right) => {
    const scheduledDelta = parseDateValue(right.scheduled_start_at || right.updated_at) - parseDateValue(left.scheduled_start_at || left.updated_at);
    if (scheduledDelta !== 0) {
      return scheduledDelta;
    }
    return right.interview_id.localeCompare(left.interview_id);
  });
}

function humanize(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function interviewTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "completed") {
    return "success";
  }
  if (status === "scheduled" || status === "rescheduled") {
    return "info";
  }
  if (status === "cancelled" || status === "no_show") {
    return "danger";
  }
  return "warning";
}

function preparationTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "completed" || status === "ready") {
    return "success";
  }
  if (status === "in_progress" || status === "updated") {
    return "info";
  }
  return "warning";
}

function checklistTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "completed") {
    return "success";
  }
  if (status === "in_progress") {
    return "info";
  }
  if (status === "blocked") {
    return "danger";
  }
  if (status === "skipped") {
    return "neutral";
  }
  return "warning";
}

function riskTone(severity: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (severity === "high") {
    return "danger";
  }
  if (severity === "medium") {
    return "warning";
  }
  return "info";
}

function questionStatusTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "prepared") {
    return "success";
  }
  if (status === "reviewing") {
    return "info";
  }
  if (status === "needs_practice") {
    return "danger";
  }
  return "warning";
}

function priorityTone(priority: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (priority === "must_prepare") {
    return "danger";
  }
  if (priority === "high") {
    return "warning";
  }
  if (priority === "medium") {
    return "info";
  }
  return "neutral";
}

function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}% confidence`;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item).trim()).filter(Boolean) : [];
}

function storyStatusTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "approved") {
    return "success";
  }
  if (status === "review") {
    return "warning";
  }
  if (status === "archived") {
    return "neutral";
  }
  if (status === "superseded") {
    return "info";
  }
  return "warning";
}

function storyQualityTone(score: number): "success" | "warning" | "danger" | "info" | "neutral" {
  if (score >= 80) {
    return "success";
  }
  if (score >= 65) {
    return "info";
  }
  if (score >= 50) {
    return "warning";
  }
  return "danger";
}

function joinLines(values: string[]): string {
  return values.join("\n");
}

function joinTags(values: string[]): string {
  return values.join(", ");
}

function parseLines(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toDateTimeLocal(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const adjusted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return adjusted.toISOString().slice(0, 16);
}

function fromDateTimeLocal(value: string): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toISOString();
}

function parseInterviewers(value: string): Array<Record<string, unknown>> {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [namePart, emailPart = "", titlePart = ""] = line.split("|").map((part) => part.trim());
      return {
        name: namePart,
        email: emailPart,
        title: titlePart,
        role: "interviewer",
      };
    });
}

function formatInterviewers(interview: InterviewRecord | null): string {
  if (!interview || interview.interviewers.length === 0) {
    return "";
  }
  return interview.interviewers.map((item) => [item.name, item.email, item.title].join(" | ")).join("\n");
}

function cloneChecklist(items: InterviewPreparationItem[]): InterviewPreparationItem[] {
  return items.map((item) => ({
    ...item,
    supporting_evidence: item.supporting_evidence.map((reference) => ({
      ...reference,
      metadata: { ...reference.metadata },
    })),
  }));
}

function checklistPayload(items: InterviewPreparationItem[]): Array<Record<string, unknown>> {
  return items.map((item) => ({
    ...item,
    supporting_evidence: item.supporting_evidence.map((reference) => ({
      ...reference,
      metadata: { ...reference.metadata },
    })),
  }));
}

function isMissingPreparationError(error: unknown): boolean {
  return error instanceof Error && error.message.includes("No preparation plan exists");
}

function toggleQuestionExpanded(questionId: string): void {
  const next = new Set(expandedQuestionIds.value);
  if (next.has(questionId)) {
    next.delete(questionId);
  } else {
    next.add(questionId);
  }
  expandedQuestionIds.value = Array.from(next);
}

function isQuestionExpanded(questionId: string): boolean {
  return expandedQuestionIds.value.includes(questionId);
}

function questionNoteDraft(questionId: string): string {
  return questionNoteDrafts.value[questionId] ?? "";
}

function setQuestionNoteDraft(questionId: string, value: string): void {
  questionNoteDrafts.value = {
    ...questionNoteDrafts.value,
    [questionId]: value,
  };
}

function syncStoryDrafts(items: InterviewStory[]): void {
  const next: Record<string, { title: string; measurableOutcomes: string; lessonsLearned: string; tags: string }> = {};
  for (const item of items) {
    next[item.story_id] = {
      title: item.title,
      measurableOutcomes: joinLines(item.measurable_outcomes),
      lessonsLearned: joinLines(item.lessons_learned),
      tags: joinTags(item.tags),
    };
  }
  storyDrafts.value = next;
}

function storyDraft(storyId: string): { title: string; measurableOutcomes: string; lessonsLearned: string; tags: string } {
  return (
    storyDrafts.value[storyId] ?? {
      title: "",
      measurableOutcomes: "",
      lessonsLearned: "",
      tags: "",
    }
  );
}

function setStoryDraftValue(
  storyId: string,
  key: "title" | "measurableOutcomes" | "lessonsLearned" | "tags",
  value: string,
): void {
  storyDrafts.value = {
    ...storyDrafts.value,
    [storyId]: {
      ...storyDraft(storyId),
      [key]: value,
    },
  };
}

function storyPromptDraft(promptId: string): string {
  return storyPromptDrafts.value[promptId] ?? "";
}

function setStoryPromptDraft(promptId: string, value: string): void {
  storyPromptDrafts.value = {
    ...storyPromptDrafts.value,
    [promptId]: value,
  };
}

function storyVersions(storyGroupId: string): InterviewStory[] {
  return [...interviewStories.value]
    .filter((item) => item.story_group_id === storyGroupId)
    .sort((left, right) => right.version_number - left.version_number);
}

function linkedQuestionLabels(story: InterviewStory): string[] {
  const byId = new Map((currentQuestionSet.value?.questions ?? []).map((item) => [item.question_id, item.question]));
  return story.related_question_ids.map((item) => byId.get(item) || item);
}

function resetCreateForm(): void {
  createApplicationId.value = applicationOptions.value[0]?.value ?? "";
  createInterviewType.value = "technical";
  createInterviewRound.value = "Round 1";
  createInterviewStatus.value = "planned";
  createScheduledStart.value = "";
  createScheduledEnd.value = "";
  createTimezone.value = browserTimezone;
  createMeetingUrl.value = "";
  createRecruiterName.value = "";
  createRecruiterEmail.value = "";
  createNotes.value = "";
  createInterviewersText.value = "";
}

function syncDetailForm(interview: InterviewRecord | null): void {
  if (!interview) {
    detailInterviewType.value = "technical";
    detailInterviewRound.value = "";
    detailInterviewStatus.value = "planned";
    detailPreparationStatus.value = "not_started";
    detailScheduledStart.value = "";
    detailScheduledEnd.value = "";
    detailTimezone.value = browserTimezone;
    detailMeetingUrl.value = "";
    detailRecruiterName.value = "";
    detailRecruiterEmail.value = "";
    detailNotes.value = "";
    detailInterviewersText.value = "";
    detailChecklist.value = [];
    return;
  }
  detailInterviewType.value = interview.interview_type;
  detailInterviewRound.value = interview.interview_round;
  detailInterviewStatus.value = interview.interview_status;
  detailPreparationStatus.value = interview.preparation_status;
  detailScheduledStart.value = toDateTimeLocal(interview.scheduled_start_at);
  detailScheduledEnd.value = toDateTimeLocal(interview.scheduled_end_at);
  detailTimezone.value = interview.timezone;
  detailMeetingUrl.value = interview.meeting_url;
  detailRecruiterName.value = interview.recruiter_name;
  detailRecruiterEmail.value = interview.recruiter_email;
  detailNotes.value = interview.notes;
  detailInterviewersText.value = formatInterviewers(interview);
  detailChecklist.value = cloneChecklist(preparationPlan.value?.interview_id === interview.interview_id ? preparationPlan.value.checklist : interview.preparation_checklist);
}

function sectionByKey(key: string): InterviewPreparationSection | null {
  return preparationSections.value.find((item) => item.section_key === key) ?? null;
}

function setCurrentQuestionSet(questionSetId: string): void {
  selectedQuestionSetId.value = questionSetId;
  currentQuestionSet.value = questionSets.value.find((item) => item.question_set_id === questionSetId) ?? null;
  expandedQuestionIds.value = [];
}

async function openInterview(interviewId: string): Promise<void> {
  if (!interviewId || interviewId === selectedInterviewId.value) {
    return;
  }
  await router.replace({
    query: {
      ...route.query,
      interview: interviewId,
    },
  });
}

async function clearSelectedInterview(): Promise<void> {
  if (!selectedInterviewId.value) {
    return;
  }
  const nextQuery = { ...route.query };
  delete nextQuery.interview;
  await router.replace({ query: nextQuery });
}

async function loadPreparation(interviewId: string): Promise<void> {
  preparationLoading.value = true;
  preparationError.value = null;
  if (!interviewId) {
    preparationPlan.value = null;
    detailChecklist.value = [];
    preparationLoading.value = false;
    return;
  }
  try {
    const payload = await fetchUserInterviewPreparation(interviewId);
    preparationPlan.value = payload.item;
    detailChecklist.value = cloneChecklist(payload.item.checklist);
  } catch (error) {
    if (isMissingPreparationError(error)) {
      preparationPlan.value = null;
      detailChecklist.value = cloneChecklist(selectedInterview.value?.preparation_checklist ?? []);
      return;
    }
    preparationPlan.value = null;
    preparationError.value = error instanceof Error ? error.message : "Failed to load interview preparation.";
  } finally {
    preparationLoading.value = false;
  }
}

async function loadQuestionSets(interviewId: string, preferredQuestionSetId = ""): Promise<void> {
  questionLoading.value = true;
  questionError.value = null;
  if (!interviewId) {
    questionSets.value = [];
    currentQuestionSet.value = null;
    selectedQuestionSetId.value = "";
    questionLoading.value = false;
    return;
  }
  try {
    const payload = await fetchUserInterviewQuestionSets(interviewId);
    questionSets.value = payload.items.sort((left, right) => right.version_number - left.version_number);
    const preferredCandidates = [
      preferredQuestionSetId,
      selectedQuestionSetId.value,
      questionSets.value.find((item) => item.status === "active")?.question_set_id ?? "",
      questionSets.value[0]?.question_set_id ?? "",
    ].filter(Boolean);
    const preferred =
      preferredCandidates.find((candidate) => questionSets.value.some((item) => item.question_set_id === candidate)) ||
      "";
    if (preferred) {
      setCurrentQuestionSet(preferred);
    } else {
      currentQuestionSet.value = null;
      selectedQuestionSetId.value = "";
    }
  } catch (error) {
    questionSets.value = [];
    currentQuestionSet.value = null;
    selectedQuestionSetId.value = "";
    questionError.value = error instanceof Error ? error.message : "Failed to load interview question bank.";
  } finally {
    questionLoading.value = false;
  }
}

async function loadStories(interviewId: string): Promise<void> {
  storyLoading.value = true;
  storyError.value = null;
  if (!interviewId) {
    interviewStories.value = [];
    storyDrafts.value = {};
    storyPromptDrafts.value = {};
    storyLoading.value = false;
    return;
  }
  try {
    const payload = await fetchUserInterviewStories(interviewId);
    interviewStories.value = payload.items.sort((left, right) => {
      const delta = parseDateValue(right.updated_at || right.created_at) - parseDateValue(left.updated_at || left.created_at);
      if (delta !== 0) {
        return delta;
      }
      return right.version_number - left.version_number;
    });
    syncStoryDrafts(payload.items);
  } catch (error) {
    interviewStories.value = [];
    storyDrafts.value = {};
    storyPromptDrafts.value = {};
    storyError.value = error instanceof Error ? error.message : "Failed to load interview stories.";
  } finally {
    storyLoading.value = false;
  }
}

async function loadWorkspace(preferredInterviewId = ""): Promise<void> {
  loading.value = true;
  pageError.value = null;
  formError.value = null;
  try {
    const [applicationPayload, interviewPayload, upcomingPayload] = await Promise.all([
      fetchUserApplications(),
      fetchUserInterviews(),
      fetchUserUpcomingInterviews(5),
    ]);
    applications.value = sortApplications(applicationPayload.items);
    interviews.value = sortInterviews(interviewPayload.items);
    upcoming.value = [...upcomingPayload.items].sort((left, right) => parseDateValue(left.scheduled_start_at) - parseDateValue(right.scheduled_start_at));
    resetCreateForm();

    const nextSelected = preferredInterviewId || selectedInterviewId.value;
    if (nextSelected && interviews.value.some((item) => item.interview_id === nextSelected)) {
      syncDetailForm(interviews.value.find((item) => item.interview_id === nextSelected) ?? null);
      await Promise.all([loadPreparation(nextSelected), loadQuestionSets(nextSelected), loadStories(nextSelected)]);
    } else if (interviews.value.length > 0) {
      await openInterview(interviews.value[0].interview_id);
    } else {
      preparationPlan.value = null;
      questionSets.value = [];
      currentQuestionSet.value = null;
      interviewStories.value = [];
      storyDrafts.value = {};
      storyPromptDrafts.value = {};
      selectedQuestionSetId.value = "";
      syncDetailForm(null);
      await clearSelectedInterview();
    }
  } catch (error) {
    pageError.value = error instanceof Error ? error.message : "Failed to load interview workspace.";
  } finally {
    loading.value = false;
  }
}

async function createInterview(): Promise<void> {
  if (!createApplicationId.value) {
    formError.value = "Select an application before creating an interview workspace.";
    return;
  }
  savingCreate.value = true;
  formError.value = null;
  try {
    const payload = await createUserInterview(createApplicationId.value, {
      interview_type: createInterviewType.value,
      interview_round: createInterviewRound.value,
      interview_status: createInterviewStatus.value,
      scheduled_start_at: fromDateTimeLocal(createScheduledStart.value),
      scheduled_end_at: fromDateTimeLocal(createScheduledEnd.value),
      timezone: createTimezone.value,
      meeting_url: createMeetingUrl.value,
      recruiter_name: createRecruiterName.value,
      recruiter_email: createRecruiterEmail.value,
      notes: createNotes.value,
      interviewers: parseInterviewers(createInterviewersText.value),
      source: "manual",
      metadata: {},
    });
    await loadWorkspace(payload.item.interview_id);
  } catch (error) {
    formError.value = error instanceof Error ? error.message : "Failed to create interview workspace.";
  } finally {
    savingCreate.value = false;
  }
}

async function saveInterview(): Promise<void> {
  if (!selectedInterview.value) {
    return;
  }
  savingDetail.value = true;
  formError.value = null;
  try {
    const payload = await updateUserInterview(selectedInterview.value.interview_id, {
      interview_type: detailInterviewType.value,
      interview_round: detailInterviewRound.value,
      interview_status: detailInterviewStatus.value,
      scheduled_start_at: fromDateTimeLocal(detailScheduledStart.value),
      scheduled_end_at: fromDateTimeLocal(detailScheduledEnd.value),
      timezone: detailTimezone.value,
      meeting_url: detailMeetingUrl.value,
      recruiter_name: detailRecruiterName.value,
      recruiter_email: detailRecruiterEmail.value,
      notes: detailNotes.value,
      preparation_status: detailPreparationStatus.value,
      interviewers: parseInterviewers(detailInterviewersText.value),
      metadata: selectedInterview.value.metadata,
    });
    await loadWorkspace(payload.item.interview_id);
  } catch (error) {
    formError.value = error instanceof Error ? error.message : "Failed to update interview workspace.";
  } finally {
    savingDetail.value = false;
  }
}

async function generatePreparation(): Promise<void> {
  if (!selectedInterview.value) {
    return;
  }
  generatingPreparation.value = true;
  preparationError.value = null;
  try {
    await generateUserInterviewPreparation(selectedInterview.value.interview_id);
    await loadWorkspace(selectedInterview.value.interview_id);
  } catch (error) {
    preparationError.value = error instanceof Error ? error.message : "Failed to generate preparation plan.";
  } finally {
    generatingPreparation.value = false;
  }
}

async function regeneratePreparation(): Promise<void> {
  if (!selectedInterview.value) {
    return;
  }
  regeneratingPreparation.value = true;
  preparationError.value = null;
  try {
    await regenerateUserInterviewPreparation(selectedInterview.value.interview_id);
    await loadWorkspace(selectedInterview.value.interview_id);
  } catch (error) {
    preparationError.value = error instanceof Error ? error.message : "Failed to regenerate preparation plan.";
  } finally {
    regeneratingPreparation.value = false;
  }
}

async function savePreparationChecklist(): Promise<void> {
  if (!selectedInterview.value || !preparationPlan.value) {
    return;
  }
  savingPreparation.value = true;
  preparationError.value = null;
  try {
    await updateUserInterviewPreparation(selectedInterview.value.interview_id, {
      checklist: checklistPayload(detailChecklist.value),
      metadata: {
        source: "interview_workspace",
      },
    });
    await loadWorkspace(selectedInterview.value.interview_id);
  } catch (error) {
    preparationError.value = error instanceof Error ? error.message : "Failed to save preparation checklist.";
  } finally {
    savingPreparation.value = false;
  }
}

async function generateQuestions(): Promise<void> {
  if (!selectedInterview.value) {
    return;
  }
  generatingQuestions.value = true;
  questionError.value = null;
  try {
    const payload = await generateUserInterviewQuestions(selectedInterview.value.interview_id);
    await loadWorkspace(selectedInterview.value.interview_id);
    setCurrentQuestionSet(payload.item.question_set_id);
  } catch (error) {
    questionError.value = error instanceof Error ? error.message : "Failed to generate interview questions.";
  } finally {
    generatingQuestions.value = false;
  }
}

async function regenerateQuestions(): Promise<void> {
  if (!selectedInterview.value) {
    return;
  }
  regeneratingQuestions.value = true;
  questionError.value = null;
  try {
    const payload = await regenerateUserInterviewQuestions(selectedInterview.value.interview_id);
    await loadWorkspace(selectedInterview.value.interview_id);
    setCurrentQuestionSet(payload.item.question_set_id);
  } catch (error) {
    questionError.value = error instanceof Error ? error.message : "Failed to regenerate interview questions.";
  } finally {
    regeneratingQuestions.value = false;
  }
}

async function saveQuestion(question: InterviewQuestion): Promise<void> {
  savingQuestionId.value = question.question_id;
  questionError.value = null;
  try {
    await updateUserInterviewQuestion(question.question_id, {
      preparation_status: question.preparation_status,
      priority: question.priority,
      sequence_order: Number(question.sequence_order),
    });
    if (selectedInterview.value) {
      await loadWorkspace(selectedInterview.value.interview_id);
      if (currentQuestionSet.value) {
        setCurrentQuestionSet(currentQuestionSet.value.question_set_id);
      }
    }
  } catch (error) {
    questionError.value = error instanceof Error ? error.message : "Failed to update interview question.";
  } finally {
    savingQuestionId.value = "";
  }
}

async function addQuestionNote(question: InterviewQuestion): Promise<void> {
  const body = questionNoteDraft(question.question_id).trim();
  if (!body) {
    questionError.value = "Add note content before saving.";
    return;
  }
  savingQuestionNoteId.value = question.question_id;
  questionError.value = null;
  try {
    await addUserInterviewQuestionNote(question.question_id, { body });
    setQuestionNoteDraft(question.question_id, "");
    if (selectedInterview.value) {
      await loadWorkspace(selectedInterview.value.interview_id);
      if (currentQuestionSet.value) {
        setCurrentQuestionSet(currentQuestionSet.value.question_set_id);
      }
    }
  } catch (error) {
    questionError.value = error instanceof Error ? error.message : "Failed to add interview question note.";
  } finally {
    savingQuestionNoteId.value = "";
  }
}

async function generateStories(): Promise<void> {
  if (!selectedInterview.value) {
    return;
  }
  generatingStories.value = true;
  storyError.value = null;
  try {
    await generateUserInterviewStories(selectedInterview.value.interview_id);
    await loadWorkspace(selectedInterview.value.interview_id);
  } catch (error) {
    storyError.value = error instanceof Error ? error.message : "Failed to generate interview stories.";
  } finally {
    generatingStories.value = false;
  }
}

async function saveStory(story: InterviewStory): Promise<void> {
  if (!selectedInterview.value) {
    return;
  }
  savingStoryId.value = story.story_id;
  storyError.value = null;
  try {
    const draft = storyDraft(story.story_id);
    await updateUserStory(story.story_id, {
      title: draft.title,
      measurable_outcomes: parseLines(draft.measurableOutcomes),
      lessons_learned: parseLines(draft.lessonsLearned),
      tags: parseTags(draft.tags),
      status: story.status === "approved" ? "review" : story.status,
      metadata: {
        source: "interview_workspace",
      },
    });
    await loadWorkspace(selectedInterview.value.interview_id);
  } catch (error) {
    storyError.value = error instanceof Error ? error.message : "Failed to save interview story.";
  } finally {
    savingStoryId.value = "";
  }
}

async function approveStoryItem(story: InterviewStory): Promise<void> {
  if (!selectedInterview.value) {
    return;
  }
  storyActionId.value = story.story_id;
  storyError.value = null;
  try {
    await approveUserStory(story.story_id);
    await loadWorkspace(selectedInterview.value.interview_id);
  } catch (error) {
    storyError.value = error instanceof Error ? error.message : "Failed to approve interview story.";
  } finally {
    storyActionId.value = "";
  }
}

async function archiveStoryItem(story: InterviewStory): Promise<void> {
  if (!selectedInterview.value) {
    return;
  }
  storyActionId.value = story.story_id;
  storyError.value = null;
  try {
    await archiveUserStory(story.story_id);
    await loadWorkspace(selectedInterview.value.interview_id);
  } catch (error) {
    storyError.value = error instanceof Error ? error.message : "Failed to archive interview story.";
  } finally {
    storyActionId.value = "";
  }
}

async function regenerateStoryItem(story: InterviewStory): Promise<void> {
  if (!selectedInterview.value) {
    return;
  }
  storyActionId.value = story.story_id;
  storyError.value = null;
  try {
    await regenerateUserStory(story.story_id);
    await loadWorkspace(selectedInterview.value.interview_id);
  } catch (error) {
    storyError.value = error instanceof Error ? error.message : "Failed to regenerate interview story.";
  } finally {
    storyActionId.value = "";
  }
}

async function submitStoryPrompt(story: InterviewStory, prompt: InterviewStoryGapPrompt): Promise<void> {
  const answer = storyPromptDraft(prompt.prompt_id).trim();
  if (!answer) {
    storyError.value = "Add an answer before sending the prompt to Profile Evolution review.";
    return;
  }
  storyPromptSubmittingId.value = prompt.prompt_id;
  storyError.value = null;
  try {
    const payload = (prompt.profile_evolution_payload ?? {}) as Record<string, unknown>;
    await submitUserProfileEvolutionAnswer({
      answer,
      topic: String(payload.topic ?? prompt.topic ?? ""),
      question_id: prompt.prompt_id,
      question_prompt: String(payload.question_prompt ?? prompt.prompt),
    });
    await updateUserStory(story.story_id, {
      missing_information_prompts: story.missing_information_prompts.map((item) => ({
        prompt_id: item.prompt_id,
        field_key: item.field_key,
        prompt: item.prompt,
        reason: item.reason,
        topic: item.topic,
        status: item.prompt_id === prompt.prompt_id ? "submitted" : item.status,
        related_evidence: item.related_evidence.map((reference) => ({
          ...reference,
          metadata: { ...reference.metadata },
        })),
        profile_evolution_payload: { ...item.profile_evolution_payload },
        created_at: item.created_at,
        updated_at: item.prompt_id === prompt.prompt_id ? new Date().toISOString() : item.updated_at,
      })),
      metadata: {
        source: "interview_story_gap_prompt",
      },
    });
    setStoryPromptDraft(prompt.prompt_id, "");
    if (selectedInterview.value) {
      await loadStories(selectedInterview.value.interview_id);
    }
  } catch (error) {
    storyError.value = error instanceof Error ? error.message : "Failed to submit story follow-up prompt.";
  } finally {
    storyPromptSubmittingId.value = "";
  }
}

async function removeInterview(): Promise<void> {
  if (!selectedInterview.value) {
    return;
  }
  deleting.value = true;
  formError.value = null;
  try {
    await deleteUserInterview(selectedInterview.value.interview_id);
    await loadWorkspace();
  } catch (error) {
    formError.value = error instanceof Error ? error.message : "Failed to delete interview workspace.";
  } finally {
    deleting.value = false;
  }
}

watch(
  selectedInterviewId,
  (interviewId, previousInterviewId) => {
    if (interviewId === previousInterviewId) {
      return;
    }
    const interview = interviews.value.find((item) => item.interview_id === interviewId) ?? null;
    syncDetailForm(interview);
    if (interviewId) {
      void Promise.all([loadPreparation(interviewId), loadQuestionSets(interviewId), loadStories(interviewId)]);
    } else {
      preparationPlan.value = null;
      preparationError.value = null;
      questionSets.value = [];
      currentQuestionSet.value = null;
      interviewStories.value = [];
      storyDrafts.value = {};
      storyPromptDrafts.value = {};
      storyError.value = null;
      selectedQuestionSetId.value = "";
      questionError.value = null;
    }
  },
);

watch(selectedQuestionSetId, (questionSetId, previousQuestionSetId) => {
  if (!questionSetId || questionSetId === previousQuestionSetId) {
    return;
  }
  currentQuestionSet.value = questionSets.value.find((item) => item.question_set_id === questionSetId) ?? null;
  expandedQuestionIds.value = [];
});

onMounted(() => {
  void loadWorkspace();
});
</script>

<template>
  <AppPage>
    <PageHeader
      title="Interview Intelligence"
      description="Keep canonical interview workspaces attached to applications, then generate evidence-backed preparation from the submitted resume, recruiter context, and approved knowledge."
    >
      <template #actions>
        <AppBadge tone="info">{{ interviews.length }} interviews</AppBadge>
      </template>
    </PageHeader>

    <PageSection>
      <AppGrid columns="4" class="interview-metrics">
        <AppCard title="Upcoming" subtitle="Interviews that still need active preparation.">
          <div class="interview-metric">
            <strong>{{ upcoming.length }}</strong>
            <p>These are the interviews that should drive the next preparation cycle.</p>
          </div>
        </AppCard>

        <AppCard title="Scheduled" subtitle="Canonical interview records with an active time on the calendar.">
          <div class="interview-metric">
            <strong>{{ totalScheduled }}</strong>
            <p>Scheduling context stays attached to the application workflow instead of living in notes.</p>
          </div>
        </AppCard>

        <AppCard title="Preparation ready" subtitle="Interviews explicitly marked ready for execution.">
          <div class="interview-metric">
            <strong>{{ totalReady }}</strong>
            <p>Preparation status is still user-controlled even after the plan is generated.</p>
          </div>
        </AppCard>

        <AppCard title="Preparation plans" subtitle="Interviews that already have an evidence-backed plan.">
          <div class="interview-metric">
            <strong>{{ totalPlans }}</strong>
            <p>Generated plans are versioned so the workspace can evolve without losing history.</p>
          </div>
        </AppCard>
      </AppGrid>
    </PageSection>

    <PageSection v-if="loading">
      <AppEmptyState title="Loading interviews" description="Refreshing interview workspaces, application context, and preparation state." />
    </PageSection>

    <PageSection v-else-if="pageError">
      <AppEmptyState title="Interview workspace unavailable" :description="pageError" />
    </PageSection>

    <PageSection v-else>
      <div class="interview-workspace">
        <AppCard title="Create interview workspace" subtitle="Start from an existing application and capture the canonical interview record before generating preparation.">
          <div class="interview-form">
            <AppSelect v-model="createApplicationId" label="Application" :options="applicationOptions" />
            <AppGrid columns="2" gap="content">
              <AppSelect v-model="createInterviewType" label="Interview type" :options="interviewTypeOptions" />
              <AppSelect v-model="createInterviewStatus" label="Status" :options="interviewStatusOptions" />
            </AppGrid>
            <AppInput v-model="createInterviewRound" label="Round" placeholder="Round 1" />
            <AppInput v-model="createScheduledStart" label="Start" type="datetime-local" />
            <AppInput v-model="createScheduledEnd" label="End" type="datetime-local" />
            <AppInput v-model="createTimezone" label="Timezone" placeholder="America/Denver" />
            <AppInput v-model="createMeetingUrl" label="Meeting URL" placeholder="https://meet.example.com/interview" />
            <AppGrid columns="2" gap="content">
              <AppInput v-model="createRecruiterName" label="Recruiter name" placeholder="Avery Chen" />
              <AppInput v-model="createRecruiterEmail" label="Recruiter email" placeholder="avery@example.com" />
            </AppGrid>
            <AppTextArea
              v-model="createInterviewersText"
              label="Interviewer list"
              placeholder="Taylor | taylor@example.com | Hiring Manager"
              :rows="4"
              hint="One interviewer per line. Format: name | email | title"
            />
            <AppTextArea v-model="createNotes" label="Notes" placeholder="Capture scheduling context, agenda, or recruiter cues before preparation is generated." :rows="4" />
            <p v-if="formError" class="interview-inline-error">{{ formError }}</p>
            <AppButton variant="primary" :disabled="savingCreate || applicationOptions.length === 0" @click="createInterview">
              {{ savingCreate ? "Creating..." : "Create interview workspace" }}
            </AppButton>
          </div>
        </AppCard>

        <div class="interview-detail">
          <AppCard title="Upcoming queue" subtitle="Select the interview workspace that should drive the next preparation cycle.">
            <div v-if="interviews.length === 0" class="interview-empty-copy">
              No interview workspaces exist yet.
            </div>
            <div v-else class="interview-list">
              <button
                v-for="item in interviews"
                :key="item.interview_id"
                class="interview-list-item"
                :class="{ 'interview-list-item--active': item.interview_id === selectedInterviewId }"
                type="button"
                @click="openInterview(item.interview_id)"
              >
                <div class="interview-list-item__header">
                  <div class="interview-list-item__avatar" :style="companyMarkStyle(String(item.metadata.application_company || item.application_id))">
                    {{ getInitials(String(item.metadata.application_company || "Interview")) }}
                  </div>
                  <div class="interview-list-item__copy">
                    <strong>{{ applicationsById.get(item.application_id)?.company || item.metadata.application_company || "Application" }}</strong>
                    <span>{{ applicationsById.get(item.application_id)?.title || item.metadata.application_title || item.interview_round }}</span>
                  </div>
                </div>
                <h3>{{ item.interview_round }} · {{ humanize(item.interview_type) }}</h3>
                <p>{{ item.scheduled_start_at ? formatDateTime(item.scheduled_start_at) : "No time scheduled yet" }}</p>
                <div class="interview-list-item__meta">
                  <AppBadge :tone="interviewTone(item.interview_status)">{{ humanize(item.interview_status) }}</AppBadge>
                  <AppBadge :tone="preparationTone(item.preparation_status)">{{ humanize(item.preparation_status) }}</AppBadge>
                </div>
              </button>
            </div>
          </AppCard>

          <AppEmptyState
            v-if="interviews.length > 0 && !selectedInterview"
            title="Select an interview"
            description="Choose an interview workspace from the queue to review details, generate preparation, and keep the timeline current."
          />

          <template v-else-if="selectedInterview">
            <AppCard :title="`${selectedInterview.interview_round} · ${humanize(selectedInterview.interview_type)}`" :subtitle="applicationsById.get(selectedInterview.application_id)?.company || 'Linked application'">
              <template #actions>
                <div class="interview-actions">
                  <AppBadge :tone="interviewTone(selectedInterview.interview_status)">{{ humanize(selectedInterview.interview_status) }}</AppBadge>
                  <AppBadge :tone="preparationTone(selectedInterview.preparation_status)">{{ humanize(selectedInterview.preparation_status) }}</AppBadge>
                </div>
              </template>

              <div class="interview-hero">
                <div class="interview-hero__avatar" :style="companyMarkStyle(applicationsById.get(selectedInterview.application_id)?.company || selectedInterview.interview_round)">
                  {{ getInitials(applicationsById.get(selectedInterview.application_id)?.company || "Interview") }}
                </div>
                <div class="interview-hero__copy">
                  <strong>{{ applicationsById.get(selectedInterview.application_id)?.company || "Application" }}</strong>
                  <span>{{ applicationsById.get(selectedInterview.application_id)?.title || selectedInterview.interview_round }}</span>
                  <p>{{ selectedInterview.scheduled_start_at ? `${formatDateTime(selectedInterview.scheduled_start_at)} · ${selectedInterview.timezone}` : "Schedule details have not been finalized yet." }}</p>
                </div>
              </div>
            </AppCard>

            <AppCard title="Interview details" subtitle="Update schedule, recruiter references, notes, and explicit preparation state on the canonical interview record.">
              <div class="interview-form">
                <AppGrid columns="2" gap="content">
                  <AppSelect v-model="detailInterviewType" label="Interview type" :options="interviewTypeOptions" />
                  <AppSelect v-model="detailInterviewStatus" label="Status" :options="interviewStatusOptions" />
                </AppGrid>
                <AppGrid columns="2" gap="content">
                  <AppInput v-model="detailInterviewRound" label="Round" placeholder="Round 2" />
                  <AppSelect v-model="detailPreparationStatus" label="Preparation status" :options="preparationStatusOptions" />
                </AppGrid>
                <AppGrid columns="2" gap="content">
                  <AppInput v-model="detailScheduledStart" label="Start" type="datetime-local" />
                  <AppInput v-model="detailScheduledEnd" label="End" type="datetime-local" />
                </AppGrid>
                <AppInput v-model="detailTimezone" label="Timezone" placeholder="America/Denver" />
                <AppInput v-model="detailMeetingUrl" label="Meeting URL" placeholder="https://meet.example.com/interview" />
                <AppGrid columns="2" gap="content">
                  <AppInput v-model="detailRecruiterName" label="Recruiter name" placeholder="Avery Chen" />
                  <AppInput v-model="detailRecruiterEmail" label="Recruiter email" placeholder="avery@example.com" />
                </AppGrid>
                <AppTextArea
                  v-model="detailInterviewersText"
                  label="Interviewer list"
                  placeholder="Taylor | taylor@example.com | Hiring Manager"
                  :rows="4"
                  hint="One interviewer per line. Format: name | email | title"
                />
                <AppTextArea v-model="detailNotes" label="Notes" placeholder="Capture prep context, agenda, and follow-ups." :rows="4" />
                <div class="interview-actions">
                  <AppButton variant="primary" :disabled="savingDetail" @click="saveInterview">
                    {{ savingDetail ? "Saving..." : "Save interview" }}
                  </AppButton>
                  <AppButton variant="danger" :disabled="deleting" @click="removeInterview">
                    {{ deleting ? "Deleting..." : "Delete interview" }}
                  </AppButton>
                </div>
              </div>
            </AppCard>

            <AppCard title="Preparation plan" subtitle="Generate and iterate on an evidence-backed preparation plan using the submitted resume, recruiter context, and approved knowledge.">
              <template #actions>
                <div class="interview-actions">
                  <AppButton
                    v-if="!preparationPlan"
                    variant="primary"
                    :disabled="generatingPreparation || preparationLoading"
                    @click="generatePreparation"
                  >
                    {{ generatingPreparation ? "Generating..." : "Generate plan" }}
                  </AppButton>
                  <AppButton
                    v-else
                    variant="secondary"
                    :disabled="regeneratingPreparation || preparationLoading"
                    @click="regeneratePreparation"
                  >
                    {{ regeneratingPreparation ? "Regenerating..." : "Regenerate plan" }}
                  </AppButton>
                </div>
              </template>

              <div v-if="preparationLoading" class="interview-empty-copy">
                Loading the latest preparation plan for this interview.
              </div>
              <AppEmptyState
                v-else-if="preparationError"
                title="Preparation unavailable"
                :description="preparationError"
              />
              <div v-else-if="!preparationPlan" class="interview-empty-copy">
                No preparation plan exists for this interview yet. Generate one to pull together role focus, resume evidence, projects, risks, and questions to ask.
              </div>
              <div v-else class="preparation-plan">
                <div class="preparation-plan__summary">
                  <div class="preparation-plan__meta">
                    <AppBadge tone="info">Version {{ preparationPlan.version_number }}</AppBadge>
                    <AppBadge :tone="preparationTone(preparationPlan.status)">{{ humanize(preparationPlan.status) }}</AppBadge>
                    <AppBadge tone="success">{{ formatConfidence(preparationPlan.overall_confidence) }}</AppBadge>
                  </div>
                  <div v-if="focusLabels.length > 0" class="preparation-plan__focus">
                    <AppBadge v-for="label in focusLabels" :key="label" tone="neutral">{{ label }}</AppBadge>
                  </div>
                </div>

                <div class="preparation-sections">
                  <article v-for="section in preparationSections" :key="section.section_key" class="preparation-section">
                    <div class="preparation-section__header">
                      <strong>{{ section.title }}</strong>
                      <AppBadge tone="info">{{ formatConfidence(section.confidence) }}</AppBadge>
                    </div>
                    <ul class="preparation-list">
                      <li v-for="line in section.content" :key="line">{{ line }}</li>
                    </ul>
                    <div v-if="section.evidence_references.length > 0" class="preparation-evidence">
                      <article
                        v-for="reference in section.evidence_references.slice(0, 3)"
                        :key="reference.reference_id"
                        class="preparation-evidence__item"
                      >
                        <strong>{{ reference.label }}</strong>
                        <p>{{ reference.excerpt }}</p>
                      </article>
                    </div>
                  </article>
                </div>
              </div>
            </AppCard>

            <AppCard title="Preparation checklist" subtitle="Track the actionable prep tasks generated from the plan and keep completion state on the interview workspace.">
              <div v-if="detailChecklist.length === 0" class="interview-empty-copy">
                No preparation checklist exists on this interview yet.
              </div>
              <div v-else class="interview-checklist">
                <article v-for="item in detailChecklist" :key="item.item_id" class="interview-checklist-item">
                  <div class="interview-checklist-item__copy">
                    <div class="interview-checklist-item__meta">
                      <strong>{{ item.label }}</strong>
                      <div class="interview-checklist-item__badges">
                        <AppBadge :tone="checklistTone(item.status)">{{ humanize(item.status) }}</AppBadge>
                        <AppBadge tone="neutral">{{ humanize(item.priority) }}</AppBadge>
                        <AppBadge tone="info">{{ item.estimated_effort || "Flexible" }}</AppBadge>
                      </div>
                    </div>
                    <p>{{ item.detail || "Interview preparation task" }}</p>
                    <p v-if="item.reason">{{ item.reason }}</p>
                    <div v-if="item.supporting_evidence.length > 0" class="preparation-evidence">
                      <article
                        v-for="reference in item.supporting_evidence.slice(0, 2)"
                        :key="reference.reference_id"
                        class="preparation-evidence__item"
                      >
                        <strong>{{ reference.label }}</strong>
                        <p>{{ reference.excerpt }}</p>
                      </article>
                    </div>
                  </div>
                  <AppSelect
                    :model-value="item.status"
                    label="Status"
                    :options="checklistStatusOptions"
                    @update:model-value="item.status = String($event)"
                  />
                </article>
              </div>
              <div v-if="preparationPlan" class="interview-actions interview-actions--end">
                <AppButton variant="primary" :disabled="savingPreparation" @click="savePreparationChecklist">
                  {{ savingPreparation ? "Saving..." : "Save checklist progress" }}
                </AppButton>
              </div>
            </AppCard>

            <AppCard title="Risk areas" subtitle="Risk analysis points to evidence gaps or thin context instead of inventing weaknesses.">
              <div v-if="preparationRisks.length === 0" class="interview-empty-copy">
                No explicit risk areas were flagged for this interview plan.
              </div>
              <div v-else class="risk-list">
                <article v-for="risk in preparationRisks" :key="risk.risk_id" class="risk-item">
                  <div class="risk-item__header">
                    <strong>{{ risk.title }}</strong>
                    <AppBadge :tone="riskTone(risk.severity)">{{ humanize(risk.severity) }}</AppBadge>
                  </div>
                  <p>{{ risk.detail }}</p>
                  <p>{{ risk.recommendation }}</p>
                </article>
              </div>
            </AppCard>

            <AppCard title="Preparation quick view" subtitle="Spot the strongest plan slices without scanning the full generation output.">
              <div class="quick-view">
                <article v-if="sectionByKey('focus_areas')" class="quick-view__card">
                  <strong>Focus areas</strong>
                  <p>{{ sectionByKey("focus_areas")?.content[0] }}</p>
                </article>
                <article v-if="sectionByKey('projects')" class="quick-view__card">
                  <strong>Project evidence</strong>
                  <p>{{ sectionByKey("projects")?.content[0] }}</p>
                </article>
                <article v-if="sectionByKey('questions_to_ask')" class="quick-view__card">
                  <strong>Questions to ask</strong>
                  <p>{{ sectionByKey("questions_to_ask")?.content[0] }}</p>
                </article>
              </div>
            </AppCard>

            <AppCard title="Question Bank" subtitle="Generate versioned interview questions grounded in the preparation plan, submitted resume, and linked workflow context.">
              <template #actions>
                <div class="interview-actions">
                  <AppButton
                    v-if="questionSets.length === 0"
                    variant="primary"
                    :disabled="generatingQuestions || questionLoading || !preparationPlan"
                    @click="generateQuestions"
                  >
                    {{ generatingQuestions ? "Generating..." : "Generate questions" }}
                  </AppButton>
                  <AppButton
                    v-else
                    variant="secondary"
                    :disabled="regeneratingQuestions || questionLoading || !preparationPlan"
                    @click="regenerateQuestions"
                  >
                    {{ regeneratingQuestions ? "Regenerating..." : "Regenerate version" }}
                  </AppButton>
                </div>
              </template>

              <div v-if="questionLoading" class="interview-empty-copy">
                Loading the current interview question bank.
              </div>
              <AppEmptyState
                v-else-if="questionError"
                title="Question bank unavailable"
                :description="questionError"
              />
              <div v-else-if="!preparationPlan" class="interview-empty-copy">
                Generate a preparation plan first so the question bank can use role focus, risks, evidence, and resume claims.
              </div>
              <div v-else-if="questionSets.length === 0" class="interview-empty-copy">
                No question bank exists yet. Generate one to turn the current preparation plan into a structured practice set.
              </div>
              <div v-else class="question-bank">
                <div class="preparation-plan__summary">
                  <div class="preparation-plan__meta">
                    <AppBadge tone="info">Version {{ currentQuestionSet?.version_number }}</AppBadge>
                    <AppBadge :tone="preparationTone(currentQuestionSet?.status || 'generated')">{{ humanize(currentQuestionSet?.status || "active") }}</AppBadge>
                    <AppBadge tone="neutral">{{ filteredQuestions.length }} visible</AppBadge>
                  </div>
                  <div class="question-bank__filters">
                    <AppSelect
                      :model-value="selectedQuestionSetId"
                      label="Version"
                      :options="questionSetOptions"
                      @update:model-value="setCurrentQuestionSet(String($event))"
                    />
                    <AppSelect v-model="questionCategoryFilter" label="Category" :options="questionCategoryOptions" />
                    <AppSelect
                      v-model="questionPriorityFilter"
                      label="Priority"
                      :options="[{ label: 'All priorities', value: 'all' }, ...questionPriorityOptions]"
                    />
                    <AppSelect
                      v-model="questionPreparationFilter"
                      label="Prep status"
                      :options="[{ label: 'All statuses', value: 'all' }, ...questionPreparationStatusOptions]"
                    />
                  </div>
                </div>

                <div v-if="filteredQuestions.length === 0" class="interview-empty-copy">
                  No questions match the current filters.
                </div>

                <div v-else class="question-list">
                  <article v-for="question in filteredQuestions" :key="question.question_id" class="question-item">
                    <div class="question-item__header">
                      <div class="question-item__copy">
                        <strong>{{ question.sequence_order }}. {{ question.question }}</strong>
                        <p>{{ question.rationale }}</p>
                      </div>
                      <div class="question-item__badges">
                        <AppBadge tone="neutral">{{ humanize(question.category) }}</AppBadge>
                        <AppBadge :tone="priorityTone(question.priority)">{{ humanize(question.priority) }}</AppBadge>
                        <AppBadge :tone="questionStatusTone(question.preparation_status)">{{ humanize(question.preparation_status) }}</AppBadge>
                        <AppBadge tone="info">{{ humanize(question.difficulty) }}</AppBadge>
                      </div>
                    </div>

                    <div class="question-item__controls">
                      <AppInput v-model="question.sequence_order" label="Order" type="number" />
                      <AppSelect v-model="question.priority" label="Priority" :options="questionPriorityOptions" />
                      <AppSelect v-model="question.preparation_status" label="Prep status" :options="questionPreparationStatusOptions" />
                      <AppButton variant="secondary" :disabled="savingQuestionId === question.question_id" @click="saveQuestion(question)">
                        {{ savingQuestionId === question.question_id ? "Saving..." : "Save" }}
                      </AppButton>
                      <AppButton variant="ghost" @click="toggleQuestionExpanded(question.question_id)">
                        {{ isQuestionExpanded(question.question_id) ? "Hide details" : "Show details" }}
                      </AppButton>
                    </div>

                    <div v-if="isQuestionExpanded(question.question_id)" class="question-item__details">
                      <div v-if="question.related_job_requirements.length > 0" class="preparation-plan__focus">
                        <AppBadge v-for="requirement in question.related_job_requirements" :key="requirement" tone="neutral">{{ requirement }}</AppBadge>
                      </div>

                      <div class="question-item__section">
                        <strong>Expected answer dimensions</strong>
                        <ul class="preparation-list">
                          <li v-for="line in question.expected_answer_outline" :key="line">{{ line }}</li>
                        </ul>
                      </div>

                      <div v-if="question.related_evidence.length > 0" class="question-item__section">
                        <strong>Supporting evidence</strong>
                        <div class="preparation-evidence">
                          <article
                            v-for="reference in question.related_evidence"
                            :key="reference.reference_id"
                            class="preparation-evidence__item"
                          >
                            <strong>{{ reference.label }}</strong>
                            <p>{{ reference.relevance_explanation || reference.excerpt }}</p>
                            <p>{{ reference.excerpt }}</p>
                          </article>
                        </div>
                      </div>

                      <div v-if="question.follow_up_questions.length > 0" class="question-item__section">
                        <strong>Follow-up probes</strong>
                        <ul class="preparation-list">
                          <li v-for="followUp in question.follow_up_questions" :key="followUp.follow_up_id">{{ followUp.question }}</li>
                        </ul>
                      </div>

                      <div v-if="question.user_notes.length > 0" class="question-item__section">
                        <strong>Notes</strong>
                        <div class="question-item__notes">
                          <article v-for="note in question.user_notes" :key="note.note_id" class="preparation-evidence__item">
                            <strong>{{ formatDateTime(note.created_at) }}</strong>
                            <p>{{ note.body }}</p>
                          </article>
                        </div>
                      </div>

                      <div class="question-item__section">
                        <AppTextArea
                          :model-value="questionNoteDraft(question.question_id)"
                          label="Add note"
                          placeholder="Capture where this answer is still thin, or which evidence you want to emphasize."
                          :rows="3"
                          @update:model-value="setQuestionNoteDraft(question.question_id, String($event))"
                        />
                        <AppButton variant="secondary" :disabled="savingQuestionNoteId === question.question_id" @click="addQuestionNote(question)">
                          {{ savingQuestionNoteId === question.question_id ? "Saving..." : "Add note" }}
                        </AppButton>
                      </div>
                    </div>
                  </article>
                </div>
              </div>
            </AppCard>

            <AppCard title="Story Library" subtitle="Turn approved evidence into versioned interview stories, map them to likely questions, and push missing details back through Profile Evolution review.">
              <template #actions>
                <div class="interview-actions">
                  <AppButton
                    variant="primary"
                    :disabled="generatingStories || storyLoading || !currentQuestionSet"
                    @click="generateStories"
                  >
                    {{ generatingStories ? "Generating..." : currentStories.length === 0 ? "Generate stories" : "Refresh stories" }}
                  </AppButton>
                </div>
              </template>

              <div v-if="storyLoading" class="interview-empty-copy">
                Loading the current story library for this interview.
              </div>
              <AppEmptyState
                v-else-if="storyError"
                title="Story library unavailable"
                :description="storyError"
              />
              <div v-else-if="!currentQuestionSet" class="interview-empty-copy">
                Generate the question bank first so Story Library can map stories to specific interview coverage.
              </div>
              <div v-else-if="currentStories.length === 0" class="interview-empty-copy">
                No interview stories exist yet. Generate them from approved evidence, resume claims, and the current interview question set.
              </div>
              <div v-else class="story-library">
                <div class="preparation-plan__summary">
                  <div class="preparation-plan__meta">
                    <AppBadge tone="info">{{ Number(storyLibrarySummary.story_count || currentStories.length) }} active stories</AppBadge>
                    <AppBadge tone="success">{{ Number(storyLibrarySummary.average_quality || 0) }} quality</AppBadge>
                    <AppBadge tone="neutral">{{ Number(storyLibrarySummary.coverage_ratio || 0) * 100 }}% question coverage</AppBadge>
                  </div>
                  <div v-if="uncoveredStoryQuestions.length > 0" class="story-summary__coverage">
                    <strong>Coverage gaps</strong>
                    <p>{{ uncoveredStoryQuestions.slice(0, 3).join(" · ") }}</p>
                  </div>
                </div>

                <article v-for="story in currentStories" :key="story.story_id" class="story-item">
                  <div class="story-item__header">
                    <div class="question-item__copy">
                      <strong>{{ story.title }}</strong>
                      <p>{{ story.quality.summary }}</p>
                    </div>
                    <div class="question-item__badges">
                      <AppBadge tone="neutral">{{ humanize(story.category) }}</AppBadge>
                      <AppBadge :tone="storyStatusTone(story.status)">{{ humanize(story.status) }}</AppBadge>
                      <AppBadge :tone="storyQualityTone(story.quality.overall_score)">{{ story.quality.overall_score }} quality</AppBadge>
                    </div>
                  </div>

                  <div v-if="story.tags.length > 0" class="preparation-plan__focus">
                    <AppBadge v-for="tag in story.tags" :key="`${story.story_id}:${tag}`" tone="neutral">{{ tag }}</AppBadge>
                  </div>

                  <div class="story-grid">
                    <article v-for="section in story.sections" :key="`${story.story_id}:${section.section_key}`" class="story-grid__section">
                      <strong>{{ section.title }}</strong>
                      <ul class="preparation-list">
                        <li v-for="line in section.content" :key="line">{{ line }}</li>
                      </ul>
                      <p v-if="section.missing_fields.length > 0" class="story-grid__hint">
                        Missing: {{ section.missing_fields.join(", ") }}
                      </p>
                    </article>
                  </div>

                  <div class="story-support">
                    <div v-if="story.coverage.length > 0" class="question-item__section">
                      <strong>Linked questions</strong>
                      <ul class="preparation-list">
                        <li v-for="item in linkedQuestionLabels(story)" :key="item">{{ item }}</li>
                      </ul>
                    </div>
                    <div v-if="story.source_evidence.length > 0" class="question-item__section">
                      <strong>Evidence</strong>
                      <div class="preparation-evidence">
                        <article
                          v-for="reference in story.source_evidence.slice(0, 3)"
                          :key="reference.reference_id"
                          class="preparation-evidence__item"
                        >
                          <strong>{{ reference.label }}</strong>
                          <p>{{ reference.excerpt }}</p>
                        </article>
                      </div>
                    </div>
                    <div class="question-item__section">
                      <strong>Version history</strong>
                      <div class="story-version-list">
                        <AppBadge
                          v-for="version in storyVersions(story.story_group_id)"
                          :key="version.story_id"
                          :tone="storyStatusTone(version.status)"
                        >
                          V{{ version.version_number }} · {{ humanize(version.status) }}
                        </AppBadge>
                      </div>
                    </div>
                  </div>

                  <div class="story-editor">
                    <AppInput
                      :model-value="storyDraft(story.story_id).title"
                      label="Story title"
                      @update:model-value="setStoryDraftValue(story.story_id, 'title', String($event))"
                    />
                    <AppTextArea
                      :model-value="storyDraft(story.story_id).measurableOutcomes"
                      label="Measurable outcomes"
                      placeholder="One outcome per line."
                      :rows="3"
                      @update:model-value="setStoryDraftValue(story.story_id, 'measurableOutcomes', String($event))"
                    />
                    <AppTextArea
                      :model-value="storyDraft(story.story_id).lessonsLearned"
                      label="Lessons learned"
                      placeholder="Capture reflection and what you would do differently."
                      :rows="3"
                      @update:model-value="setStoryDraftValue(story.story_id, 'lessonsLearned', String($event))"
                    />
                    <AppInput
                      :model-value="storyDraft(story.story_id).tags"
                      label="Tags"
                      placeholder="Python, Kubernetes, leadership"
                      @update:model-value="setStoryDraftValue(story.story_id, 'tags', String($event))"
                    />
                    <div class="interview-actions">
                      <AppButton variant="secondary" :disabled="savingStoryId === story.story_id" @click="saveStory(story)">
                        {{ savingStoryId === story.story_id ? "Saving..." : story.status === "approved" ? "Create revised version" : "Save story" }}
                      </AppButton>
                      <AppButton
                        variant="primary"
                        :disabled="storyActionId === story.story_id || story.status === 'approved'"
                        @click="approveStoryItem(story)"
                      >
                        {{ story.status === "approved" ? "Approved" : storyActionId === story.story_id ? "Working..." : "Approve" }}
                      </AppButton>
                      <AppButton variant="ghost" :disabled="storyActionId === story.story_id" @click="regenerateStoryItem(story)">
                        {{ storyActionId === story.story_id ? "Working..." : "Regenerate" }}
                      </AppButton>
                      <AppButton variant="danger" :disabled="storyActionId === story.story_id" @click="archiveStoryItem(story)">
                        {{ storyActionId === story.story_id ? "Working..." : "Archive" }}
                      </AppButton>
                    </div>
                  </div>

                  <div v-if="story.missing_information_prompts.length > 0" class="story-prompts">
                    <article v-for="prompt in story.missing_information_prompts" :key="prompt.prompt_id" class="story-prompt">
                      <div class="risk-item__header">
                        <strong>{{ prompt.prompt }}</strong>
                        <AppBadge :tone="prompt.status === 'submitted' ? 'info' : 'warning'">{{ humanize(prompt.status) }}</AppBadge>
                      </div>
                      <p>{{ prompt.reason }}</p>
                      <AppTextArea
                        :model-value="storyPromptDraft(prompt.prompt_id)"
                        label="Profile Evolution answer"
                        placeholder="Add the missing detail exactly as you would want it reviewed and canonically stored."
                        :rows="3"
                        @update:model-value="setStoryPromptDraft(prompt.prompt_id, String($event))"
                      />
                      <AppButton
                        variant="secondary"
                        :disabled="storyPromptSubmittingId === prompt.prompt_id || prompt.status === 'submitted'"
                        @click="submitStoryPrompt(story, prompt)"
                      >
                        {{ prompt.status === "submitted" ? "Submitted" : storyPromptSubmittingId === prompt.prompt_id ? "Sending..." : "Send to Profile Evolution" }}
                      </AppButton>
                    </article>
                  </div>
                </article>
              </div>
            </AppCard>

            <AppCard title="Timeline" subtitle="Interview lifecycle and preparation events remain explicit and chronological.">
              <div class="interview-timeline">
                <article v-for="event in selectedInterview.timeline" :key="`${event.event_type}:${event.occurred_at}`" class="interview-timeline-item">
                  <strong>{{ event.label }}</strong>
                  <p>{{ event.detail || humanize(event.event_type) }}</p>
                  <span>{{ formatDateTime(event.occurred_at) }}</span>
                </article>
              </div>
            </AppCard>
          </template>
        </div>
      </div>
    </PageSection>
  </AppPage>
</template>

<style scoped>
.interview-metrics {
  align-items: stretch;
}

.interview-metric strong {
  font-family: var(--font-display);
  font-size: clamp(2rem, 4vw, 2.6rem);
  line-height: 1;
}

.interview-workspace {
  display: grid;
  grid-template-columns: minmax(20rem, 24rem) minmax(0, 1fr);
  gap: var(--space-6);
  align-items: start;
}

.interview-form,
.interview-detail,
.interview-list,
.interview-checklist,
.interview-timeline,
.preparation-plan,
.preparation-sections,
.preparation-evidence,
.risk-list,
.quick-view,
.question-bank,
.question-list,
.story-library,
.story-support,
.story-editor,
.story-prompts,
.question-item__details,
.question-item__notes,
.question-item__section {
  display: grid;
  gap: var(--space-3);
}

.interview-metric p,
.interview-empty-copy,
.interview-list-item p,
.interview-hero__copy p,
.interview-checklist-item p,
.interview-timeline-item p,
.interview-timeline-item span,
.interview-inline-error,
.preparation-evidence__item p,
.risk-item p,
.quick-view__card p,
.question-item__copy p,
.story-grid__hint,
.story-summary__coverage p {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.6;
}

.interview-list-item,
.interview-checklist-item,
.interview-timeline-item,
.preparation-section,
.risk-item,
.quick-view__card,
.question-item,
.story-item,
.story-grid__section,
.story-prompt {
  border: 1px solid var(--color-border);
  border-radius: 1.25rem;
  background: var(--color-surface);
  padding: 1rem;
}

.interview-list-item {
  text-align: left;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.interview-list-item:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 255, 0.28);
}

.interview-list-item--active {
  border-color: rgba(37, 99, 255, 0.42);
  box-shadow: 0 14px 30px rgba(37, 99, 255, 0.12);
}

.interview-list-item__header,
.interview-list-item__meta,
.interview-actions,
.interview-hero,
.preparation-plan__meta,
.preparation-plan__summary,
.interview-checklist-item__meta,
.interview-checklist-item__badges,
.risk-item__header,
.preparation-section__header,
.question-item__header,
.question-item__badges,
.story-item__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.interview-actions--end {
  justify-content: flex-end;
}

.interview-list-item__copy,
.interview-hero__copy,
.interview-checklist-item__copy,
.preparation-plan__focus,
.question-item__copy {
  display: grid;
  gap: 0.25rem;
}

.interview-list-item__copy span,
.interview-hero__copy span {
  color: var(--color-text-muted);
  font-size: var(--type-small);
}

.interview-list-item h3,
.interview-hero__copy p {
  margin: 0;
}

.interview-list-item__avatar,
.interview-hero__avatar {
  width: 3rem;
  height: 3rem;
  border-radius: 1rem;
  display: grid;
  place-items: center;
  font-weight: 700;
}

.interview-inline-error {
  color: var(--color-danger);
}

.preparation-sections {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.question-bank__filters,
.question-item__controls {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.story-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.story-version-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.question-item__controls .app-button {
  align-self: end;
}

.question-item__section strong {
  display: block;
  margin-bottom: 0.35rem;
}

.preparation-list {
  margin: 0;
  padding-left: 1rem;
  display: grid;
  gap: 0.35rem;
}

.preparation-plan__focus {
  grid-auto-flow: column;
  justify-content: flex-start;
  align-items: center;
  flex-wrap: wrap;
}

.preparation-evidence__item {
  border-radius: 1rem;
  background: rgba(15, 23, 42, 0.04);
  padding: 0.75rem;
}

.quick-view {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

@media (max-width: 1180px) {
  .interview-workspace {
    grid-template-columns: 1fr;
  }

  .preparation-sections,
  .quick-view,
  .question-bank__filters,
  .question-item__controls,
  .story-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .interview-list-item__header,
  .interview-list-item__meta,
  .interview-actions,
  .interview-hero,
  .preparation-plan__summary,
  .preparation-section__header,
  .risk-item__header,
  .interview-checklist-item__meta,
  .question-item__header,
  .question-item__badges,
  .story-item__header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
