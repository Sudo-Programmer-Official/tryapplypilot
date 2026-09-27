export type UserRole = "super_admin" | "admin" | "user";
export type MatchDecision = "APPLY_NOW" | "REVIEW" | "IGNORE";
export type JobStatus = "new" | "seen" | "dismissed" | "skipped";
export type ThemeMode = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";
export type StatusTone = "healthy" | "warning" | "failed" | "inactive" | "info";
export type ToastTone = "success" | "error" | "info";
export type CompanyPriorityLevel = "dream" | "high" | "normal" | "hidden";

export interface SkillPriority {
  skill: string;
  weight: number;
}

export interface ResumeProfileSummary {
  resume_id?: string;
  display_name?: string;
  skills?: string[];
  role_focus?: string;
  created_at?: string | null;
}

export interface JobOpportunity {
  id: string;
  company: string;
  title: string;
  source: string;
  location: string;
  remote_policy: string;
  posted_minutes_ago: number;
  match_score: number;
  decision: MatchDecision;
  why: string[];
  recommended_resume: string;
  duplicate_sources: number;
  status: JobStatus;
  alert_sent: boolean;
  apply_url: string;
  gaps: string[];
  country_code: string | null;
  country_display: string;
  freshness_label: string;
  freshness_tone: "fresh" | "aging" | "stale";
  recommendation: string;
  recommendation_tone: "apply" | "review" | "skip";
  notification_status?: string | null;
  notification_reason?: string | null;
  notification_type?: string | null;
}

export interface JobListResponse {
  items: JobOpportunity[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface CompanyPreference {
  id: string;
  company: string;
  enabled: boolean;
  tier: number;
  priority: number;
  connector: string;
  poll_interval_minutes: number;
  country: string;
  career_url: string;
  external_identifier: string;
  role_families: string[];
}

export interface RolePreference {
  label: string;
  enabled: boolean;
}

export interface NotificationChannel {
  channel: "telegram" | "email" | "slack" | "desktop";
  enabled: boolean;
  destination: string;
}

export interface WatchlistTerm {
  id: string;
  term: string;
  company: string;
  enabled: boolean;
}

export interface Watchlist {
  id: string;
  name: string;
  enabled: boolean;
  terms: WatchlistTerm[];
}

export interface OnboardingStep {
  id: string;
  label: string;
  completed: boolean;
}

export interface OnboardingStatus {
  progress_percent: number;
  steps: OnboardingStep[];
}

export interface UserProfileRecord {
  linkedin_url?: string;
  portfolio_url?: string;
  github_url?: string;
  years_of_experience?: number | null;
  visa_status?: string;
  work_authorization?: string;
  resume_uploaded?: boolean;
  resume_library?: ResumeProfileSummary[];
  resume_skill_keywords?: string[];
}

export interface UserPreferencesRecord {
  country?: string;
  locations?: string[];
  preferred_companies?: string[];
  company_priorities?: Record<string, CompanyPriorityLevel>;
  preferred_roles?: string[];
  skills?: string[];
  skill_priorities?: SkillPriority[];
  work_arrangements?: string[];
  experience_levels?: string[];
  job_types?: string[];
  company_sizes?: string[];
  industries?: string[];
  minimum_salary?: number | null;
  desired_salary?: number | null;
  visa_status?: string;
  years_of_experience?: number | null;
  travel_preference?: string;
  remote_preference?: string;
  freshness_hours?: number;
  search_window_hours?: number;
  minimum_match_score?: number;
  notification_frequency?: string;
  notification_rules?: string[];
  excluded_keywords?: string[];
  resume_strategy?: string;
  preferred_resume_variants?: string[];
}

export interface AuthUser {
  id: string;
  email: string;
  role: UserRole;
  full_name: string;
  telegram_chat_id: string | null;
  country: string;
  profile: UserProfileRecord;
  preferences: UserPreferencesRecord;
  onboarding: OnboardingStatus;
  created_at: string | null;
  last_login_at: string | null;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in_seconds: number;
  refresh_expires_in_seconds: number;
}

export interface TelegramConnectSession {
  connect_token: string;
  connect_url: string;
  connect_command?: string;
  bot_username: string;
  expires_in_seconds: number;
  already_connected: boolean;
  delivery_chat_id: string | null;
}

export interface TelegramVerifyResult {
  connected: boolean;
  chat_id: string | null;
  delivery_chat_id: string | null;
  message?: string;
  user: AuthUser;
}

export interface ResumeAsset {
  id: string;
  user_id: string;
  display_name: string;
  original_filename: string;
  storage_path: string;
  mime_type: string;
  file_size_bytes: number;
  extracted_text_preview: string;
  extracted_skills: string[];
  role_focus: string;
  created_at: string | null;
}

export interface ResumeSelectionReason {
  label: string;
  detail: string;
}

export interface ResumeSelectionResult {
  status: string;
  confidence: number;
  resume_id: string | null;
  display_name: string;
  original_filename: string;
  role_focus: string;
  matched_requirements: string[];
  reason_summary: ResumeSelectionReason[];
  fallback_behavior: string;
}

export interface ResumeIntelligenceGapEvidence {
  source_type: string;
  source_id: string;
  excerpt: string;
  confidence: number;
}

export interface JobRequirement {
  label: string;
  category: string;
  keywords: string[];
}

export interface RequirementAssessment {
  label: string;
  category: string;
  status: string;
  source: string;
  confidence: number;
  reason: string;
  evidence: ResumeIntelligenceGapEvidence[];
}

export interface GapAnalysisResult {
  covered_requirements: RequirementAssessment[];
  weak_requirements: RequirementAssessment[];
  missing_requirements: RequirementAssessment[];
  keyword_opportunities: string[];
  risk_flags: string[];
}

export interface RetrievedRequirementEvidence {
  requirement_label: string;
  category: string;
  support_level: string;
  rationale: string;
  entity_names: string[];
  evidence: ResumeIntelligenceGapEvidence[];
}

export interface EvidenceRetrievalResult {
  items: RetrievedRequirementEvidence[];
  missing_proof_flags: string[];
}

export interface ResumeChange {
  change_id: string;
  section: string;
  entry_id: string;
  operation: string;
  original_text: string;
  suggested_text: string;
  rationale: string;
  job_requirements: string[];
  evidence: ResumeIntelligenceGapEvidence[];
  confidence: number;
  risk_level: string;
  status: string;
}

export interface ResumeChangeSet {
  status: string;
  source_resume_id: string | null;
  source_resume_name: string;
  changes: ResumeChange[];
  blocked_requirements: string[];
  summary: string;
  added_count: number;
  modified_count: number;
  removed_count: number;
}

export interface CritiqueDimensionScore {
  label: string;
  before: number;
  after: number;
  rationale: string;
}

export interface ResumeCritiqueResult {
  verdict: string;
  overall_before: number;
  overall_after: number;
  dimensions: CritiqueDimensionScore[];
  issues: string[];
  strengths: string[];
  summary: string;
}

export interface ResumeIntelligenceAnalysis {
  generated_at: string;
  job: {
    job_id: string;
    user_id: string;
    company: string;
    title: string;
    location: string;
    remote_policy: string;
    apply_url: string;
    description_text: string;
    connector_key: string;
    published_at: string | null;
    match_score: number | null;
    decision: string;
    recommended_resume: string;
    why: string[];
    gaps: string[];
  };
  requirements: JobRequirement[];
  selection: ResumeSelectionResult;
  gap_analysis: GapAnalysisResult;
  evidence_retrieval: EvidenceRetrievalResult;
  change_set: ResumeChangeSet;
  critique: ResumeCritiqueResult;
}

export interface ResumeVersionRecord {
  version_id: string;
  user_id: string;
  job_id: string;
  source_resume_id: string | null;
  source_resume_name: string;
  file_name: string;
  pdf_storage_path: string;
  text_storage_path: string;
  status: string;
  version_signature: string;
  accepted_changes: Array<Record<string, unknown>>;
  rejected_changes: Array<Record<string, unknown>>;
  blocked_requirements: string[];
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface ApplicationPackageArtifact {
  artifact_id: string;
  kind: string;
  label: string;
  status: string;
  version: number;
  source: string;
  url: string;
  file_name: string;
  mime_type: string;
  detail: string;
  source_id: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
  audit_history: Array<Record<string, unknown>>;
}

export interface ApplicationTask {
  task_id: string;
  label: string;
  status: string;
  detail: string;
  action: string;
  action_url: string;
  due_at: string | null;
  completed_at: string | null;
  priority: string;
  category: string;
  source: string;
  generated: boolean;
  reminder_status: string;
  updated_at: string | null;
}

export interface ApplicationNote {
  note_id: string;
  note_type: string;
  body: string;
  created_at: string | null;
  created_by_user_id: string | null;
}

export interface ApplicationAnswer {
  answer_id: string;
  application_id: string;
  question: string;
  normalized_question_key: string;
  answer: string;
  source: string;
  created_at: string | null;
  last_used_at: string | null;
  reusable: boolean;
  sensitive_data: boolean;
  user_approved: boolean;
  status: string;
}

export interface ApplicationStructuredMetadata {
  recruiter_name: string;
  recruiter_email: string;
  hiring_manager: string;
  application_portal: string;
  external_application_id: string;
  confirmation_number: string;
  submitted_url: string;
  submission_timestamp: string | null;
  deadline: string | null;
  assessment_deadline: string | null;
  follow_up_date: string | null;
  referral_source: string;
  referral_contact: string;
  salary_range: string;
  location: string;
  work_arrangement: string;
  sponsorship_status: string;
  application_source: string;
}

export interface ApplicationSubmissionRecord {
  submitted_at: string | null;
  portal: string;
  confirmation_number: string;
  external_application_id: string;
  submitted_url: string;
  resume_version_id: string;
  answer_ids: string[];
  artifact_ids: string[];
}

export interface ApplicationTimelineEvent {
  event_type: string;
  label: string;
  detail: string;
  occurred_at: string | null;
}

export interface ApplicationRecord {
  application_id: string;
  user_id: string;
  job_id: string;
  resume_version_id: string;
  status: string;
  package_signature: string;
  company: string;
  title: string;
  apply_url: string;
  match_score: number | null;
  decision: string;
  artifacts: ApplicationPackageArtifact[];
  tasks: ApplicationTask[];
  notes: ApplicationNote[];
  answers: ApplicationAnswer[];
  structured_metadata: ApplicationStructuredMetadata;
  submission: ApplicationSubmissionRecord;
  timeline: ApplicationTimelineEvent[];
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  applied_at: string | null;
}

export interface InterviewParticipant {
  participant_id: string;
  name: string;
  email: string;
  title: string;
  role: string;
  source_contact_id: string;
}

export interface InterviewPreparationItem {
  item_id: string;
  label: string;
  status: string;
  detail: string;
  reason: string;
  estimated_effort: string;
  priority: string;
  category: string;
  source: string;
  due_at: string | null;
  completed_at: string | null;
  generated: boolean;
  updated_at: string | null;
  supporting_evidence: InterviewPreparationEvidenceReference[];
}

export interface InterviewTimelineEvent {
  event_type: string;
  label: string;
  detail: string;
  occurred_at: string | null;
}

export interface InterviewAuditEntry {
  event_type: string;
  detail: string;
  actor_user_id: string | null;
  created_at: string | null;
}

export interface InterviewPreparationEvidenceReference {
  reference_id: string;
  source_type: string;
  source_id: string;
  label: string;
  excerpt: string;
  evidence_id: string;
  relevance_explanation: string;
  confidence: number;
  entity_type: string;
  entity_id: string;
  metadata: Record<string, unknown>;
}

export interface InterviewPreparationSection {
  section_key: string;
  title: string;
  content: string[];
  evidence_references: InterviewPreparationEvidenceReference[];
  confidence: number;
  generated_at: string | null;
  strategy_version: string;
}

export interface InterviewPreparationRisk {
  risk_id: string;
  title: string;
  detail: string;
  recommendation: string;
  severity: string;
  confidence: number;
  evidence_references: InterviewPreparationEvidenceReference[];
  generated_at: string | null;
  strategy_version: string;
}

export interface InterviewPreparationPlan {
  plan_id: string;
  interview_id: string;
  application_id: string;
  user_id: string;
  version_number: number;
  status: string;
  strategy_version: string;
  focus_labels: string[];
  overall_confidence: number;
  sections: InterviewPreparationSection[];
  checklist: InterviewPreparationItem[];
  risks: InterviewPreparationRisk[];
  metadata: Record<string, unknown>;
  generated_at: string | null;
  updated_at: string | null;
}

export interface InterviewQuestionNote {
  note_id: string;
  body: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface InterviewQuestionFollowUp {
  follow_up_id: string;
  question: string;
  rationale: string;
  evaluation_dimensions: string[];
  confidence: number;
}

export interface InterviewQuestion {
  question_id: string;
  question_set_id: string;
  interview_id: string;
  application_id: string;
  user_id: string;
  category: string;
  question: string;
  rationale: string;
  evaluation_dimensions: string[];
  related_job_requirements: string[];
  related_evidence: InterviewPreparationEvidenceReference[];
  follow_up_questions: InterviewQuestionFollowUp[];
  difficulty: string;
  priority: string;
  confidence: number;
  expected_answer_outline: string[];
  risk_tags: string[];
  sequence_order: number;
  preparation_status: string;
  hidden: boolean;
  archived: boolean;
  user_notes: InterviewQuestionNote[];
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface InterviewQuestionSet {
  question_set_id: string;
  interview_id: string;
  application_id: string;
  user_id: string;
  version_number: number;
  status: string;
  title: string;
  interview_type: string;
  interview_round: string;
  strategy_version: string;
  source_preparation_plan_id: string;
  provider: string;
  model_key: string;
  metadata: Record<string, unknown>;
  generated_at: string | null;
  updated_at: string | null;
  superseded_by_question_set_id: string;
  questions: InterviewQuestion[];
}

export interface InterviewStorySection {
  section_key: string;
  title: string;
  content: string[];
  evidence_references: InterviewPreparationEvidenceReference[];
  missing_fields: string[];
}

export interface InterviewStoryGapPrompt {
  prompt_id: string;
  field_key: string;
  prompt: string;
  reason: string;
  topic: string;
  status: string;
  related_evidence: InterviewPreparationEvidenceReference[];
  profile_evolution_payload: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface InterviewStoryCoverageLink {
  question_id: string;
  question: string;
  category: string;
  coverage_score: number;
  reason: string;
  confidence: number;
}

export interface InterviewStoryQualityDimension {
  label: string;
  score: number;
  rationale: string;
}

export interface InterviewStoryQualityAssessment {
  overall_score: number;
  dimensions: InterviewStoryQualityDimension[];
  summary: string;
  generated_at: string | null;
  strategy_version: string;
}

export interface InterviewStory {
  story_id: string;
  story_group_id: string;
  user_id: string;
  application_id: string | null;
  interview_id: string | null;
  linked_application_ids: string[];
  linked_interview_ids: string[];
  title: string;
  category: string;
  source_evidence: InterviewPreparationEvidenceReference[];
  related_projects: string[];
  related_resume_version_id: string;
  related_question_ids: string[];
  interview_types: string[];
  tags: string[];
  version_number: number;
  status: string;
  sections: InterviewStorySection[];
  technical_decisions: string[];
  tradeoffs: string[];
  leadership_moments: string[];
  measurable_outcomes: string[];
  lessons_learned: string[];
  interviewer_follow_ups: string[];
  coverage: InterviewStoryCoverageLink[];
  quality: InterviewStoryQualityAssessment;
  missing_information_prompts: InterviewStoryGapPrompt[];
  superseded_by_story_id: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface InterviewRecord {
  interview_id: string;
  application_id: string;
  user_id: string;
  interview_type: string;
  interview_round: string;
  interview_status: string;
  preparation_status: string;
  scheduled_start_at: string | null;
  scheduled_end_at: string | null;
  timezone: string;
  meeting_url: string;
  recruiter_name: string;
  recruiter_email: string;
  recruiter_contact_id: string;
  notes: string;
  source: string;
  interviewers: InterviewParticipant[];
  preparation_checklist: InterviewPreparationItem[];
  timeline: InterviewTimelineEvent[];
  audit_history: InterviewAuditEntry[];
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
}

export interface CommunicationEvidence {
  source_type: string;
  source_id: string;
  label: string;
  excerpt: string;
}

export interface CommunicationInsightSummary {
  summary_id: string;
  scope_type: string;
  scope_id: string;
  thread_id: string;
  application_id: string | null;
  message_id: string;
  title: string;
  summary: string;
  communication_objective: string;
  key_points: string[];
  pending_action: string;
  risks: string[];
  evidence: CommunicationEvidence[];
  assumptions: string[];
  confidence: number;
  strategy_version: string;
  generated_at: string | null;
}

export interface CommunicationDraft {
  draft_id: string;
  draft_group_id: string;
  version_number: number;
  user_id: string;
  thread_id: string;
  draft_kind: string;
  tone: string;
  status: string;
  intended_recipient: string;
  intended_recipient_email: string;
  communication_objective: string;
  subject: string;
  body: string;
  confidence: number;
  explanation: string;
  strategy_version: string;
  model_key: string;
  application_id: string | null;
  source_message_id: string;
  parent_draft_id: string;
  evidence: CommunicationEvidence[];
  assumptions: string[];
  user_edited: boolean;
  generated_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ConversationSla {
  waiting_on: string;
  last_recruiter_message_at: string | null;
  last_candidate_response_at: string | null;
  last_contact_at: string | null;
  response_latency_hours: number | null;
  average_response_latency_hours: number | null;
  days_since_last_contact: number | null;
  overdue_threshold_hours: number;
  overdue: boolean;
}

export interface ConversationState {
  application_id: string | null;
  thread_id: string;
  state: string;
  label: string;
  waiting_on: string;
  derived_from_message_id: string;
  last_message_type: string;
  last_message_at: string | null;
  reason: string;
  sla: ConversationSla;
}

export interface CommunicationHealth {
  application_id: string | null;
  status: string;
  label: string;
  score: number;
  waiting_on: string;
  last_message_at: string | null;
  needs_follow_up: boolean;
  reason: string;
}

export interface ConversationSuggestion {
  suggestion_id: string;
  action_type: string;
  label: string;
  reason: string;
  confidence: number;
  supporting_message_id: string;
  supporting_message_subject: string;
  related_application_id: string | null;
  due_at: string | null;
  waiting_on: string;
}

export interface CommunicationSummary {
  application_id: string | null;
  last_message_id: string;
  last_thread_id: string;
  last_message_type: string;
  last_message_subject: string;
  last_contact_date: string | null;
  pending_action: string;
  conversation_status: string;
  response_overdue: boolean;
  suggested_actions: string[];
  recruiter_name: string;
  recruiter_email: string;
  confidence: number;
  reason: string;
  waiting_on: string;
  conversation_state: ConversationState;
  health: CommunicationHealth;
  sla: ConversationSla;
  suggestions: ConversationSuggestion[];
}

export interface RecruiterContactApplicationLink {
  application_id: string;
  company: string;
  title: string;
  status: string;
  last_contact_at: string | null;
}

export interface RecruiterContact {
  contact_id: string;
  user_id: string;
  display_name: string;
  email: string;
  company: string;
  title: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface RecruiterContactProfile {
  contact: RecruiterContact;
  applications_connected: RecruiterContactApplicationLink[];
  last_contact_at: string | null;
  total_conversations: number;
  total_messages: number;
  average_response_time_hours: number | null;
  waiting_on: string;
  latest_conversation_state: string;
  latest_health_status: string;
}

export interface RecruiterThread {
  thread_id: string;
  user_id: string;
  application_id: string | null;
  recruiter: RecruiterContact;
  subject: string;
  company: string;
  job_title: string;
  last_message_id: string;
  last_message_at: string | null;
  message_count: number;
  source: string;
  confidence: number;
  conversation_status: string;
  pending_action: string;
  response_overdue: boolean;
  created_at: string | null;
  updated_at: string | null;
  metadata: Record<string, unknown>;
}

export interface RecruiterMessage {
  message_id: string;
  thread_id: string;
  user_id: string;
  application_id: string | null;
  recruiter: RecruiterContact;
  sender: string;
  recipients: string[];
  subject: string;
  body_reference: string;
  body_preview: string;
  received_at: string | null;
  message_type: string;
  confidence: number;
  source: string;
  timeline_id: string;
  company: string;
  job_title: string;
  matched: boolean;
  match_confidence: number;
  match_reason: string;
  classification_reason: string;
  suggested_actions: string[];
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface CommunicationEvent {
  event_id: string;
  user_id: string;
  application_id: string | null;
  thread_id: string;
  message_id: string;
  event_type: string;
  title: string;
  detail: string;
  occurred_at: string | null;
  source: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
}

export interface ProviderAuthorizationRequest {
  provider: string;
  authorization_url: string;
  expires_in_seconds: number;
  scopes: string[];
  metadata: Record<string, unknown>;
}

export interface EmailProviderConnection {
  connection_id: string;
  user_id: string;
  provider: string;
  account_email: string;
  status: string;
  scopes: string[];
  connected_at: string | null;
  disconnected_at: string | null;
  last_sync_at: string | null;
  sync_cursor: string;
  token_configured: boolean;
}

export interface EmailProviderStatus {
  provider: string;
  account_email: string;
  status: string;
  connected_at: string | null;
  disconnected_at: string | null;
  last_sync_at: string | null;
  sync_cursor: string;
  token_configured: boolean;
  last_run_status: string;
  last_run_started_at: string | null;
  last_run_completed_at: string | null;
  last_imported_count: number;
  last_skipped_count: number;
  last_duplicate_count: number;
  last_error_count: number;
}

export interface EmailSyncRun {
  sync_run_id: string;
  connection_id: string;
  user_id: string;
  provider: string;
  account_email: string;
  run_status: string;
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  imported_count: number;
  skipped_count: number;
  duplicate_count: number;
  error_count: number;
  metadata: Record<string, unknown>;
}

export interface CompanyRequest {
  id: string;
  user_id: string;
  requester_email: string;
  company_name: string;
  career_url: string;
  connector_suggestion: string;
  external_identifier_suggestion: string;
  notes: string;
  status: "pending" | "approved" | "rejected";
  admin_notes: string;
  reviewed_at: string | null;
  reviewed_by_user_id: string | null;
  approved_company_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface SavedJobRecord {
  id: string;
  user_id: string;
  job_id: string;
  saved_at: string | null;
}

export interface ProfileEvolutionQuestion {
  id: string;
  topic: string;
  prompt: string;
  rationale: string;
  missing_fields: string[];
  confidence: number;
}

export interface ProfileEvolutionTopicProgress {
  topic: string;
  answers: string[];
  extracted_fields: Record<string, unknown>;
  asked_follow_ups: string[];
  staged_version_ids: string[];
  status: "pending" | "completed" | "skipped";
  confidence: number;
}

export interface ProfileEvolutionSession {
  id: string;
  user_id: string;
  current_topic: string | null;
  completed_topics: string[];
  pending_topics: string[];
  skipped_topics: string[];
  confidence: number;
  extracted_entities: Array<Record<string, unknown>>;
  topic_progress: Record<string, ProfileEvolutionTopicProgress>;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProfileEvolutionStateResponse {
  session: ProfileEvolutionSession;
  remaining_topics: string[];
}

export interface ProfileEvolutionExtractedFact {
  topic: string;
  entity_type: string;
  canonical_name: string;
  content: Record<string, unknown>;
  reason: string;
  confidence: number;
  extracted_fields: Record<string, unknown>;
}

export interface ProfileEvolutionSubmissionResult {
  session: ProfileEvolutionSession;
  extracted_facts: ProfileEvolutionExtractedFact[];
  staged_version_ids: string[];
  knowledge_gain: Record<string, number>;
  next_question: ProfileEvolutionQuestion | null;
}

export interface KnowledgeEvidenceRecord {
  id: string;
  user_id: string;
  source_type: string;
  source_id: string;
  excerpt: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
}

export interface KnowledgeEntityVersionRecord {
  id: string;
  entity_id: string;
  user_id: string;
  version_number: number;
  status: string;
  source: string;
  reason: string;
  actor_user_id: string | null;
  reviewed_by_user_id: string | null;
  agent_name: string;
  confidence: number;
  evidence_ids: string[];
  previous_content: Record<string, unknown>;
  new_content: Record<string, unknown>;
  created_at: string | null;
  reviewed_at: string | null;
  review_notes: string;
}

export interface KnowledgeEntityRecord {
  id: string;
  user_id: string;
  entity_type: string;
  canonical_name: string;
  content: Record<string, unknown>;
  source: string;
  confidence: number;
  evidence_ids: string[];
  version: number;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProfileEvolutionChangeItem {
  version: KnowledgeEntityVersionRecord;
  entity: KnowledgeEntityRecord | null;
  evidence: KnowledgeEvidenceRecord[];
}

export interface SourceStatus {
  id: string;
  source: string;
  connector_key: string;
  layer: "official_ats" | "company_careers" | "job_aggregator" | "discovery_agent";
  admin_status: "live" | "beta" | "planned" | "disabled";
  enabled: boolean;
  rollout_stage: "live" | "next" | "later";
  state: "healthy" | "lagging" | "degraded";
  cadence_minutes: number;
  new_jobs_today: number;
  last_run_minutes_ago: number | null;
  retries_today: number;
  last_successful_sync: string | null;
  jobs_collected: number;
  companies_enabled: number;
  catalog_company_count: number;
  average_runtime_seconds: number | null;
  last_failed_sync: string | null;
  next_scheduled_poll: string | null;
  lag_reason: string | null;
}

export interface ConnectorInventorySnapshot {
  active: number;
  stale: number;
  closed: number;
  expired: number;
  archived: number;
  deleted: number;
  collected_lifetime: number;
  new_today: number;
  estimated_storage_bytes: number | null;
  total_rows: number;
}

export interface AdminConnectorWorkspaceConnector extends SourceStatus {
  coverage_percent: number;
  reliability_percent: number;
  uptime_percent: number;
  quality_score: number;
  quality_grade: string;
  runs_14d: number;
  failed_runs_14d: number;
  failed_runs_today: number;
  companies_scanned_today: number;
  jobs_fetched_today: number;
  jobs_inserted_today: number;
  jobs_updated_today: number;
  jobs_closed_today: number;
  jobs_archived_today: number;
  jobs_ignored_today: number;
  alerts_sent_today: number;
  average_runtime_seconds_14d: number | null;
  active_jobs: number;
  stale_jobs: number;
  closed_jobs: number;
  expired_jobs: number;
  archived_jobs: number;
}

export interface AdminConnectorWorkspaceCompany {
  id: string;
  company: string;
  connector: string;
  connector_label: string;
  layer: SourceStatus["layer"];
  roadmap_status: SourceStatus["admin_status"];
  priority: number;
  tier: number;
  enabled: boolean;
  poll_interval_minutes: number;
  country: string;
  external_identifier: string;
  career_url: string;
  role_families: string[];
  ai_collections: string[];
  monitoring_state: string;
  monitoring_reason: string;
  monitoring_detail: string;
  validation_status: string;
  validation_reason: string;
  validation_message: string;
  validated_at: string | null;
  production_readiness_status: "ready" | "pending" | "blocked";
  production_readiness_summary: string;
  production_readiness_passed: number;
  production_readiness_total: number;
  production_readiness_blocked: number;
  production_readiness_pending: number;
  production_readiness_checks: Array<{
    key: string;
    label: string;
    status: "passed" | "pending_evidence" | "blocked" | "not_applicable";
    detail: string;
  }>;
  active_jobs: number;
  stale_jobs: number;
  closed_jobs: number;
  expired_jobs: number;
  archived_jobs: number;
  last_successful_sync: string | null;
  last_failed_sync: string | null;
  recent_failures: number;
}

export interface CoverageGapItem {
  company_id: string;
  company: string;
  connector: string;
  priority: number;
  tier: number;
  roadmap_status: SourceStatus["admin_status"];
  missing_capability: string;
  recommended_action: string;
  detail: string;
}

export interface RunHistoryItem {
  run_id: string;
  connector_key: string;
  connector_group: string;
  company_id: string | null;
  company_name: string | null;
  started_at: string | null;
  finished_at: string | null;
  run_status: string;
  companies_scanned: number;
  jobs_fetched: number;
  jobs_inserted: number;
  jobs_updated: number;
  jobs_closed: number;
  jobs_archived: number;
  jobs_ignored: number;
  jobs_matched: number;
  alerts_sent: number;
  alerts_failed: number;
  retries: number;
  trigger: string;
  error_message: string | null;
  duration_seconds: number | null;
}

export interface ConnectorTrendPoint {
  date: string;
  label: string;
  jobs_fetched: number;
  jobs_inserted: number;
  jobs_closed: number;
  jobs_archived: number;
  jobs_ignored: number;
  alerts_sent: number;
  failures: number;
  retries: number;
  average_runtime_seconds: number | null;
}

export interface AICollectionCoverage {
  name: string;
  total: number;
  covered: number;
  planned: number;
  missing: number;
}

export interface AICompanyCoverageSummary {
  total: number;
  covered: number;
  planned: number;
  missing: number;
  collections: AICollectionCoverage[];
}

export interface ConnectorCompanyJobRecord {
  job_id: string;
  title: string;
  location: string;
  apply_url: string;
  lifecycle_status: string;
  source_status: string;
  published_at: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  closed_at: string | null;
  archived_at: string | null;
}

export interface ConnectorCompanyErrorRecord {
  run_id: string;
  connector_key: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
}

export interface MaintenanceStatusSnapshot {
  running: boolean;
  cycle_state: "running" | "idle" | "stopped";
  interval_minutes: number;
  started_at: string | null;
  last_run_started_at: string | null;
  last_run: string | null;
  next_run: string | null;
  last_duration_seconds: number | null;
  archived_jobs: number;
  deleted_jobs: number;
  company_backfills: number;
  errors: number;
  last_error: string | null;
}

export interface AdminConnectorsWorkspace {
  generated_at: string;
  overview: {
    inventory: ConnectorInventorySnapshot;
    connectors_total: number;
    connectors_live: number;
    connectors_beta: number;
    connectors_planned: number;
    catalog_companies: number;
    monitored_companies: number;
    coverage_gaps: number;
    enabled_connectors: number;
    kpis: {
      jobs_active: number;
      companies_monitored: number;
      connectors_live: number;
      coverage_percent: number;
      jobs_added_today: number;
      alerts_sent_today: number;
      connector_failures_today: number;
      average_quality_score: number;
    };
    trends: ConnectorTrendPoint[];
    ai_coverage: AICompanyCoverageSummary;
  };
  connectors: AdminConnectorWorkspaceConnector[];
  companies: AdminConnectorWorkspaceCompany[];
  coverage_gaps: CoverageGapItem[];
  lifecycle: {
    settings: {
      stale_after_missed_syncs: number;
      closed_after_missed_syncs: number;
      archive_after_days: number;
      delete_after_days: number;
      cleanup_batch_size: number;
      maintenance_interval_minutes: number;
    };
    inventory: ConnectorInventorySnapshot;
    maintenance: MaintenanceStatusSnapshot | null;
  };
  database: {
    estimated_storage_bytes: number | null;
    jobs_rows: number;
    connector_runs_rows: number;
    alerts_rows: number;
    user_alerts_rows: number;
    job_matches_rows: number;
    saved_jobs_rows: number;
    active_inventory: number;
    stale_inventory: number;
    closed_inventory: number;
    expired_inventory: number;
    archived_inventory: number;
    collected_lifetime: number;
  };
  roadmap: Array<{
    connector_key: string;
    source: string;
    layer: SourceStatus["layer"];
    roadmap_status: SourceStatus["admin_status"];
    companies_enabled: number;
    catalog_company_count: number;
    coverage_percent: number;
    reliability_percent: number;
    quality_score: number;
    quality_grade: string;
  }>;
  run_history: RunHistoryItem[];
}

export interface AuditLogEntry {
  id: string;
  event_type: string;
  subject_type: string;
  subject_id: string;
  message: string;
  actor_user_id: string | null;
  actor_email: string | null;
  metadata: Record<string, unknown>;
  created_at: string | null;
}

export interface AlertEvent {
  id: string;
  channel: "telegram" | "email" | "slack" | "desktop";
  company: string;
  title: string;
  match_score: number;
  decision: MatchDecision;
  posted_minutes_ago: number;
  sent_minutes_ago: number;
  why: string[];
  recommended_resume: string;
  apply_url: string;
  gaps: string[];
  country_code: string | null;
  country_display: string;
  freshness_label: string;
  freshness_tone: "fresh" | "aging" | "stale";
  recommendation: string;
  recommendation_tone: "apply" | "review" | "skip";
  alert_status: string;
  notification_type: string;
  reason_code: string;
  failure_reason?: string | null;
}

export interface NotificationInsightBucket {
  key: string;
  count: number;
}

export interface NotificationInsightTotals {
  evaluated: number;
  sent: number;
  failed: number;
  suppressed: number;
  digest_pending: number;
  pending: number;
  missed_opportunities: number;
}

export interface NotificationInsights {
  totals: NotificationInsightTotals;
  reasons: NotificationInsightBucket[];
  types: NotificationInsightBucket[];
  missed_jobs: JobOpportunity[];
  failed_alerts: AlertEvent[];
}

export interface DashboardSummary {
  todays_jobs: number;
  apply_now_queue: number;
  review_queue: number;
  ignore_queue: number;
  already_seen: number;
  dismissed: number;
  skipped: number;
  alerts_sent: number;
  configured_companies: number;
  live_connectors: number;
  next_connectors: number;
  polling_interval_minutes: number;
  notification_sla_minutes: number;
  apply_now_threshold_score: number;
  review_threshold_score: number;
  active_inventory?: number;
  stale_inventory?: number;
  closed_inventory?: number;
  expired_inventory?: number;
  archived_inventory?: number;
  collected_lifetime?: number;
  new_today_inventory?: number;
  estimated_storage_bytes?: number | null;
}

export interface ProductInfo {
  name: string;
  phase: string;
  goal: string;
  focus: string;
  implementation_order?: string;
}

export interface AgentSnapshot {
  name: string;
  state: "healthy" | "lagging" | "degraded";
  current_connector: string;
  polling_interval_minutes: number;
  apply_now_threshold_score: number;
  review_threshold_score: number;
  last_run_minutes_ago: number;
  next_run_minutes: number;
  workflow: string[];
}

export interface ScoutSettings {
  primary_connector: string;
  apply_now_threshold_score: number;
  review_threshold_score: number;
  polling_interval_minutes: number;
  companies: CompanyPreference[];
  roles: RolePreference[];
  notifications: NotificationChannel[];
  role_families: RolePreference[];
  work_arrangements: RolePreference[];
  experience_levels: RolePreference[];
  excluded_keywords: string[];
  watchlists: Watchlist[];
  minimum_match_score: number;
  selected_country: string;
  alert_freshness_hours: number;
  dashboard_freshness_hours: number;
  resume_variants: string[];
  initial_alert_window_hours: number;
  initial_sync_openai_job_limit: number;
  initial_sync_max_alerts: number;
}

export interface SystemStatusComponent {
  key: string;
  label: string;
  status: "healthy" | "lagging" | "degraded";
  detail: string;
}

export interface SystemStatusStats {
  running: boolean;
  jobs_collected: number;
  jobs_matched: number;
  new_today: number;
  notifications_sent: number;
  errors: number;
  last_poll_at: string | null;
  next_poll_at: string | null;
}

export interface SystemStatusSnapshot {
  components: SystemStatusComponent[];
  stats: SystemStatusStats;
}

export interface SchedulerStatusSnapshot {
  running: boolean;
  cycle_state: "running" | "idle" | "stopped";
  polling_interval_minutes: number;
  started_at: string | null;
  last_run_started_at: string | null;
  last_run: string | null;
  next_run: string | null;
  last_duration_seconds: number | null;
  jobs_collected: number;
  jobs_inserted: number;
  jobs_matched: number;
  notifications_sent: number;
  errors: number;
  current_connector: string | null;
  last_error: string | null;
}

export interface DashboardSnapshot {
  generated_at: string;
  product: ProductInfo;
  agent: AgentSnapshot;
  summary: DashboardSummary;
  notification_preview: AlertEvent | null;
  jobs: JobOpportunity[];
  alerts: AlertEvent[];
  sources: SourceStatus[];
  settings: ScoutSettings;
  scheduler: SchedulerStatusSnapshot;
  system_status: SystemStatusSnapshot;
}

export interface SidebarItem {
  label: string;
  to: string;
  icon: string;
  badge?: string | number;
  featureFlag?: string;
}

export interface TableColumn {
  key: string;
  label: string;
  className?: string;
}

export interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  tone: ToastTone;
}

export interface UserPreferenceDraft {
  full_name: string;
  linkedin_url: string;
  portfolio_url: string;
  github_url: string;
  years_of_experience: number | null;
  visa_status: string;
  work_authorization: string;
  country: string;
  locations: string[];
  preferred_companies: string[];
  company_priorities: Record<string, CompanyPriorityLevel>;
  preferred_roles: string[];
  skills: string[];
  skill_priorities: SkillPriority[];
  work_arrangements: string[];
  experience_levels: string[];
  job_types: string[];
  company_sizes: string[];
  industries: string[];
  minimum_salary: number | null;
  desired_salary: number | null;
  travel_preference: string;
  remote_preference: string;
  freshness_hours: number;
  search_window_hours: number;
  minimum_match_score: number;
  notification_frequency: string;
  notification_rules: string[];
  excluded_keywords: string[];
  resume_strategy: string;
  preferred_resume_variants: string[];
}
