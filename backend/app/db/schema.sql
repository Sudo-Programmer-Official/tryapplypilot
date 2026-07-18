CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
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
    match_score INTEGER CHECK (match_score BETWEEN 0 AND 100),
    decision TEXT NOT NULL CHECK (decision IN ('APPLY_NOW', 'REVIEW', 'IGNORE')),
    recommended_resume TEXT NOT NULL,
    job_status TEXT NOT NULL CHECK (job_status IN ('new', 'seen', 'dismissed', 'skipped')),
    duplicate_source_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT jobs_connector_external_unique UNIQUE (connector_key, external_job_id)
);

CREATE INDEX IF NOT EXISTS jobs_company_idx ON jobs (company);
CREATE INDEX IF NOT EXISTS jobs_decision_idx ON jobs (decision);
CREATE INDEX IF NOT EXISTS jobs_published_at_idx ON jobs (published_at DESC);

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
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    run_status TEXT NOT NULL CHECK (run_status IN ('running', 'succeeded', 'failed')),
    jobs_fetched INTEGER NOT NULL DEFAULT 0,
    jobs_inserted INTEGER NOT NULL DEFAULT 0,
    retries INTEGER NOT NULL DEFAULT 0,
    cursor_before TEXT,
    cursor_after TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS connector_runs_connector_started_idx ON connector_runs (connector_key, started_at DESC);
