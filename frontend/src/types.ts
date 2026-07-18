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

export interface SourceStatus {
  id: string;
  source: string;
  enabled: boolean;
  rollout_stage: "live" | "next" | "later";
  state: "healthy" | "lagging" | "degraded";
  cadence_minutes: number;
  new_jobs_today: number;
  last_run_minutes_ago: number | null;
  retries_today: number;
  last_successful_sync: string | null;
  jobs_collected: number;
  average_runtime_seconds: number | null;
  last_failed_sync: string | null;
  next_scheduled_poll: string | null;
  lag_reason: string | null;
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
  minimum_match_score: number;
  notification_frequency: string;
  notification_rules: string[];
  excluded_keywords: string[];
  resume_strategy: string;
  preferred_resume_variants: string[];
}
