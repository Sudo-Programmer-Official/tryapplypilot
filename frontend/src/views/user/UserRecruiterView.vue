<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import {
  completeUserRecruiterGmailConnect,
  disconnectUserRecruiterGmail,
  fetchUserRecruiterDrafts,
  fetchUserRecruiterMessageSummary,
  fetchUserRecruiterMessageSuggestions,
  fetchUserRecruiterMessages,
  fetchUserRecruiterProviderStatuses,
  fetchUserRecruiterSyncHistory,
  fetchUserRecruiterThreadSummary,
  fetchUserRecruiterThreads,
  generateUserRecruiterDraft,
  startUserRecruiterGmailConnect,
  syncUserRecruiterProvider,
  updateUserRecruiterDraft,
} from "../../api/user.api";
import AppGrid from "../../components/layout/AppGrid.vue";
import AppPage from "../../components/layout/AppPage.vue";
import PageHeader from "../../components/layout/PageHeader.vue";
import PageSection from "../../components/layout/PageSection.vue";
import AppBadge from "../../components/ui/AppBadge.vue";
import AppButton from "../../components/ui/AppButton.vue";
import AppCard from "../../components/ui/AppCard.vue";
import AppEmptyState from "../../components/ui/AppEmptyState.vue";
import AppInput from "../../components/ui/AppInput.vue";
import AppSelect from "../../components/ui/AppSelect.vue";
import AppTextArea from "../../components/ui/AppTextArea.vue";
import type {
  CommunicationDraft,
  CommunicationInsightSummary,
  ConversationSuggestion,
  EmailProviderStatus,
  EmailSyncRun,
  RecruiterMessage,
  RecruiterThread,
} from "../../types";
import { companyMarkStyle, formatDate, formatDateTime, getInitials } from "../../utils/format";

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const loadingThread = ref(false);
const connectingProvider = ref(false);
const disconnectingProvider = ref(false);
const syncingProvider = ref(false);
const generatingDraft = ref(false);
const savingDraft = ref(false);

const workspaceError = ref<string | null>(null);
const providerError = ref<string | null>(null);
const detailError = ref<string | null>(null);
const draftError = ref<string | null>(null);

const threads = ref<RecruiterThread[]>([]);
const providerStatuses = ref<EmailProviderStatus[]>([]);
const syncHistory = ref<EmailSyncRun[]>([]);
const messages = ref<RecruiterMessage[]>([]);
const suggestions = ref<ConversationSuggestion[]>([]);
const drafts = ref<CommunicationDraft[]>([]);
const threadSummary = ref<CommunicationInsightSummary | null>(null);
const latestMessageSummary = ref<CommunicationInsightSummary | null>(null);

const draftKind = ref("reply");
const draftTone = ref("professional");
const draftSubject = ref("");
const draftBody = ref("");
const activeDraftId = ref("");

const draftKindOptions = [
  { label: "Reply", value: "reply" },
  { label: "Follow-up", value: "follow_up" },
  { label: "Interview confirmation", value: "interview_confirmation" },
  { label: "Thank-you", value: "thank_you" },
];

const toneOptions = [
  { label: "Professional", value: "professional" },
  { label: "Warm", value: "warm" },
  { label: "Direct", value: "direct" },
  { label: "Appreciative", value: "appreciative" },
];

const selectedThreadId = computed(() => {
  const value = route.query.thread;
  return typeof value === "string" ? value : "";
});

const selectedThread = computed(
  () => threads.value.find((item) => item.thread_id === selectedThreadId.value) ?? null,
);

const latestMessage = computed(() => messages.value[0] ?? null);
const gmailStatus = computed(() => providerStatuses.value.find((item) => item.provider === "gmail") ?? null);
const connectedProviderCount = computed(() => providerStatuses.value.filter((item) => item.status === "connected").length);
const overdueThreadCount = computed(() => threads.value.filter((item) => item.response_overdue).length);
const activeConversationCount = computed(() => threads.value.filter((item) => item.pending_action || item.response_overdue).length);
const latestSyncRun = computed(() => syncHistory.value[0] ?? null);

const latestDrafts = computed(() => {
  const latestByGroup = new Map<string, CommunicationDraft>();
  drafts.value.forEach((item) => {
    const current = latestByGroup.get(item.draft_group_id);
    if (!current || item.version_number > current.version_number) {
      latestByGroup.set(item.draft_group_id, item);
    }
  });
  return sortDrafts(Array.from(latestByGroup.values()));
});

const selectedDraft = computed(() => {
  if (activeDraftId.value) {
    return drafts.value.find((item) => item.draft_id === activeDraftId.value) ?? null;
  }
  return drafts.value[0] ?? null;
});

function parseDateValue(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function sortThreads(items: RecruiterThread[]): RecruiterThread[] {
  return [...items].sort((left, right) => {
    return parseDateValue(right.last_message_at || right.updated_at) - parseDateValue(left.last_message_at || left.updated_at);
  });
}

function sortDrafts(items: CommunicationDraft[]): CommunicationDraft[] {
  return [...items].sort((left, right) => {
    const timeDelta = parseDateValue(right.updated_at || right.created_at) - parseDateValue(left.updated_at || left.created_at);
    if (timeDelta !== 0) {
      return timeDelta;
    }
    return right.version_number - left.version_number;
  });
}

function humanize(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function waitingLabel(value: string): string {
  if (!value || value === "none") {
    return "No owner";
  }
  return `Waiting on ${humanize(value)}`;
}

function providerTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "connected") {
    return "success";
  }
  if (status === "needs_reauth" || status === "pending") {
    return "warning";
  }
  if (status === "error" || status === "disconnected") {
    return "danger";
  }
  return "neutral";
}

function conversationTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "interview_scheduled" || status === "waiting_for_recruiter") {
    return "info";
  }
  if (status === "waiting_for_candidate" || status === "assessment_pending" || status === "offer_pending") {
    return "warning";
  }
  if (status === "conversation_closed") {
    return "neutral";
  }
  return "success";
}

function healthTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "healthy" || status === "closed") {
    return "success";
  }
  if (status === "needs_follow_up" || status === "stale") {
    return "warning";
  }
  if (status === "blocked") {
    return "danger";
  }
  return "neutral";
}

function draftToneForStatus(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "approved") {
    return "success";
  }
  if (status === "edited") {
    return "info";
  }
  if (status === "rejected") {
    return "danger";
  }
  return "warning";
}

function isRecruiterAuthored(message: RecruiterMessage): boolean {
  return message.sender.trim().toLowerCase() === message.recruiter.email.trim().toLowerCase();
}

function messageAuthorLabel(message: RecruiterMessage): string {
  return isRecruiterAuthored(message) ? message.recruiter.display_name || "Recruiter" : "You";
}

function messageTone(message: RecruiterMessage): "success" | "warning" | "danger" | "info" | "neutral" {
  return isRecruiterAuthored(message) ? "info" : "success";
}

function syncDraftEditor(draft: CommunicationDraft | null): void {
  if (draft === null) {
    draftSubject.value = "";
    draftBody.value = "";
    return;
  }
  draftKind.value = draft.draft_kind;
  draftTone.value = draft.tone;
  draftSubject.value = draft.subject;
  draftBody.value = draft.body;
}

function resetThreadContext(): void {
  messages.value = [];
  suggestions.value = [];
  drafts.value = [];
  threadSummary.value = null;
  latestMessageSummary.value = null;
  activeDraftId.value = "";
  draftSubject.value = "";
  draftBody.value = "";
  detailError.value = null;
  draftError.value = null;
}

async function openThread(threadId: string): Promise<void> {
  if (!threadId || threadId === selectedThreadId.value) {
    return;
  }
  await router.replace({
    query: {
      ...route.query,
      thread: threadId,
    },
  });
}

async function clearSelectedThread(): Promise<void> {
  if (!selectedThreadId.value) {
    return;
  }
  const nextQuery = { ...route.query };
  delete nextQuery.thread;
  await router.replace({ query: nextQuery });
}

async function loadThreadContext(threadId: string, preferredDraftId = ""): Promise<void> {
  loadingThread.value = true;
  detailError.value = null;
  draftError.value = null;
  try {
    const [messagesPayload, threadSummaryPayload, draftPayload] = await Promise.all([
      fetchUserRecruiterMessages({ threadId }),
      fetchUserRecruiterThreadSummary(threadId),
      fetchUserRecruiterDrafts({ threadId, latestOnly: false }),
    ]);
    messages.value = messagesPayload.items;
    threadSummary.value = threadSummaryPayload.item;
    drafts.value = sortDrafts(draftPayload.items);
    activeDraftId.value = preferredDraftId || drafts.value[0]?.draft_id || "";
    syncDraftEditor(drafts.value.find((item) => item.draft_id === activeDraftId.value) ?? drafts.value[0] ?? null);

    const currentMessage = messagesPayload.items[0] ?? null;
    if (currentMessage) {
      const [messageSummaryPayload, suggestionPayload] = await Promise.all([
        fetchUserRecruiterMessageSummary(currentMessage.message_id),
        fetchUserRecruiterMessageSuggestions(currentMessage.message_id),
      ]);
      latestMessageSummary.value = messageSummaryPayload.item;
      suggestions.value = suggestionPayload.items;
    } else {
      latestMessageSummary.value = null;
      suggestions.value = [];
    }
  } catch (err) {
    resetThreadContext();
    detailError.value = err instanceof Error ? err.message : "Failed to load recruiter thread context.";
  } finally {
    loadingThread.value = false;
  }
}

async function loadWorkspace(): Promise<void> {
  loading.value = true;
  workspaceError.value = null;
  try {
    const [threadPayload, providerPayload, historyPayload] = await Promise.all([
      fetchUserRecruiterThreads(),
      fetchUserRecruiterProviderStatuses(),
      fetchUserRecruiterSyncHistory({ limit: 5 }),
    ]);
    threads.value = sortThreads(threadPayload.items);
    providerStatuses.value = providerPayload.items;
    syncHistory.value = historyPayload.items.sort((left, right) => parseDateValue(right.started_at) - parseDateValue(left.started_at));

    if (selectedThreadId.value && threads.value.some((item) => item.thread_id === selectedThreadId.value)) {
      await loadThreadContext(selectedThreadId.value, activeDraftId.value);
    } else if (threads.value.length > 0) {
      await openThread(threads.value[0].thread_id);
    } else {
      resetThreadContext();
      await clearSelectedThread();
    }
  } catch (err) {
    workspaceError.value = err instanceof Error ? err.message : "Failed to load recruiter workspace.";
  } finally {
    loading.value = false;
  }
}

async function connectGmail(): Promise<void> {
  connectingProvider.value = true;
  workspaceError.value = null;
  providerError.value = null;
  try {
    const payload = await startUserRecruiterGmailConnect();
    if (typeof window !== "undefined") {
      window.location.assign(payload.item.authorization_url);
    }
  } catch (err) {
    workspaceError.value = err instanceof Error ? err.message : "Failed to start Gmail connection.";
  } finally {
    connectingProvider.value = false;
  }
}

function queryString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

// Google redirects back here with ?code&state (or ?error). The signed-in user finishes
// the exchange so the backend can check the state was issued to this same account.
async function completeGmailOAuthFromQuery(): Promise<void> {
  const code = queryString(route.query.code);
  const state = queryString(route.query.state);
  const oauthError = queryString(route.query.error);
  if (!code && !state && !oauthError) {
    return;
  }
  const nextQuery = { ...route.query };
  delete nextQuery.code;
  delete nextQuery.state;
  delete nextQuery.error;
  delete nextQuery.error_description;
  delete nextQuery.scope;
  delete nextQuery.authuser;
  delete nextQuery.prompt;
  const errorDescription = queryString(route.query.error_description);
  await router.replace({ query: nextQuery });

  if (oauthError) {
    providerError.value = oauthError === "access_denied"
      ? "Gmail access was not granted."
      : `Gmail connection failed: ${errorDescription || oauthError}`;
    return;
  }
  if (!code || !state) {
    providerError.value = "Gmail connection could not be completed. Please try connecting again.";
    return;
  }
  connectingProvider.value = true;
  try {
    await completeUserRecruiterGmailConnect({ code, state });
  } catch (err) {
    providerError.value = err instanceof Error ? err.message : "Failed to complete Gmail connection.";
  } finally {
    connectingProvider.value = false;
  }
}

async function disconnectGmail(): Promise<void> {
  disconnectingProvider.value = true;
  workspaceError.value = null;
  try {
    await disconnectUserRecruiterGmail();
    await loadWorkspace();
  } catch (err) {
    workspaceError.value = err instanceof Error ? err.message : "Failed to disconnect Gmail.";
  } finally {
    disconnectingProvider.value = false;
  }
}

async function syncProviders(): Promise<void> {
  syncingProvider.value = true;
  workspaceError.value = null;
  try {
    await syncUserRecruiterProvider({ provider: gmailStatus.value?.provider });
    await loadWorkspace();
  } catch (err) {
    workspaceError.value = err instanceof Error ? err.message : "Failed to sync recruiter providers.";
  } finally {
    syncingProvider.value = false;
  }
}

async function generateDraft(): Promise<void> {
  if (!selectedThread.value) {
    return;
  }
  generatingDraft.value = true;
  draftError.value = null;
  try {
    const payload = await generateUserRecruiterDraft({
      thread_id: selectedThread.value.thread_id,
      draft_kind: draftKind.value,
      tone: draftTone.value,
      source_message_id: latestMessage.value?.message_id ?? "",
    });
    await loadThreadContext(selectedThread.value.thread_id, payload.item.draft_id);
  } catch (err) {
    draftError.value = err instanceof Error ? err.message : "Failed to generate recruiter draft.";
  } finally {
    generatingDraft.value = false;
  }
}

async function saveDraft(nextStatus = "edited"): Promise<void> {
  if (!selectedDraft.value || !selectedThread.value) {
    return;
  }
  savingDraft.value = true;
  draftError.value = null;
  try {
    const payload = await updateUserRecruiterDraft(selectedDraft.value.draft_id, {
      subject: draftSubject.value,
      body: draftBody.value,
      status: nextStatus,
    });
    await loadThreadContext(selectedThread.value.thread_id, payload.item.draft_id);
  } catch (err) {
    draftError.value = err instanceof Error ? err.message : "Failed to save recruiter draft.";
  } finally {
    savingDraft.value = false;
  }
}

function selectDraft(draft: CommunicationDraft): void {
  activeDraftId.value = draft.draft_id;
  syncDraftEditor(draft);
}

watch(
  selectedThreadId,
  (threadId, previousThreadId) => {
    if (!threadId) {
      resetThreadContext();
      return;
    }
    if (threadId === previousThreadId) {
      return;
    }
    void loadThreadContext(threadId);
  },
);

onMounted(async () => {
  await completeGmailOAuthFromQuery();
  await loadWorkspace();
});
</script>

<template>
  <AppPage>
    <PageHeader
      title="Recruiter Intelligence"
      description="Bring recruiter emails into the application workflow, see what changed, and review grounded reply drafts without automating outreach."
    >
      <template #actions>
        <AppBadge tone="info">{{ threads.length }} conversations</AppBadge>
      </template>
    </PageHeader>

    <PageSection>
      <AppGrid columns="4" class="recruiter-metrics">
        <AppCard title="Connected providers" subtitle="Live provider connections feeding recruiter communication into the workspace.">
          <div class="recruiter-metric">
            <strong>{{ connectedProviderCount }}</strong>
            <p>{{ providerStatuses.length === 0 ? "No provider connected yet." : "Provider status remains visible before sync and after disconnect." }}</p>
          </div>
        </AppCard>

        <AppCard title="Open conversations" subtitle="Threads that are active and attached to recruiter workflow state.">
          <div class="recruiter-metric">
            <strong>{{ threads.length }}</strong>
            <p>Every thread stays linked to recruiter, application, and timeline context instead of living in inbox search.</p>
          </div>
        </AppCard>

        <AppCard title="Needs attention" subtitle="Conversations with an explicit next action or overdue response risk.">
          <div class="recruiter-metric">
            <strong>{{ activeConversationCount }}</strong>
            <p>{{ overdueThreadCount }} thread<span v-if="overdueThreadCount !== 1">s</span> are already overdue.</p>
          </div>
        </AppCard>

        <AppCard title="Draft groups" subtitle="Versioned recruiter drafts grounded in thread evidence rather than freeform prompts.">
          <div class="recruiter-metric">
            <strong>{{ latestDrafts.length }}</strong>
            <p>{{ drafts.length }} total draft version<span v-if="drafts.length !== 1">s</span> are available in the current workspace.</p>
          </div>
        </AppCard>
      </AppGrid>
    </PageSection>

    <PageSection>
      <AppCard title="Provider status" subtitle="Keep email ingestion deliberate: connect, sync, review, then decide what to send manually.">
        <template #actions>
          <div class="recruiter-actions">
            <AppButton variant="secondary" :disabled="connectingProvider || Boolean(gmailStatus && gmailStatus.status === 'connected')" @click="connectGmail">
              {{ connectingProvider ? "Connecting..." : gmailStatus?.status === "connected" ? "Gmail connected" : "Connect Gmail" }}
            </AppButton>
            <AppButton variant="ghost" :disabled="syncingProvider || providerStatuses.length === 0" @click="syncProviders">
              {{ syncingProvider ? "Syncing..." : "Sync inbox" }}
            </AppButton>
            <AppButton
              v-if="gmailStatus"
              variant="danger"
              :disabled="disconnectingProvider"
              @click="disconnectGmail"
            >
              {{ disconnectingProvider ? "Disconnecting..." : "Disconnect Gmail" }}
            </AppButton>
          </div>
        </template>

        <div v-if="providerError" class="recruiter-inline-error">{{ providerError }}</div>
        <div class="recruiter-provider-grid">
          <div v-if="providerStatuses.length === 0" class="recruiter-provider-empty">
            <p>No provider is connected yet. The workspace still supports imported recruiter messages, and live Gmail sync can be added when you are ready.</p>
          </div>
          <article v-for="status in providerStatuses" :key="status.provider" class="recruiter-provider-card">
            <div class="recruiter-provider-card__header">
              <strong>{{ humanize(status.provider) }}</strong>
              <AppBadge :tone="providerTone(status.status)">{{ humanize(status.status) }}</AppBadge>
            </div>
            <p>{{ status.account_email }}</p>
            <dl class="recruiter-provider-card__facts">
              <div>
                <dt>Last sync</dt>
                <dd>{{ formatDateTime(status.last_sync_at) }}</dd>
              </div>
              <div>
                <dt>Last run</dt>
                <dd>{{ humanize(status.last_run_status) }}</dd>
              </div>
              <div>
                <dt>Imported</dt>
                <dd>{{ status.last_imported_count }}</dd>
              </div>
              <div>
                <dt>Duplicates</dt>
                <dd>{{ status.last_duplicate_count }}</dd>
              </div>
            </dl>
          </article>
        </div>

        <div v-if="latestSyncRun" class="recruiter-sync-history">
          <strong>Latest sync</strong>
          <span>{{ humanize(latestSyncRun.run_status) }} · {{ latestSyncRun.provider }} · {{ formatDateTime(latestSyncRun.started_at) }}</span>
          <span>Imported {{ latestSyncRun.imported_count }}, duplicates {{ latestSyncRun.duplicate_count }}, errors {{ latestSyncRun.error_count }}</span>
        </div>
      </AppCard>
    </PageSection>

    <PageSection v-if="loading">
      <AppEmptyState title="Loading recruiter workspace" description="Refreshing provider status, conversation threads, and grounded draft context." />
    </PageSection>

    <PageSection v-else-if="workspaceError">
      <AppEmptyState title="Recruiter workspace unavailable" :description="workspaceError" />
    </PageSection>

    <PageSection v-else-if="threads.length === 0">
      <AppEmptyState
        title="No recruiter conversations yet"
        description="Import recruiter messages or connect Gmail to start linking email threads to application records and suggested next actions."
      >
        <template #actions>
          <AppButton variant="secondary" :disabled="connectingProvider" @click="connectGmail">
            {{ connectingProvider ? "Connecting..." : "Connect Gmail" }}
          </AppButton>
        </template>
      </AppEmptyState>
    </PageSection>

    <PageSection v-else>
      <div class="recruiter-workspace">
        <AppCard title="Conversation queue" subtitle="Choose the recruiter thread that should drive the next workflow decision." class="recruiter-sidebar">
          <div class="recruiter-thread-list">
            <button
              v-for="thread in threads"
              :key="thread.thread_id"
              class="recruiter-thread-item"
              :class="{ 'recruiter-thread-item--active': thread.thread_id === selectedThreadId }"
              type="button"
              @click="openThread(thread.thread_id)"
            >
              <div class="recruiter-thread-item__header">
                <div class="recruiter-thread-item__avatar" :style="companyMarkStyle(thread.company || thread.recruiter.display_name || thread.recruiter.email)">
                  {{ getInitials(thread.recruiter.display_name || thread.recruiter.email) }}
                </div>
                <div class="recruiter-thread-item__copy">
                  <strong>{{ thread.recruiter.display_name || thread.recruiter.email }}</strong>
                  <span>{{ thread.company || "Unknown company" }} · {{ thread.job_title || "Unknown role" }}</span>
                </div>
              </div>
              <h3>{{ thread.subject || "Recruiter conversation" }}</h3>
              <p>{{ thread.pending_action || "No explicit action yet." }}</p>
              <div class="recruiter-thread-item__meta">
                <AppBadge :tone="conversationTone(thread.conversation_status)">{{ humanize(thread.conversation_status) }}</AppBadge>
                <AppBadge v-if="thread.response_overdue" tone="danger">Overdue</AppBadge>
                <span>{{ formatDateTime(thread.last_message_at) }}</span>
              </div>
            </button>
          </div>
        </AppCard>

        <div class="recruiter-detail">
          <AppEmptyState
            v-if="detailError"
            title="Thread context unavailable"
            :description="detailError"
          />

          <template v-else>
            <AppCard v-if="selectedThread" :title="selectedThread.subject || 'Recruiter conversation'" :subtitle="`${selectedThread.company || 'Unknown company'} · ${selectedThread.job_title || 'Unknown role'}`">
              <template #actions>
                <div class="recruiter-actions">
                  <AppBadge :tone="conversationTone(selectedThread.conversation_status)">{{ humanize(selectedThread.conversation_status) }}</AppBadge>
                  <AppBadge
                    v-if="threadSummary"
                    :tone="healthTone(threadSummary.pending_action ? 'needs_follow_up' : 'healthy')"
                  >
                    {{ waitingLabel(threadSummary.pending_action ? 'candidate' : 'none') }}
                  </AppBadge>
                </div>
              </template>

              <div class="recruiter-hero">
                <div class="recruiter-hero__avatar" :style="companyMarkStyle(selectedThread.company || selectedThread.recruiter.display_name || selectedThread.recruiter.email)">
                  {{ getInitials(selectedThread.recruiter.display_name || selectedThread.recruiter.email) }}
                </div>
                <div class="recruiter-hero__copy">
                  <strong>{{ selectedThread.recruiter.display_name || selectedThread.recruiter.email }}</strong>
                  <span>{{ selectedThread.recruiter.email }}</span>
                  <p>{{ threadSummary?.summary || "The recruiter thread is linked and ready for review." }}</p>
                </div>
              </div>

              <div v-if="threadSummary" class="recruiter-summary-points">
                <div v-for="point in threadSummary.key_points" :key="point" class="recruiter-summary-point">
                  {{ point }}
                </div>
              </div>
            </AppCard>

            <AppCard v-if="latestMessageSummary" title="Latest message insight" subtitle="Deterministic summary grounded in the newest recruiter message and linked application context.">
              <div class="recruiter-insight">
                <p class="recruiter-insight__summary">{{ latestMessageSummary.summary }}</p>
                <dl class="recruiter-insight__facts">
                  <div>
                    <dt>Objective</dt>
                    <dd>{{ latestMessageSummary.communication_objective }}</dd>
                  </div>
                  <div>
                    <dt>Pending action</dt>
                    <dd>{{ latestMessageSummary.pending_action || "Review manually" }}</dd>
                  </div>
                  <div>
                    <dt>Confidence</dt>
                    <dd>{{ Math.round(latestMessageSummary.confidence * 100) }}%</dd>
                  </div>
                  <div>
                    <dt>Generated</dt>
                    <dd>{{ formatDateTime(latestMessageSummary.generated_at) }}</dd>
                  </div>
                </dl>
                <div v-if="latestMessageSummary.evidence.length > 0" class="recruiter-evidence-list">
                  <article v-for="item in latestMessageSummary.evidence" :key="`${item.source_type}:${item.source_id}`" class="recruiter-evidence-item">
                    <strong>{{ item.label }}</strong>
                    <p>{{ item.excerpt }}</p>
                  </article>
                </div>
              </div>
            </AppCard>

            <AppCard title="Suggested next actions" subtitle="Workflow suggestions stay explainable and human-controlled.">
              <div v-if="suggestions.length === 0" class="recruiter-empty-copy">
                No explicit action suggestions are available for the current message yet.
              </div>
              <div v-else class="recruiter-suggestions">
                <article v-for="item in suggestions" :key="item.suggestion_id" class="recruiter-suggestion">
                  <div class="recruiter-suggestion__header">
                    <strong>{{ item.label }}</strong>
                    <AppBadge :tone="item.confidence >= 0.85 ? 'success' : item.confidence >= 0.65 ? 'warning' : 'neutral'">
                      {{ Math.round(item.confidence * 100) }}%
                    </AppBadge>
                  </div>
                  <p>{{ item.reason }}</p>
                  <div class="recruiter-suggestion__meta">
                    <span>{{ waitingLabel(item.waiting_on) }}</span>
                    <span v-if="item.due_at">Due {{ formatDateTime(item.due_at) }}</span>
                    <span v-else>No due date</span>
                  </div>
                </article>
              </div>
            </AppCard>

            <AppCard title="Draft workspace" subtitle="Generate a grounded recruiter draft, then edit or approve a new version without sending anything automatically.">
              <template #actions>
                <div class="recruiter-actions">
                  <AppBadge v-if="selectedDraft" :tone="draftToneForStatus(selectedDraft.status)">
                    {{ humanize(selectedDraft.status) }} · v{{ selectedDraft.version_number }}
                  </AppBadge>
                  <AppBadge v-if="selectedDraft" tone="info">{{ humanize(selectedDraft.draft_kind) }}</AppBadge>
                </div>
              </template>

              <div class="recruiter-draft-toolbar">
                <AppSelect v-model="draftKind" label="Draft type" :options="draftKindOptions" />
                <AppSelect v-model="draftTone" label="Tone" :options="toneOptions" />
                <div class="recruiter-draft-toolbar__actions">
                  <AppButton variant="secondary" :disabled="generatingDraft || !selectedThread" @click="generateDraft">
                    {{ generatingDraft ? "Generating..." : "Generate draft" }}
                  </AppButton>
                </div>
              </div>

              <div v-if="draftError" class="recruiter-inline-error">{{ draftError }}</div>

              <div v-if="selectedDraft" class="recruiter-draft-editor">
                <AppInput v-model="draftSubject" label="Subject" placeholder="Draft subject" />
                <AppTextArea v-model="draftBody" label="Body" placeholder="Draft body" :rows="10" />
                <p class="recruiter-draft-editor__hint">{{ selectedDraft.explanation }}</p>
                <div class="recruiter-actions">
                  <AppButton variant="primary" :disabled="savingDraft" @click="saveDraft('edited')">
                    {{ savingDraft ? "Saving..." : "Save new version" }}
                  </AppButton>
                  <AppButton variant="success" :disabled="savingDraft" @click="saveDraft('approved')">Approve draft</AppButton>
                  <AppButton variant="danger" :disabled="savingDraft" @click="saveDraft('rejected')">Reject draft</AppButton>
                </div>
              </div>
              <div v-else class="recruiter-empty-copy">
                Generate a recruiter draft to create a versioned communication artifact for this thread.
              </div>

              <div v-if="drafts.length > 0" class="recruiter-draft-history">
                <strong>Draft history</strong>
                <div class="recruiter-draft-history__list">
                  <button
                    v-for="item in drafts"
                    :key="item.draft_id"
                    class="recruiter-draft-history__item"
                    :class="{ 'recruiter-draft-history__item--active': item.draft_id === activeDraftId }"
                    type="button"
                    @click="selectDraft(item)"
                  >
                    <span>{{ humanize(item.draft_kind) }} · v{{ item.version_number }}</span>
                    <span>{{ humanize(item.status) }} · {{ formatDateTime(item.updated_at) }}</span>
                  </button>
                </div>
              </div>
            </AppCard>

            <AppCard title="Message timeline" subtitle="The inbox thread is reduced to the context that matters for recruiter workflow decisions.">
              <div v-if="loadingThread" class="recruiter-empty-copy">Loading recruiter messages...</div>
              <div v-else-if="messages.length === 0" class="recruiter-empty-copy">No messages are attached to this recruiter thread yet.</div>
              <div v-else class="recruiter-message-list">
                <article v-for="message in messages" :key="message.message_id" class="recruiter-message-card">
                  <div class="recruiter-message-card__header">
                    <div>
                      <strong>{{ messageAuthorLabel(message) }}</strong>
                      <p>{{ message.subject || humanize(message.message_type) }}</p>
                    </div>
                    <div class="recruiter-actions">
                      <AppBadge :tone="messageTone(message)">{{ humanize(message.message_type) }}</AppBadge>
                      <span>{{ formatDateTime(message.received_at) }}</span>
                    </div>
                  </div>
                  <p class="recruiter-message-card__preview">{{ message.body_preview || message.body_reference }}</p>
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
.recruiter-metrics {
  align-items: stretch;
}

.recruiter-metric {
  display: grid;
  gap: var(--space-3);
}

.recruiter-metric strong {
  font-family: var(--font-display);
  font-size: clamp(2rem, 4vw, 2.6rem);
  line-height: 1;
}

.recruiter-metric p,
.recruiter-provider-empty p,
.recruiter-empty-copy,
.recruiter-message-card__preview,
.recruiter-insight__summary,
.recruiter-suggestion p,
.recruiter-draft-editor__hint,
.recruiter-inline-error {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.6;
}

.recruiter-workspace {
  display: grid;
  grid-template-columns: minmax(18rem, 22rem) minmax(0, 1fr);
  gap: var(--space-6);
  align-items: start;
}

.recruiter-sidebar {
  position: sticky;
  top: var(--space-6);
}

.recruiter-thread-list,
.recruiter-detail,
.recruiter-provider-grid,
.recruiter-draft-history__list,
.recruiter-message-list,
.recruiter-suggestions {
  display: grid;
  gap: var(--space-4);
}

.recruiter-thread-item,
.recruiter-draft-history__item {
  border: 1px solid var(--color-border);
  border-radius: 1.25rem;
  background: var(--color-surface);
  padding: 1rem;
  text-align: left;
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    transform var(--transition-fast);
  cursor: pointer;
}

.recruiter-thread-item:hover,
.recruiter-draft-history__item:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 255, 0.28);
}

.recruiter-thread-item--active,
.recruiter-draft-history__item--active {
  border-color: rgba(37, 99, 255, 0.4);
  box-shadow: 0 14px 30px rgba(37, 99, 255, 0.12);
}

.recruiter-thread-item__header,
.recruiter-provider-card__header,
.recruiter-hero,
.recruiter-suggestion__header,
.recruiter-message-card__header,
.recruiter-draft-toolbar,
.recruiter-actions,
.recruiter-sync-history {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.recruiter-thread-item__copy,
.recruiter-hero__copy,
.recruiter-insight,
.recruiter-draft-editor,
.recruiter-provider-card,
.recruiter-message-card {
  display: grid;
  gap: var(--space-3);
}

.recruiter-thread-item__avatar,
.recruiter-hero__avatar {
  width: 3rem;
  height: 3rem;
  border-radius: 1rem;
  display: grid;
  place-items: center;
  font-weight: 700;
}

.recruiter-thread-item__copy span,
.recruiter-hero__copy span,
.recruiter-thread-item__meta,
.recruiter-suggestion__meta,
.recruiter-sync-history span,
.recruiter-draft-history__item span:last-child,
.recruiter-message-card__header p {
  color: var(--color-text-muted);
  font-size: var(--type-small);
}

.recruiter-thread-item h3,
.recruiter-provider-card p,
.recruiter-thread-item p,
.recruiter-hero__copy p,
.recruiter-message-card__header p {
  margin: 0;
}

.recruiter-thread-item__meta,
.recruiter-suggestion__meta,
.recruiter-summary-points,
.recruiter-provider-card__facts,
.recruiter-insight__facts,
.recruiter-evidence-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.recruiter-summary-point,
.recruiter-evidence-item,
.recruiter-suggestion,
.recruiter-provider-card,
.recruiter-message-card {
  border: 1px solid var(--color-border);
  border-radius: 1.25rem;
  background: var(--color-surface);
  padding: 1rem;
}

.recruiter-insight__facts,
.recruiter-provider-card__facts {
  margin: 0;
}

.recruiter-insight__facts div,
.recruiter-provider-card__facts div {
  display: grid;
  gap: 0.25rem;
  min-width: 8rem;
}

.recruiter-insight__facts dt,
.recruiter-provider-card__facts dt {
  color: var(--color-text-muted);
  font-size: var(--type-caption);
}

.recruiter-insight__facts dd,
.recruiter-provider-card__facts dd {
  margin: 0;
  font-weight: 600;
}

.recruiter-draft-toolbar {
  align-items: end;
}

.recruiter-draft-toolbar > :deep(.app-field) {
  flex: 1;
}

.recruiter-draft-toolbar__actions {
  min-width: 12rem;
}

.recruiter-draft-history {
  display: grid;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.recruiter-draft-history__item {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}

.recruiter-inline-error {
  color: var(--color-danger);
}

@media (max-width: 1080px) {
  .recruiter-workspace {
    grid-template-columns: 1fr;
  }

  .recruiter-sidebar {
    position: static;
  }
}

@media (max-width: 720px) {
  .recruiter-provider-card__facts,
  .recruiter-insight__facts,
  .recruiter-summary-points,
  .recruiter-thread-item__meta,
  .recruiter-suggestion__meta,
  .recruiter-message-card__header,
  .recruiter-draft-toolbar,
  .recruiter-draft-history__item,
  .recruiter-provider-card__header,
  .recruiter-actions,
  .recruiter-sync-history,
  .recruiter-hero,
  .recruiter-thread-item__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .recruiter-draft-toolbar__actions {
    width: 100%;
    min-width: 0;
  }
}
</style>
