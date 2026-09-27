CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    company_id TEXT,
    connector_key TEXT NOT NULL,
    external_job_id TEXT NOT NULL,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT NOT NULL,
    remote_policy TEXT NOT NULL,
    apply_url TEXT NOT NULL,
    description_text TEXT NOT NULL,
    job_fingerprint TEXT NOT NULL UNIQUE,
    published_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    consecutive_missed_syncs INTEGER NOT NULL DEFAULT 0,
    lifecycle_status TEXT NOT NULL DEFAULT 'active' CHECK (lifecycle_status IN ('active', 'stale', 'closed', 'expired', 'archived', 'deleted')),
    source_status TEXT NOT NULL DEFAULT 'observed' CHECK (source_status IN ('observed', 'missing', 'confirmed_closed', 'expired', 'archived', 'deleted')),
    content_hash TEXT NOT NULL DEFAULT '',
    match_score INTEGER CHECK (match_score BETWEEN 0 AND 100),
    decision TEXT NOT NULL CHECK (decision IN ('APPLY_NOW', 'REVIEW', 'IGNORE')),
    recommended_resume TEXT NOT NULL,
    job_status TEXT NOT NULL CHECK (job_status IN ('new', 'seen', 'dismissed', 'skipped')),
    duplicate_source_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT jobs_connector_external_unique UNIQUE (connector_key, external_job_id)
);

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS company_id TEXT,
    ADD COLUMN IF NOT EXISTS last_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS consecutive_missed_syncs INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS lifecycle_status TEXT NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS source_status TEXT NOT NULL DEFAULT 'observed',
    ADD COLUMN IF NOT EXISTS content_hash TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS jobs_company_idx ON jobs (company);
CREATE INDEX IF NOT EXISTS jobs_decision_idx ON jobs (decision);
CREATE INDEX IF NOT EXISTS jobs_published_at_idx ON jobs (published_at DESC);
CREATE INDEX IF NOT EXISTS jobs_company_lifecycle_idx ON jobs (company_id, lifecycle_status, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS jobs_lifecycle_idx ON jobs (lifecycle_status, archived_at DESC, closed_at DESC);

CREATE TABLE IF NOT EXISTS seen_jobs (
    job_fingerprint TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs (job_id) ON DELETE CASCADE,
    connector_key TEXT NOT NULL,
    seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_cursor TEXT
);

CREATE INDEX IF NOT EXISTS seen_jobs_job_id_idx ON seen_jobs (job_id);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs (job_id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK (channel IN ('telegram', 'email', 'slack', 'desktop')),
    decision TEXT NOT NULL CHECK (decision IN ('APPLY_NOW', 'REVIEW', 'IGNORE')),
    alert_status TEXT NOT NULL CHECK (alert_status IN ('pending', 'sent', 'failed', 'suppressed')),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    failure_reason TEXT,
    CONSTRAINT alerts_job_channel_decision_unique UNIQUE (job_id, channel, decision)
);

CREATE INDEX IF NOT EXISTS alerts_created_at_idx ON alerts (created_at DESC);

CREATE TABLE IF NOT EXISTS companies (
    company_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    connector TEXT NOT NULL,
    external_identifier TEXT NOT NULL DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 999,
    tier INTEGER NOT NULL DEFAULT 3 CHECK (tier BETWEEN 1 AND 3),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    poll_interval_minutes INTEGER NOT NULL DEFAULT 5 CHECK (poll_interval_minutes >= 1),
    country TEXT NOT NULL DEFAULT 'US',
    career_url TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS companies_enabled_priority_idx ON companies (enabled, tier, priority);
CREATE INDEX IF NOT EXISTS companies_connector_idx ON companies (connector);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('super_admin', 'admin', 'user')),
    full_name TEXT NOT NULL DEFAULT '',
    telegram_chat_id TEXT,
    country TEXT NOT NULL DEFAULT 'US',
    profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS users_role_idx ON users (role);
CREATE INDEX IF NOT EXISTS users_created_at_idx ON users (created_at DESC);

CREATE TABLE IF NOT EXISTS resumes (
    resume_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    extracted_text TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS resumes_user_created_idx ON resumes (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS saved_jobs (
    saved_job_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs (job_id) ON DELETE CASCADE,
    saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT saved_jobs_user_job_unique UNIQUE (user_id, job_id)
);

CREATE INDEX IF NOT EXISTS saved_jobs_user_saved_idx ON saved_jobs (user_id, saved_at DESC);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    refresh_token_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    user_agent TEXT NOT NULL DEFAULT '',
    ip_address TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS refresh_tokens_user_idx ON refresh_tokens (user_id, expires_at DESC);

CREATE TABLE IF NOT EXISTS job_matches (
    match_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs (job_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    match_score INTEGER NOT NULL CHECK (match_score BETWEEN 0 AND 100),
    decision TEXT NOT NULL CHECK (decision IN ('APPLY_NOW', 'REVIEW', 'IGNORE')),
    recommended_resume TEXT NOT NULL,
    match_status TEXT NOT NULL CHECK (match_status IN ('new', 'seen', 'dismissed', 'skipped')),
    why JSONB NOT NULL DEFAULT '[]'::jsonb,
    gaps JSONB NOT NULL DEFAULT '[]'::jsonb,
    provider TEXT NOT NULL DEFAULT 'heuristic',
    country_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    alerted_at TIMESTAMPTZ,
    CONSTRAINT job_matches_user_job_unique UNIQUE (user_id, job_id)
);

CREATE INDEX IF NOT EXISTS job_matches_job_score_idx ON job_matches (job_id, match_score DESC, updated_at DESC);
CREATE INDEX IF NOT EXISTS job_matches_user_score_idx ON job_matches (user_id, match_score DESC, updated_at DESC);

CREATE TABLE IF NOT EXISTS user_alerts (
    user_alert_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs (job_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK (channel IN ('telegram', 'email', 'slack', 'desktop')),
    decision TEXT NOT NULL CHECK (decision IN ('APPLY_NOW', 'REVIEW', 'IGNORE')),
    alert_status TEXT NOT NULL CHECK (alert_status IN ('pending', 'sent', 'failed', 'suppressed')),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    failure_reason TEXT,
    CONSTRAINT user_alerts_user_job_channel_decision_unique UNIQUE (user_id, job_id, channel, decision)
);

CREATE INDEX IF NOT EXISTS user_alerts_created_at_idx ON user_alerts (created_at DESC);
CREATE INDEX IF NOT EXISTS user_alerts_user_created_at_idx ON user_alerts (user_id, created_at DESC);

ALTER TABLE job_matches
    ADD COLUMN IF NOT EXISTS notification_status TEXT,
    ADD COLUMN IF NOT EXISTS notification_reason TEXT,
    ADD COLUMN IF NOT EXISTS notification_type TEXT,
    ADD COLUMN IF NOT EXISTS notification_evaluated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS notification_attempts INTEGER NOT NULL DEFAULT 0;

ALTER TABLE user_alerts
    ADD COLUMN IF NOT EXISTS notification_type TEXT NOT NULL DEFAULT 'fresh_alert',
    ADD COLUMN IF NOT EXISTS reason_code TEXT NOT NULL DEFAULT 'sent',
    ADD COLUMN IF NOT EXISTS evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE TABLE IF NOT EXISTS company_requests (
    company_request_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    company_name TEXT NOT NULL,
    career_url TEXT NOT NULL DEFAULT '',
    connector_suggestion TEXT NOT NULL DEFAULT '',
    external_identifier_suggestion TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
    admin_notes TEXT NOT NULL DEFAULT '',
    reviewed_at TIMESTAMPTZ,
    reviewed_by_user_id TEXT REFERENCES users (user_id) ON DELETE SET NULL,
    approved_company_id TEXT REFERENCES companies (company_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS company_requests_status_created_idx ON company_requests (status, created_at DESC);
CREATE INDEX IF NOT EXISTS company_requests_user_created_idx ON company_requests (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS role_families (
    role_family_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS company_role_families (
    company_id TEXT NOT NULL REFERENCES companies (company_id) ON DELETE CASCADE,
    role_family_id TEXT NOT NULL REFERENCES role_families (role_family_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (company_id, role_family_id)
);

CREATE TABLE IF NOT EXISTS watchlists (
    watchlist_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS watchlist_terms (
    watchlist_term_id TEXT PRIMARY KEY,
    watchlist_id TEXT NOT NULL REFERENCES watchlists (watchlist_id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    company_name TEXT NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS watchlist_terms_watchlist_idx ON watchlist_terms (watchlist_id);

CREATE TABLE IF NOT EXISTS user_watchlists (
    user_watchlist_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT user_watchlists_user_name_unique UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS user_watchlists_user_updated_idx ON user_watchlists (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS user_watchlist_terms (
    user_watchlist_term_id TEXT PRIMARY KEY,
    user_watchlist_id TEXT NOT NULL REFERENCES user_watchlists (user_watchlist_id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    company_name TEXT NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS user_watchlist_terms_watchlist_idx ON user_watchlist_terms (user_watchlist_id);

CREATE TABLE IF NOT EXISTS user_preferences (
    preference_key TEXT PRIMARY KEY,
    preference_value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS connector_cursors (
    connector_key TEXT PRIMARY KEY,
    cursor_value TEXT,
    last_published_at TIMESTAMPTZ,
    last_successful_sync TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS connector_runs (
    run_id TEXT PRIMARY KEY,
    connector_key TEXT NOT NULL,
    company_id TEXT,
    companies_scanned INTEGER NOT NULL DEFAULT 1,
    trigger TEXT NOT NULL DEFAULT 'scheduled',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    run_status TEXT NOT NULL CHECK (run_status IN ('running', 'succeeded', 'failed')),
    jobs_fetched INTEGER NOT NULL DEFAULT 0,
    jobs_inserted INTEGER NOT NULL DEFAULT 0,
    jobs_updated INTEGER NOT NULL DEFAULT 0,
    jobs_closed INTEGER NOT NULL DEFAULT 0,
    jobs_archived INTEGER NOT NULL DEFAULT 0,
    jobs_ignored INTEGER NOT NULL DEFAULT 0,
    jobs_matched INTEGER NOT NULL DEFAULT 0,
    alerts_sent INTEGER NOT NULL DEFAULT 0,
    alerts_failed INTEGER NOT NULL DEFAULT 0,
    requests_made INTEGER NOT NULL DEFAULT 0,
    retries INTEGER NOT NULL DEFAULT 0,
    inventory_complete BOOLEAN NOT NULL DEFAULT TRUE,
    pages_scanned INTEGER NOT NULL DEFAULT 1,
    expected_pages INTEGER,
    partial_reason TEXT,
    cursor_before TEXT,
    cursor_after TEXT,
    error_message TEXT
);

ALTER TABLE connector_runs
    ADD COLUMN IF NOT EXISTS company_id TEXT,
    ADD COLUMN IF NOT EXISTS companies_scanned INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS trigger TEXT NOT NULL DEFAULT 'scheduled',
    ADD COLUMN IF NOT EXISTS jobs_updated INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS jobs_closed INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS jobs_archived INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS jobs_ignored INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS jobs_matched INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS alerts_sent INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS alerts_failed INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS requests_made INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS inventory_complete BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS pages_scanned INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS expected_pages INTEGER,
    ADD COLUMN IF NOT EXISTS partial_reason TEXT;

CREATE INDEX IF NOT EXISTS connector_runs_connector_started_idx ON connector_runs (connector_key, started_at DESC);
CREATE INDEX IF NOT EXISTS connector_runs_company_started_idx ON connector_runs (company_id, started_at DESC);

CREATE TABLE IF NOT EXISTS knowledge_entities (
    entity_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    search_text TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    current_version INTEGER NOT NULL DEFAULT 0,
    approval_status TEXT NOT NULL DEFAULT 'approved' CHECK (approval_status IN ('suggested', 'approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT knowledge_entities_user_type_name_unique UNIQUE (user_id, entity_type, canonical_name)
);

CREATE INDEX IF NOT EXISTS knowledge_entities_user_type_updated_idx ON knowledge_entities (user_id, entity_type, updated_at DESC);
CREATE INDEX IF NOT EXISTS knowledge_entities_user_status_updated_idx ON knowledge_entities (user_id, approval_status, updated_at DESC);
CREATE INDEX IF NOT EXISTS knowledge_entities_user_name_idx ON knowledge_entities (user_id, canonical_name);

CREATE TABLE IF NOT EXISTS knowledge_evidence (
    evidence_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('resume', 'profile', 'project', 'conversation', 'manual_entry')),
    source_id TEXT NOT NULL DEFAULT '',
    excerpt TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS knowledge_evidence_user_created_idx ON knowledge_evidence (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS knowledge_evidence_user_source_idx ON knowledge_evidence (user_id, source_type, created_at DESC);
CREATE INDEX IF NOT EXISTS knowledge_evidence_user_source_id_idx ON knowledge_evidence (user_id, source_id, created_at DESC);

CREATE TABLE IF NOT EXISTS knowledge_aliases (
    alias_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    alias_value TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    is_manual_override BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT knowledge_aliases_user_type_alias_unique UNIQUE (user_id, entity_type, normalized_alias)
);

CREATE INDEX IF NOT EXISTS knowledge_aliases_user_type_canonical_idx ON knowledge_aliases (user_id, entity_type, canonical_name);
CREATE INDEX IF NOT EXISTS knowledge_aliases_user_type_alias_idx ON knowledge_aliases (user_id, entity_type, normalized_alias);

CREATE TABLE IF NOT EXISTS knowledge_timeline_events (
    timeline_event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    entity_id TEXT REFERENCES knowledge_entities (entity_id) ON DELETE SET NULL,
    evidence_id TEXT REFERENCES knowledge_evidence (evidence_id) ON DELETE SET NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS knowledge_timeline_events_user_created_idx ON knowledge_timeline_events (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS knowledge_timeline_events_user_type_created_idx ON knowledge_timeline_events (user_id, event_type, created_at DESC);

CREATE TABLE IF NOT EXISTS knowledge_entity_versions (
    version_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES knowledge_entities (entity_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('suggested', 'approved', 'rejected')),
    source TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    actor_user_id TEXT REFERENCES users (user_id) ON DELETE SET NULL,
    reviewed_by_user_id TEXT REFERENCES users (user_id) ON DELETE SET NULL,
    agent_name TEXT NOT NULL DEFAULT '',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    previous_content JSONB NOT NULL DEFAULT '{}'::jsonb,
    new_content JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT NOT NULL DEFAULT '',
    CONSTRAINT knowledge_entity_versions_entity_version_unique UNIQUE (entity_id, version_number)
);

CREATE INDEX IF NOT EXISTS knowledge_entity_versions_entity_created_idx ON knowledge_entity_versions (entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS knowledge_entity_versions_user_created_idx ON knowledge_entity_versions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS knowledge_entity_versions_user_status_idx ON knowledge_entity_versions (user_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS profile_evolution_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    current_topic TEXT,
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT profile_evolution_sessions_user_unique UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS profile_evolution_sessions_user_updated_idx ON profile_evolution_sessions (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS profile_evolution_sessions_updated_idx ON profile_evolution_sessions (updated_at DESC);

CREATE TABLE IF NOT EXISTS resume_versions (
    resume_version_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs (job_id) ON DELETE CASCADE,
    source_resume_id TEXT REFERENCES resumes (resume_id) ON DELETE SET NULL,
    source_resume_name TEXT NOT NULL DEFAULT '',
    file_name TEXT NOT NULL,
    pdf_storage_path TEXT NOT NULL,
    text_storage_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'generated' CHECK (status IN ('generated', 'failed')),
    version_signature TEXT NOT NULL UNIQUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS resume_versions_user_created_idx ON resume_versions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS resume_versions_job_created_idx ON resume_versions (job_id, created_at DESC);
CREATE INDEX IF NOT EXISTS resume_versions_user_job_idx ON resume_versions (user_id, job_id, created_at DESC);

CREATE TABLE IF NOT EXISTS applications (
    application_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs (job_id) ON DELETE CASCADE,
    resume_version_id TEXT NOT NULL REFERENCES resume_versions (resume_version_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'ready_to_apply' CHECK (status IN ('ready_to_apply', 'applied', 'interviewing', 'offer', 'accepted', 'rejected', 'withdrawn')),
    package_signature TEXT NOT NULL,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    apply_url TEXT NOT NULL,
    match_score INTEGER CHECK (match_score BETWEEN 0 AND 100),
    decision TEXT NOT NULL DEFAULT '' CHECK (decision IN ('', 'APPLY_NOW', 'REVIEW', 'IGNORE')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_at TIMESTAMPTZ,
    CONSTRAINT applications_user_signature_unique UNIQUE (user_id, package_signature)
);

CREATE INDEX IF NOT EXISTS applications_user_status_updated_idx ON applications (user_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS applications_user_updated_idx ON applications (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS applications_job_created_idx ON applications (job_id, created_at DESC);

CREATE TABLE IF NOT EXISTS interviews (
    interview_id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications (application_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    interview_type TEXT NOT NULL CHECK (
        interview_type IN (
            'recruiter_screen',
            'hiring_manager',
            'technical',
            'coding',
            'system_design',
            'behavioral',
            'panel',
            'executive',
            'onsite',
            'final'
        )
    ),
    interview_round TEXT NOT NULL DEFAULT '',
    interview_status TEXT NOT NULL CHECK (interview_status IN ('planned', 'scheduled', 'completed', 'cancelled', 'rescheduled', 'no_show')),
    preparation_status TEXT NOT NULL CHECK (preparation_status IN ('not_started', 'in_progress', 'ready', 'completed')),
    scheduled_start_at TIMESTAMPTZ,
    scheduled_end_at TIMESTAMPTZ,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    meeting_url TEXT NOT NULL DEFAULT '',
    recruiter_name TEXT NOT NULL DEFAULT '',
    recruiter_email TEXT NOT NULL DEFAULT '',
    recruiter_contact_id TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    interviewers JSONB NOT NULL DEFAULT '[]'::jsonb,
    preparation_checklist JSONB NOT NULL DEFAULT '[]'::jsonb,
    timeline JSONB NOT NULL DEFAULT '[]'::jsonb,
    audit_history JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS interviews_user_scheduled_idx ON interviews (user_id, scheduled_start_at DESC);
CREATE INDEX IF NOT EXISTS interviews_user_application_idx ON interviews (user_id, application_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS interviews_user_status_idx ON interviews (user_id, interview_status, scheduled_start_at DESC);

CREATE TABLE IF NOT EXISTS interview_preparation_plans (
    preparation_plan_id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL REFERENCES interviews (interview_id) ON DELETE CASCADE,
    application_id TEXT NOT NULL REFERENCES applications (application_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    status TEXT NOT NULL DEFAULT 'generated' CHECK (status IN ('generated', 'updated')),
    strategy_version TEXT NOT NULL DEFAULT '',
    focus_labels JSONB NOT NULL DEFAULT '[]'::jsonb,
    overall_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    sections JSONB NOT NULL DEFAULT '[]'::jsonb,
    checklist JSONB NOT NULL DEFAULT '[]'::jsonb,
    risks JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT interview_preparation_plans_interview_version_unique UNIQUE (interview_id, version_number)
);

CREATE INDEX IF NOT EXISTS interview_preparation_plans_user_interview_idx
    ON interview_preparation_plans (user_id, interview_id, version_number DESC);
CREATE INDEX IF NOT EXISTS interview_preparation_plans_application_idx
    ON interview_preparation_plans (application_id, generated_at DESC);

CREATE TABLE IF NOT EXISTS interview_question_sets (
    question_set_id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL REFERENCES interviews (interview_id) ON DELETE CASCADE,
    application_id TEXT NOT NULL REFERENCES applications (application_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'superseded', 'archived')),
    title TEXT NOT NULL DEFAULT '',
    interview_type TEXT NOT NULL DEFAULT '',
    interview_round TEXT NOT NULL DEFAULT '',
    strategy_version TEXT NOT NULL DEFAULT '',
    source_preparation_plan_id TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    model_key TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    superseded_by_question_set_id TEXT REFERENCES interview_question_sets (question_set_id) ON DELETE SET NULL,
    CONSTRAINT interview_question_sets_interview_version_unique UNIQUE (interview_id, version_number)
);

CREATE INDEX IF NOT EXISTS interview_question_sets_user_interview_idx
    ON interview_question_sets (user_id, interview_id, version_number DESC);
CREATE INDEX IF NOT EXISTS interview_question_sets_status_idx
    ON interview_question_sets (user_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS interview_questions (
    question_id TEXT PRIMARY KEY,
    question_set_id TEXT NOT NULL REFERENCES interview_question_sets (question_set_id) ON DELETE CASCADE,
    interview_id TEXT NOT NULL REFERENCES interviews (interview_id) ON DELETE CASCADE,
    application_id TEXT NOT NULL REFERENCES applications (application_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    category TEXT NOT NULL CHECK (
        category IN (
            'recruiter_screen',
            'behavioral',
            'technical',
            'coding',
            'system_design',
            'architecture',
            'leadership',
            'product_judgment',
            'domain_specific',
            'company_specific',
            'resume_deep_dive',
            'project_deep_dive',
            'career_motivation',
            'candidate_questions'
        )
    ),
    question TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    evaluation_dimensions JSONB NOT NULL DEFAULT '[]'::jsonb,
    related_job_requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
    related_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    follow_up_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    difficulty TEXT NOT NULL DEFAULT 'intermediate' CHECK (difficulty IN ('introductory', 'intermediate', 'advanced', 'expert')),
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('must_prepare', 'high', 'medium', 'low')),
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    expected_answer_outline JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    sequence_order INTEGER NOT NULL DEFAULT 1 CHECK (sequence_order >= 1),
    preparation_status TEXT NOT NULL DEFAULT 'not_started' CHECK (preparation_status IN ('not_started', 'reviewing', 'prepared', 'needs_practice')),
    hidden BOOLEAN NOT NULL DEFAULT FALSE,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    user_notes JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS interview_questions_set_order_idx
    ON interview_questions (question_set_id, sequence_order ASC, created_at ASC);
CREATE INDEX IF NOT EXISTS interview_questions_user_status_idx
    ON interview_questions (user_id, preparation_status, updated_at DESC);

CREATE TABLE IF NOT EXISTS interview_stories (
    story_id TEXT PRIMARY KEY,
    story_group_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    application_id TEXT REFERENCES applications (application_id) ON DELETE CASCADE,
    interview_id TEXT REFERENCES interviews (interview_id) ON DELETE CASCADE,
    linked_application_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    linked_interview_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    title TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'project' CHECK (category IN ('project', 'leadership', 'architecture', 'technical', 'behavioral', 'resume_claim')),
    source_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    related_projects JSONB NOT NULL DEFAULT '[]'::jsonb,
    related_resume_version_id TEXT NOT NULL DEFAULT '',
    related_question_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    interview_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'review', 'approved', 'archived', 'superseded')),
    sections JSONB NOT NULL DEFAULT '[]'::jsonb,
    technical_decisions JSONB NOT NULL DEFAULT '[]'::jsonb,
    tradeoffs JSONB NOT NULL DEFAULT '[]'::jsonb,
    leadership_moments JSONB NOT NULL DEFAULT '[]'::jsonb,
    measurable_outcomes JSONB NOT NULL DEFAULT '[]'::jsonb,
    lessons_learned JSONB NOT NULL DEFAULT '[]'::jsonb,
    interviewer_follow_ups JSONB NOT NULL DEFAULT '[]'::jsonb,
    coverage JSONB NOT NULL DEFAULT '[]'::jsonb,
    quality JSONB NOT NULL DEFAULT '{}'::jsonb,
    missing_information_prompts JSONB NOT NULL DEFAULT '[]'::jsonb,
    superseded_by_story_id TEXT REFERENCES interview_stories (story_id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT interview_stories_group_version_unique UNIQUE (story_group_id, version_number)
);

CREATE INDEX IF NOT EXISTS interview_stories_user_interview_idx
    ON interview_stories (user_id, interview_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS interview_stories_group_status_idx
    ON interview_stories (story_group_id, status, version_number DESC);
CREATE INDEX IF NOT EXISTS interview_stories_application_idx
    ON interview_stories (user_id, application_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS recruiter_contacts (
    contact_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT recruiter_contacts_user_email_unique UNIQUE (user_id, email)
);

CREATE INDEX IF NOT EXISTS recruiter_contacts_user_updated_idx ON recruiter_contacts (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS recruiter_contacts_user_email_idx ON recruiter_contacts (user_id, email);

CREATE TABLE IF NOT EXISTS recruiter_threads (
    thread_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    application_id TEXT REFERENCES applications (application_id) ON DELETE SET NULL,
    contact_id TEXT NOT NULL REFERENCES recruiter_contacts (contact_id) ON DELETE CASCADE,
    subject TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    job_title TEXT NOT NULL DEFAULT '',
    last_message_id TEXT NOT NULL DEFAULT '',
    last_message_at TIMESTAMPTZ,
    message_count INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manual_import',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    conversation_status TEXT NOT NULL DEFAULT 'idle',
    pending_action TEXT NOT NULL DEFAULT '',
    response_overdue BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS recruiter_threads_user_updated_idx ON recruiter_threads (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS recruiter_threads_user_application_idx ON recruiter_threads (user_id, application_id, last_message_at DESC);

CREATE TABLE IF NOT EXISTS recruiter_messages (
    message_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES recruiter_threads (thread_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    application_id TEXT REFERENCES applications (application_id) ON DELETE SET NULL,
    contact_id TEXT NOT NULL REFERENCES recruiter_contacts (contact_id) ON DELETE CASCADE,
    sender TEXT NOT NULL DEFAULT '',
    recipients JSONB NOT NULL DEFAULT '[]'::jsonb,
    subject TEXT NOT NULL DEFAULT '',
    body_reference TEXT NOT NULL DEFAULT '',
    body_preview TEXT NOT NULL DEFAULT '',
    received_at TIMESTAMPTZ,
    message_type TEXT NOT NULL DEFAULT 'unknown' CHECK (
        message_type IN (
            'interview_invitation',
            'assessment',
            'offer',
            'rejection',
            'recruiter_outreach',
            'follow_up',
            'scheduling',
            'general',
            'unknown'
        )
    ),
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    source TEXT NOT NULL DEFAULT 'manual_import',
    timeline_id TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    job_title TEXT NOT NULL DEFAULT '',
    classification_reason TEXT NOT NULL DEFAULT '',
    match_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (match_confidence >= 0.0 AND match_confidence <= 1.0),
    match_reason TEXT NOT NULL DEFAULT '',
    suggested_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS recruiter_messages_user_received_idx ON recruiter_messages (user_id, received_at DESC);
CREATE INDEX IF NOT EXISTS recruiter_messages_user_application_idx ON recruiter_messages (user_id, application_id, received_at DESC);
CREATE INDEX IF NOT EXISTS recruiter_messages_thread_received_idx ON recruiter_messages (thread_id, received_at DESC);
CREATE INDEX IF NOT EXISTS recruiter_messages_type_received_idx ON recruiter_messages (user_id, message_type, received_at DESC);

CREATE TABLE IF NOT EXISTS communication_events (
    event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    application_id TEXT REFERENCES applications (application_id) ON DELETE SET NULL,
    thread_id TEXT NOT NULL REFERENCES recruiter_threads (thread_id) ON DELETE CASCADE,
    message_id TEXT NOT NULL REFERENCES recruiter_messages (message_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    occurred_at TIMESTAMPTZ,
    source TEXT NOT NULL DEFAULT 'manual_import',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS communication_events_user_occurred_idx ON communication_events (user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS communication_events_application_occurred_idx ON communication_events (application_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS recruiter_message_drafts (
    draft_id TEXT PRIMARY KEY,
    draft_group_id TEXT NOT NULL,
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    application_id TEXT REFERENCES applications (application_id) ON DELETE SET NULL,
    thread_id TEXT NOT NULL REFERENCES recruiter_threads (thread_id) ON DELETE CASCADE,
    source_message_id TEXT REFERENCES recruiter_messages (message_id) ON DELETE SET NULL,
    parent_draft_id TEXT REFERENCES recruiter_message_drafts (draft_id) ON DELETE SET NULL,
    draft_kind TEXT NOT NULL CHECK (draft_kind IN ('reply', 'follow_up', 'interview_confirmation', 'thank_you')),
    tone TEXT NOT NULL CHECK (tone IN ('professional', 'warm', 'direct', 'appreciative')),
    status TEXT NOT NULL DEFAULT 'generated' CHECK (status IN ('generated', 'edited', 'approved', 'rejected')),
    intended_recipient TEXT NOT NULL DEFAULT '',
    intended_recipient_email TEXT NOT NULL DEFAULT '',
    communication_objective TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    assumptions JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    explanation TEXT NOT NULL DEFAULT '',
    strategy_version TEXT NOT NULL DEFAULT '',
    model_key TEXT NOT NULL DEFAULT '',
    user_edited BOOLEAN NOT NULL DEFAULT FALSE,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT recruiter_message_drafts_group_version_unique UNIQUE (draft_group_id, version_number)
);

CREATE INDEX IF NOT EXISTS recruiter_message_drafts_user_updated_idx ON recruiter_message_drafts (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS recruiter_message_drafts_thread_updated_idx ON recruiter_message_drafts (thread_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS recruiter_message_drafts_application_updated_idx ON recruiter_message_drafts (application_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS email_provider_connections (
    connection_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    account_email TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'connected', 'disconnected', 'needs_reauth', 'error')),
    scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    disconnected_at TIMESTAMPTZ,
    last_sync_at TIMESTAMPTZ,
    sync_cursor TEXT NOT NULL DEFAULT '',
    token_reference TEXT NOT NULL DEFAULT '',
    token_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT email_provider_connections_user_provider_unique UNIQUE (user_id, provider)
);

CREATE INDEX IF NOT EXISTS email_provider_connections_user_connected_idx ON email_provider_connections (user_id, connected_at DESC);
CREATE INDEX IF NOT EXISTS email_provider_connections_user_status_idx ON email_provider_connections (user_id, status, connected_at DESC);

CREATE TABLE IF NOT EXISTS email_provider_token_secrets (
    token_reference TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    account_email TEXT NOT NULL DEFAULT '',
    access_token TEXT NOT NULL DEFAULT '',
    refresh_token TEXT NOT NULL DEFAULT '',
    expires_at TIMESTAMPTZ,
    scope TEXT NOT NULL DEFAULT '',
    token_type TEXT NOT NULL DEFAULT 'Bearer',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT email_provider_token_secrets_user_provider_unique UNIQUE (user_id, provider)
);

CREATE INDEX IF NOT EXISTS email_provider_token_secrets_user_provider_idx ON email_provider_token_secrets (user_id, provider);

CREATE TABLE IF NOT EXISTS email_sync_runs (
    sync_run_id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL REFERENCES email_provider_connections (connection_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    account_email TEXT NOT NULL,
    run_status TEXT NOT NULL CHECK (run_status IN ('running', 'completed', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    imported_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS email_sync_runs_user_started_idx ON email_sync_runs (user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS email_sync_runs_provider_started_idx ON email_sync_runs (provider, started_at DESC);

CREATE TABLE IF NOT EXISTS email_synced_messages (
    sync_message_id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL REFERENCES email_provider_connections (connection_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    account_email TEXT NOT NULL,
    provider_message_id TEXT NOT NULL,
    provider_thread_id TEXT NOT NULL,
    canonical_message_id TEXT REFERENCES recruiter_messages (message_id) ON DELETE SET NULL,
    canonical_thread_id TEXT REFERENCES recruiter_threads (thread_id) ON DELETE SET NULL,
    provider_history_id TEXT NOT NULL DEFAULT '',
    attachment_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT email_synced_messages_connection_message_unique UNIQUE (connection_id, provider_message_id)
);

CREATE INDEX IF NOT EXISTS email_synced_messages_connection_synced_idx ON email_synced_messages (connection_id, last_synced_at DESC);
CREATE INDEX IF NOT EXISTS email_synced_messages_user_canonical_idx ON email_synced_messages (user_id, canonical_message_id);

CREATE TABLE IF NOT EXISTS email_synced_threads (
    sync_thread_id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL REFERENCES email_provider_connections (connection_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    account_email TEXT NOT NULL,
    provider_thread_id TEXT NOT NULL,
    canonical_thread_id TEXT REFERENCES recruiter_threads (thread_id) ON DELETE SET NULL,
    subject TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT email_synced_threads_connection_thread_unique UNIQUE (connection_id, provider_thread_id)
);

CREATE INDEX IF NOT EXISTS email_synced_threads_connection_synced_idx ON email_synced_threads (connection_id, last_synced_at DESC);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_log_id TEXT PRIMARY KEY,
    actor_user_id TEXT REFERENCES users (user_id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS audit_logs_created_at_idx ON audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS audit_logs_event_created_at_idx ON audit_logs (event_type, created_at DESC);
