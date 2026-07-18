# Architecture Notes

## Active boundary

The repo now treats Phase 1 as the only build target:

> Never miss a high-quality job again.

That means the system is currently just one agent:

- Poll jobs every 5 minutes
- Normalize listings
- Remove duplicates
- Score fit
- Alert when the score clears the threshold

Everything beyond `discover -> score -> notify` is explicitly deferred.

## Implementation order

Phase 1 is not "all sources at once."

It is:

1. One live connector end-to-end
2. One live notification channel end-to-end
3. One reliable scheduler loop
4. Then expand connector coverage

The first preferred local path is:

1. Greenhouse
2. Normalize
3. Deduplicate
4. Store
5. Match
6. Telegram notify
7. Show in dashboard

Nothing should be deployed until this flow is stable on the development machine.

## Current architecture

### Market Scout Agent

The `Market Scout Agent` is the only agent in the system right now. Its loop is:

1. Collect from configured sources
2. Normalize into one canonical job shape
3. Deduplicate repeated listings
4. Score against the user profile
5. Send notifications for high-fit new roles
6. Sleep until the next polling cycle

### Source rollout strategy

The rollout order is intentionally incremental and config-driven:

1. Greenhouse
2. Lever
3. Ashby
4. Microsoft Careers
5. Google Careers
6. Workday
7. SmartRecruiters
8. company-specific APIs

Only Greenhouse should be treated as the first production connector target.
Connector enablement must come from configuration so that a new source can be switched on without refactoring the scheduler.

### Stored data

The MVP data model is intentionally small:

- `jobs`
- `seen_jobs`
- `alerts`
- `user_settings`

The first real implementation sprint should add PostgreSQL-backed persistence for these tables before expanding source coverage.

### Priority queue

The MVP should reduce notification fatigue with a simple queue:

- `APPLY_NOW`: match >= 90
- `REVIEW`: match 75-89
- `IGNORE`: match < 75

Only `APPLY_NOW` should interrupt by default. The dashboard should still retain `REVIEW` and `IGNORE` items for later inspection.

### Dashboard purpose

The dashboard is not meant to be a full career workspace yet. Its job is to answer:

- What new opportunities appeared today?
- Which ones are high matches?
- Which jobs were already seen, dismissed, or skipped?
- Is the polling engine healthy?
- Which companies, roles, sources, and notification channels are active?

It also needs a dedicated health surface for:

- backend
- database
- scheduler
- primary connector
- OpenAI
- Telegram
- last poll
- next poll

## Current API shape

- `GET /health`
- `GET /api/dashboard`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/settings`
- `GET /api/alerts`
- `GET /api/sources`

`/health` should evolve from a basic liveness check into a connector-and-scheduler status surface. `/api/dashboard` remains the primary frontend contract for the Phase 1 radar workflow.

## Deliberately deferred

These are not part of the active milestone:

- Resume generation
- Cover letters
- ATS scoring
- Application tracking
- Recruiter CRM
- Interview preparation
- Career analytics
