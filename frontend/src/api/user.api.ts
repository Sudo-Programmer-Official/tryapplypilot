import type {
  ApplicationRecord,
  AlertEvent,
  AuthUser,
  CommunicationDraft,
  CommunicationInsightSummary,
  ConversationSuggestion,
  CompanyPreference,
  CompanyRequest,
  EmailProviderConnection,
  EmailProviderStatus,
  EmailSyncRun,
  InterviewPreparationPlan,
  InterviewQuestion,
  InterviewQuestionSet,
  InterviewRecord,
  InterviewStory,
  JobOpportunity,
  NotificationInsights,
  ProviderAuthorizationRequest,
  RecruiterContactProfile,
  RecruiterMessage,
  RecruiterThread,
  ResumeIntelligenceAnalysis,
  ResumeVersionRecord,
  ProfileEvolutionChangeItem,
  ProfileEvolutionQuestion,
  ProfileEvolutionStateResponse,
  ProfileEvolutionSubmissionResult,
  SavedJobRecord,
  Watchlist,
} from "../types";
import { requestJson } from "./client";

export function fetchUserJobs(): Promise<{ items: JobOpportunity[] }> {
  return requestJson<{ items: JobOpportunity[] }>("/api/auth/me/jobs");
}

export function fetchUserResumeIntelligenceAnalysis(jobId: string): Promise<{ item: ResumeIntelligenceAnalysis }> {
  return requestJson<{ item: ResumeIntelligenceAnalysis }>(`/api/auth/me/resume-intelligence/jobs/${jobId}/analysis`);
}

export function fetchUserApplications(status?: string): Promise<{ items: ApplicationRecord[] }> {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
  return requestJson<{ items: ApplicationRecord[] }>(`/api/auth/me/applications${suffix}`);
}

export function finalizeUserResumeIntelligenceReview(
  jobId: string,
  payload: {
    reviews: Array<{
      change_id: string;
      decision: string;
      edited_text?: string;
    }>;
  },
): Promise<{ item: ResumeVersionRecord }> {
  return requestJson<{ item: ResumeVersionRecord }>(`/api/auth/me/resume-intelligence/jobs/${jobId}/finalize`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function buildUserApplicationPackage(
  jobId: string,
  payload: {
    resume_version_id: string;
    notes?: string;
  },
): Promise<{ item: ApplicationRecord }> {
  return requestJson<{ item: ApplicationRecord }>(`/api/auth/me/applications/jobs/${jobId}/package`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitUserApplication(
  applicationId: string,
  payload: {
    submitted_at?: string;
    portal?: string;
    confirmation_number?: string;
    external_application_id?: string;
    submitted_url?: string;
    answer_ids?: string[];
    artifact_ids?: string[];
    notes?: string;
  },
): Promise<{ item: ApplicationRecord }> {
  return requestJson<{ item: ApplicationRecord }>(`/api/auth/me/applications/${applicationId}/submit`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateUserApplicationStatus(
  applicationId: string,
  payload: {
    status: string;
    notes?: string;
  },
): Promise<{ item: ApplicationRecord }> {
  return requestJson<{ item: ApplicationRecord }>(`/api/auth/me/applications/${applicationId}/status`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function updateUserApplicationTask(
  applicationId: string,
  taskId: string,
  payload: {
    status: string;
    detail?: string;
  },
): Promise<{ item: ApplicationRecord }> {
  return requestJson<{ item: ApplicationRecord }>(`/api/auth/me/applications/${applicationId}/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function updateUserApplicationMetadata(
  applicationId: string,
  payload: {
    recruiter_name?: string;
    recruiter_email?: string;
    hiring_manager?: string;
    application_portal?: string;
    external_application_id?: string;
    confirmation_number?: string;
    submitted_url?: string;
    submission_timestamp?: string;
    deadline?: string;
    assessment_deadline?: string;
    follow_up_date?: string;
    referral_source?: string;
    referral_contact?: string;
    salary_range?: string;
    location?: string;
    work_arrangement?: string;
    sponsorship_status?: string;
    application_source?: string;
  },
): Promise<{ item: ApplicationRecord }> {
  return requestJson<{ item: ApplicationRecord }>(`/api/auth/me/applications/${applicationId}/metadata`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function addUserApplicationNote(
  applicationId: string,
  payload: {
    body: string;
    note_type?: string;
  },
): Promise<{ item: ApplicationRecord }> {
  return requestJson<{ item: ApplicationRecord }>(`/api/auth/me/applications/${applicationId}/notes`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function addUserApplicationAnswer(
  applicationId: string,
  payload: {
    question: string;
    question_key?: string;
    answer: string;
    source?: string;
    reusable?: boolean;
    sensitive_data?: boolean;
    user_approved?: boolean;
  },
): Promise<{ item: ApplicationRecord }> {
  return requestJson<{ item: ApplicationRecord }>(`/api/auth/me/applications/${applicationId}/answers`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function addUserApplicationArtifact(
  applicationId: string,
  payload: {
    kind: string;
    title: string;
    source?: string;
    status?: string;
    url?: string;
    file_name?: string;
    mime_type?: string;
    detail?: string;
    source_id?: string;
    metadata?: Record<string, unknown>;
  },
): Promise<{ item: ApplicationRecord }> {
  return requestJson<{ item: ApplicationRecord }>(`/api/auth/me/applications/${applicationId}/artifacts`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchUserInterviews(params: {
  applicationId?: string;
  interviewStatus?: string;
} = {}): Promise<{ items: InterviewRecord[] }> {
  const search = new URLSearchParams();
  if (params.applicationId) {
    search.set("application_id", params.applicationId);
  }
  if (params.interviewStatus) {
    search.set("interview_status", params.interviewStatus);
  }
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return requestJson<{ items: InterviewRecord[] }>(`/api/auth/me/interviews${suffix}`);
}

export function fetchUserUpcomingInterviews(limit = 10): Promise<{ items: InterviewRecord[] }> {
  return requestJson<{ items: InterviewRecord[] }>(`/api/auth/me/interviews/upcoming?limit=${encodeURIComponent(String(limit))}`);
}

export function fetchUserInterview(interviewId: string): Promise<{ item: InterviewRecord }> {
  return requestJson<{ item: InterviewRecord }>(`/api/auth/me/interviews/${interviewId}`);
}

export function fetchUserInterviewPreparation(interviewId: string): Promise<{ item: InterviewPreparationPlan }> {
  return requestJson<{ item: InterviewPreparationPlan }>(`/api/auth/me/interviews/${interviewId}/preparation`);
}

export function generateUserInterviewPreparation(interviewId: string): Promise<{ item: InterviewPreparationPlan }> {
  return requestJson<{ item: InterviewPreparationPlan }>(`/api/auth/me/interviews/${interviewId}/prepare`, {
    method: "POST",
  });
}

export function updateUserInterviewPreparation(
  interviewId: string,
  payload: {
    checklist?: Array<Record<string, unknown>> | null;
    status?: string | null;
    metadata?: Record<string, unknown> | null;
  },
): Promise<{ item: InterviewPreparationPlan }> {
  return requestJson<{ item: InterviewPreparationPlan }>(`/api/auth/me/interviews/${interviewId}/preparation`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function regenerateUserInterviewPreparation(interviewId: string): Promise<{ item: InterviewPreparationPlan }> {
  return requestJson<{ item: InterviewPreparationPlan }>(`/api/auth/me/interviews/${interviewId}/preparation/regenerate`, {
    method: "POST",
  });
}

export function fetchUserInterviewQuestionSets(interviewId: string): Promise<{ items: InterviewQuestionSet[] }> {
  return requestJson<{ items: InterviewQuestionSet[] }>(`/api/auth/me/interviews/${interviewId}/question-sets`);
}

export function fetchUserCurrentInterviewQuestionSet(interviewId: string): Promise<{ item: InterviewQuestionSet }> {
  return requestJson<{ item: InterviewQuestionSet }>(`/api/auth/me/interviews/${interviewId}/question-sets/current`);
}

export function fetchUserInterviewQuestionSet(questionSetId: string): Promise<{ item: InterviewQuestionSet }> {
  return requestJson<{ item: InterviewQuestionSet }>(`/api/auth/me/interview-question-sets/${questionSetId}`);
}

export function generateUserInterviewQuestions(interviewId: string): Promise<{ item: InterviewQuestionSet }> {
  return requestJson<{ item: InterviewQuestionSet }>(`/api/auth/me/interviews/${interviewId}/questions/generate`, {
    method: "POST",
  });
}

export function regenerateUserInterviewQuestions(interviewId: string): Promise<{ item: InterviewQuestionSet }> {
  return requestJson<{ item: InterviewQuestionSet }>(`/api/auth/me/interviews/${interviewId}/questions/regenerate`, {
    method: "POST",
  });
}

export function updateUserInterviewQuestion(
  questionId: string,
  payload: {
    preparation_status?: string | null;
    priority?: string | null;
    sequence_order?: number | null;
    hidden?: boolean | null;
    archived?: boolean | null;
    metadata?: Record<string, unknown> | null;
  },
): Promise<{ item: InterviewQuestion }> {
  return requestJson<{ item: InterviewQuestion }>(`/api/auth/me/interview-questions/${questionId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function addUserInterviewQuestionNote(
  questionId: string,
  payload: {
    body: string;
  },
): Promise<{ item: InterviewQuestion }> {
  return requestJson<{ item: InterviewQuestion }>(`/api/auth/me/interview-questions/${questionId}/notes`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchUserInterviewStories(interviewId: string): Promise<{ items: InterviewStory[] }> {
  return requestJson<{ items: InterviewStory[] }>(`/api/auth/me/interviews/${interviewId}/stories`);
}

export function generateUserInterviewStories(interviewId: string): Promise<{ items: InterviewStory[] }> {
  return requestJson<{ items: InterviewStory[] }>(`/api/auth/me/interviews/${interviewId}/stories/generate`, {
    method: "POST",
  });
}

export function fetchUserStories(params: {
  applicationId?: string;
  interviewId?: string;
  status?: string;
} = {}): Promise<{ items: InterviewStory[] }> {
  const search = new URLSearchParams();
  if (params.applicationId) {
    search.set("application_id", params.applicationId);
  }
  if (params.interviewId) {
    search.set("interview_id", params.interviewId);
  }
  if (params.status) {
    search.set("status", params.status);
  }
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return requestJson<{ items: InterviewStory[] }>(`/api/auth/me/stories${suffix}`);
}

export function fetchUserStory(storyId: string): Promise<{ item: InterviewStory }> {
  return requestJson<{ item: InterviewStory }>(`/api/auth/me/stories/${storyId}`);
}

export function updateUserStory(
  storyId: string,
  payload: {
    title?: string | null;
    category?: string | null;
    status?: string | null;
    sections?: Array<Record<string, unknown>> | null;
    technical_decisions?: string[] | null;
    tradeoffs?: string[] | null;
    leadership_moments?: string[] | null;
    measurable_outcomes?: string[] | null;
    lessons_learned?: string[] | null;
    interviewer_follow_ups?: string[] | null;
    tags?: string[] | null;
    missing_information_prompts?: Array<Record<string, unknown>> | null;
    metadata?: Record<string, unknown> | null;
  },
): Promise<{ item: InterviewStory }> {
  return requestJson<{ item: InterviewStory }>(`/api/auth/me/stories/${storyId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function approveUserStory(storyId: string): Promise<{ item: InterviewStory }> {
  return requestJson<{ item: InterviewStory }>(`/api/auth/me/stories/${storyId}/approve`, {
    method: "POST",
  });
}

export function archiveUserStory(storyId: string): Promise<{ item: InterviewStory }> {
  return requestJson<{ item: InterviewStory }>(`/api/auth/me/stories/${storyId}/archive`, {
    method: "POST",
  });
}

export function regenerateUserStory(storyId: string): Promise<{ item: InterviewStory }> {
  return requestJson<{ item: InterviewStory }>(`/api/auth/me/stories/${storyId}/regenerate`, {
    method: "POST",
  });
}

export function createUserInterview(
  applicationId: string,
  payload: {
    interview_type: string;
    interview_round?: string;
    interview_status?: string;
    scheduled_start_at?: string;
    scheduled_end_at?: string;
    timezone?: string;
    meeting_url?: string;
    recruiter_name?: string;
    recruiter_email?: string;
    recruiter_contact_id?: string;
    notes?: string;
    preparation_status?: string;
    interviewers?: Array<Record<string, unknown>>;
    preparation_checklist?: Array<Record<string, unknown>>;
    source?: string;
    metadata?: Record<string, unknown>;
  },
): Promise<{ item: InterviewRecord }> {
  return requestJson<{ item: InterviewRecord }>(`/api/auth/me/applications/${applicationId}/interviews`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateUserInterview(
  interviewId: string,
  payload: {
    interview_type?: string | null;
    interview_round?: string | null;
    interview_status?: string | null;
    scheduled_start_at?: string | null;
    scheduled_end_at?: string | null;
    timezone?: string | null;
    meeting_url?: string | null;
    recruiter_name?: string | null;
    recruiter_email?: string | null;
    recruiter_contact_id?: string | null;
    notes?: string | null;
    preparation_status?: string | null;
    interviewers?: Array<Record<string, unknown>> | null;
    preparation_checklist?: Array<Record<string, unknown>> | null;
    source?: string | null;
    metadata?: Record<string, unknown> | null;
  },
): Promise<{ item: InterviewRecord }> {
  return requestJson<{ item: InterviewRecord }>(`/api/auth/me/interviews/${interviewId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteUserInterview(interviewId: string): Promise<{ item: InterviewRecord }> {
  return requestJson<{ item: InterviewRecord }>(`/api/auth/me/interviews/${interviewId}`, {
    method: "DELETE",
  });
}

export function fetchUserRecruiterMessages(params: {
  applicationId?: string;
  messageType?: string;
  threadId?: string;
  matchedOnly?: boolean;
} = {}): Promise<{ items: RecruiterMessage[] }> {
  const search = new URLSearchParams();
  if (params.applicationId) {
    search.set("application_id", params.applicationId);
  }
  if (params.messageType) {
    search.set("message_type", params.messageType);
  }
  if (params.threadId) {
    search.set("thread_id", params.threadId);
  }
  if (params.matchedOnly) {
    search.set("matched_only", "true");
  }
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return requestJson<{ items: RecruiterMessage[] }>(`/api/auth/me/recruiter/messages${suffix}`);
}

export function fetchUserRecruiterThreads(applicationId?: string): Promise<{ items: RecruiterThread[] }> {
  const suffix = applicationId ? `?application_id=${encodeURIComponent(applicationId)}` : "";
  return requestJson<{ items: RecruiterThread[] }>(`/api/auth/me/recruiter/threads${suffix}`);
}

export function fetchUserRecruiterThread(threadId: string): Promise<{ item: RecruiterThread }> {
  return requestJson<{ item: RecruiterThread }>(`/api/auth/me/recruiter/threads/${threadId}`);
}

export function fetchUserRecruiterThreadSummary(threadId: string): Promise<{ item: CommunicationInsightSummary }> {
  return requestJson<{ item: CommunicationInsightSummary }>(`/api/auth/me/recruiter/threads/${threadId}/summary`);
}

export function fetchUserRecruiterContacts(): Promise<{ items: RecruiterContactProfile[] }> {
  return requestJson<{ items: RecruiterContactProfile[] }>("/api/auth/me/recruiter/contacts");
}

export function fetchUserRecruiterMessage(messageId: string): Promise<{ item: RecruiterMessage }> {
  return requestJson<{ item: RecruiterMessage }>(`/api/auth/me/recruiter/messages/${messageId}`);
}

export function fetchUserRecruiterMessageSummary(messageId: string): Promise<{ item: CommunicationInsightSummary }> {
  return requestJson<{ item: CommunicationInsightSummary }>(`/api/auth/me/recruiter/messages/${messageId}/summary`);
}

export function fetchUserRecruiterMessageSuggestions(messageId: string): Promise<{ items: ConversationSuggestion[] }> {
  return requestJson<{ items: ConversationSuggestion[] }>(`/api/auth/me/recruiter/messages/${messageId}/suggestions`);
}

export function fetchUserRecruiterDrafts(params: {
  threadId?: string;
  applicationId?: string;
  latestOnly?: boolean;
} = {}): Promise<{ items: CommunicationDraft[] }> {
  const search = new URLSearchParams();
  if (params.threadId) {
    search.set("thread_id", params.threadId);
  }
  if (params.applicationId) {
    search.set("application_id", params.applicationId);
  }
  if (typeof params.latestOnly === "boolean") {
    search.set("latest_only", String(params.latestOnly));
  }
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return requestJson<{ items: CommunicationDraft[] }>(`/api/auth/me/recruiter/drafts${suffix}`);
}

export function generateUserRecruiterDraft(payload: {
  thread_id: string;
  draft_kind?: string;
  tone?: string;
  source_message_id?: string;
}): Promise<{ item: CommunicationDraft }> {
  return requestJson<{ item: CommunicationDraft }>("/api/auth/me/recruiter/drafts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateUserRecruiterDraft(
  draftId: string,
  payload: {
    subject?: string | null;
    body?: string | null;
    status?: string | null;
  },
): Promise<{ item: CommunicationDraft }> {
  return requestJson<{ item: CommunicationDraft }>(`/api/auth/me/recruiter/drafts/${draftId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function fetchUserRecruiterProviderStatuses(): Promise<{ items: EmailProviderStatus[] }> {
  return requestJson<{ items: EmailProviderStatus[] }>("/api/auth/me/recruiter/providers/status");
}

export function startUserRecruiterGmailConnect(payload: {
  scopes?: string[];
  login_hint?: string;
  metadata?: Record<string, unknown>;
} = {}): Promise<{ item: ProviderAuthorizationRequest }> {
  return requestJson<{ item: ProviderAuthorizationRequest }>("/api/auth/me/recruiter/connect/gmail/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function completeUserRecruiterGmailConnect(payload: {
  code: string;
  state: string;
}): Promise<{ item: EmailProviderConnection }> {
  return requestJson<{ item: EmailProviderConnection }>("/api/auth/me/recruiter/connect/gmail/complete", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function disconnectUserRecruiterGmail(): Promise<{ item: EmailProviderConnection }> {
  return requestJson<{ item: EmailProviderConnection }>("/api/auth/me/recruiter/connect/gmail", {
    method: "DELETE",
  });
}

export function syncUserRecruiterProvider(payload: { provider?: string } = {}): Promise<{ items: EmailSyncRun[] }> {
  return requestJson<{ items: EmailSyncRun[] }>("/api/auth/me/recruiter/sync", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchUserRecruiterSyncHistory(params: {
  provider?: string;
  limit?: number;
} = {}): Promise<{ items: EmailSyncRun[] }> {
  const search = new URLSearchParams();
  if (params.provider) {
    search.set("provider", params.provider);
  }
  if (typeof params.limit === "number") {
    search.set("limit", String(params.limit));
  }
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return requestJson<{ items: EmailSyncRun[] }>(`/api/auth/me/recruiter/sync/history${suffix}`);
}

export function fetchUserResumeIntelligenceVersionContent(versionId: string): Promise<{
  item: {
    version_id: string;
    file_name: string;
    mime_type: string;
    content_base64: string;
  };
}> {
  return requestJson<{ item: { version_id: string; file_name: string; mime_type: string; content_base64: string } }>(
    `/api/auth/me/resume-intelligence/versions/${versionId}/content`,
  );
}

export function fetchUserAlerts(): Promise<{ items: AlertEvent[] }> {
  return requestJson<{ items: AlertEvent[] }>("/api/auth/me/alerts");
}

export function fetchUserMissedOpportunities(): Promise<{ items: JobOpportunity[] }> {
  return requestJson<{ items: JobOpportunity[] }>("/api/auth/me/missed-opportunities");
}

export function fetchUserNotificationInsights(): Promise<NotificationInsights> {
  return requestJson<NotificationInsights>("/api/auth/me/notification-insights");
}

export function fetchUserCompanyRequests(): Promise<{ items: CompanyRequest[] }> {
  return requestJson<{ items: CompanyRequest[] }>("/api/auth/me/company-requests");
}

export function fetchUserCompanies(): Promise<{ items: CompanyPreference[] }> {
  return requestJson<{ items: CompanyPreference[] }>("/api/auth/me/companies");
}

export function createUserCompanyRequest(payload: {
  company_name: string;
  career_url: string;
  connector_suggestion: string;
  external_identifier_suggestion: string;
  notes: string;
}): Promise<{ item: CompanyRequest }> {
  return requestJson<{ item: CompanyRequest }>("/api/auth/me/company-requests", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchUserSavedJobs(): Promise<{ items: SavedJobRecord[] }> {
  return requestJson<{ items: SavedJobRecord[] }>("/api/auth/me/saved-jobs");
}

export function saveUserSavedJob(jobId: string): Promise<{ item: SavedJobRecord }> {
  return requestJson<{ item: SavedJobRecord }>("/api/auth/me/saved-jobs", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId }),
  });
}

export function deleteUserSavedJob(jobId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/auth/me/saved-jobs/${jobId}`, {
    method: "DELETE",
  });
}

export function fetchUserWatchlists(): Promise<{ items: Watchlist[] }> {
  return requestJson<{ items: Watchlist[] }>("/api/auth/me/watchlists");
}

export function createUserWatchlist(watchlist: Watchlist): Promise<{ item: Watchlist }> {
  return requestJson<{ item: Watchlist }>("/api/auth/me/watchlists", {
    method: "POST",
    body: JSON.stringify({
      name: watchlist.name,
      enabled: watchlist.enabled,
      terms: watchlist.terms.map((term) => ({
        term: term.term,
        company: term.company,
        enabled: term.enabled,
      })),
    }),
  });
}

export function updateUserWatchlist(watchlist: Watchlist): Promise<{ item: Watchlist }> {
  return requestJson<{ item: Watchlist }>(`/api/auth/me/watchlists/${watchlist.id}`, {
    method: "PATCH",
    body: JSON.stringify({
      name: watchlist.name,
      enabled: watchlist.enabled,
      terms: watchlist.terms.map((term) => ({
        term: term.term,
        company: term.company,
        enabled: term.enabled,
      })),
    }),
  });
}

export function deleteUserWatchlist(watchlistId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/auth/me/watchlists/${watchlistId}`, {
    method: "DELETE",
  });
}

export function saveUserProfile(payload: Record<string, unknown>): Promise<{ user: AuthUser }> {
  return requestJson<{ user: AuthUser }>("/api/auth/me/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function saveUserPreferences(payload: Record<string, unknown>): Promise<{ user: AuthUser }> {
  return requestJson<{ user: AuthUser }>("/api/auth/me/preferences", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function fetchUserProfileEvolutionState(): Promise<ProfileEvolutionStateResponse> {
  return requestJson<ProfileEvolutionStateResponse>("/api/auth/me/profile-evolution/state");
}

export function fetchUserProfileEvolutionNextQuestion(): Promise<{ item: ProfileEvolutionQuestion | null }> {
  return requestJson<{ item: ProfileEvolutionQuestion | null }>("/api/auth/me/profile-evolution/next-question");
}

export function submitUserProfileEvolutionAnswer(payload: {
  answer: string;
  topic?: string;
  question_id?: string;
  question_prompt?: string;
}): Promise<ProfileEvolutionSubmissionResult> {
  return requestJson<ProfileEvolutionSubmissionResult>("/api/auth/me/profile-evolution/answers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchUserProfileEvolutionChanges(params: {
  limit?: number;
  sessionId?: string;
} = {}): Promise<{ items: ProfileEvolutionChangeItem[] }> {
  const search = new URLSearchParams();
  if (typeof params.limit === "number") {
    search.set("limit", String(params.limit));
  }
  if (params.sessionId) {
    search.set("session_id", params.sessionId);
  }
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return requestJson<{ items: ProfileEvolutionChangeItem[] }>(`/api/auth/me/profile-evolution/changes${suffix}`);
}

export function approveUserProfileEvolutionChange(
  versionId: string,
  reviewNotes = "",
): Promise<{ item: { version_id: string; status: string; entity: Record<string, unknown>; review_notes: string } }> {
  return requestJson<{ item: { version_id: string; status: string; entity: Record<string, unknown>; review_notes: string } }>(
    `/api/auth/me/profile-evolution/changes/${versionId}/approve`,
    {
      method: "POST",
      body: JSON.stringify({ review_notes: reviewNotes }),
    },
  );
}

export function rejectUserProfileEvolutionChange(versionId: string, reviewNotes = ""): Promise<{ item: Record<string, unknown> }> {
  return requestJson<{ item: Record<string, unknown> }>(`/api/auth/me/profile-evolution/changes/${versionId}/reject`, {
    method: "POST",
    body: JSON.stringify({ review_notes: reviewNotes }),
  });
}
