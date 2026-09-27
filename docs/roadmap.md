# Phase 1 Roadmap

This document is the detailed execution plan for the active `Phase 1` build. For the full multi-phase product roadmap, see [../ROADMAP.md](../ROADMAP.md).

## Current goal

Run the entire job radar locally until the end-to-end flow is stable.

The active path is:

1. Greenhouse
2. Collector
3. PostgreSQL
4. Deduplication
5. AI match scoring
6. Telegram notification
7. Dashboard

Success means:

- localhost dashboard shows live jobs
- scheduler runs every 5 minutes
- new jobs are stored in PostgreSQL
- high-match jobs trigger Telegram notifications
- logs clearly show each pipeline step

## Current connector frontier

Implemented or active in the current Phase 1 code path:

- `Greenhouse`
- `Lever`
- `Ashby`
- `Workday`
- `SmartRecruiters`
- `iCIMS`
- `Microsoft Careers`
- `Google Careers`
- `Amazon Jobs`

Still planned:

- `Meta Careers`
- `Jobvite`
- `BambooHR`
- `Comeet`
- additional dedicated company collectors after the current set is stable

## Local development stack

Run locally:

- frontend on `localhost:5173`
- FastAPI backend
- PostgreSQL
- scheduler / poller
- Telegram bot
- OpenAI API

Redis, deployment, Docker, CI/CD, and cloud infrastructure are explicitly out of scope until the local path is reliable.

## Phase 1.0 implementation order

Do not start with multiple sources.

Start with one production-grade local loop:

1. Greenhouse
2. Collect jobs
3. Normalize
4. Deduplicate
5. Store in PostgreSQL
6. Score the job
7. Notify on Telegram
8. Show the state in the dashboard

Once this works reliably, every additional source becomes another connector instead of another architecture problem.

## Sprint plan

### Sprint 1

Infrastructure only:

- PostgreSQL schema
- `jobs`
- `seen_jobs`
- `alerts`
- `connector_cursors`
- `connector_runs`
- connector framework
- logging
- retry framework

### Sprint 2

First collector:

1. Greenhouse
2. Lever
3. Ashby

Requirements:

- normalization
- retry
- rate limiting
- duplicate detection
- local end-to-end verification

### Sprint 3

Scheduler:

Every 5 minutes:

1. Collect
2. Normalize
3. Save
4. Compare
5. Detect new jobs
6. Notify

### Sprint 4

Telegram notifications first:

- fast
- free
- reliable
- easy to configure
- easy to debug

Each notification should include:

- company
- role
- discovery context
- original posted time
- match score
- top reasons
- recommended resume
- direct apply link

## Notification freshness policy

TryApplyPilot now separates notification freshness from browsing freshness.

- `Only notify me about jobs posted within` answers: "How old can a job be before we notify the user?"
- `Dashboard search window` answers: "How far back should the workspace show jobs for browsing and review?"

Product rules:

- Telegram push notifications must always respect the user's notification freshness window.
- Recovery and rediscovery flows must not bypass that freshness setting.
- Older high-match jobs can still appear in the dashboard and review queue if they fall inside the user's dashboard search window.
- Telegram cards should describe both discovery time and original posting time when available.

### Sprint 5

LLM matching with structured JSON output:

```json
{
  "score": 94,
  "decision": "APPLY_NOW",
  "top_strengths": ["Distributed Systems", "Python", "Backend"],
  "gaps": ["Azure AI Search"],
  "recommended_resume": "backend_ai"
}
```

## Connector configuration rule

Connector enablement must come from configuration, not code changes.

The company catalog in PostgreSQL is now the source of truth for which companies are enabled, which connector they use, and how often they are polled. Environment variables should only provide infrastructure settings and safe bootstrap defaults, not per-company monitoring lists.

## Settings ownership rule

Admin settings control platform-wide behavior.

- scheduler cadence
- connector orchestration
- initial sync behavior
- shared maintenance windows
- runtime and infrastructure controls

User preferences control personal behavior.

- match thresholds
- notification freshness
- dashboard search window
- country, location, remote, salary, and visa filters
- resume and exclusion preferences

Admin may expose default user settings for new accounts, but existing users keep control of their own preferences after onboarding.

## Health dashboard requirement

The dashboard must expose a fast status readout for:

- backend
- database
- primary connector
- scheduler
- OpenAI
- Telegram
- jobs collected
- new today
- notifications sent
- last poll
- next poll

## Definition of done

Do not move to the next source until all of these are true:

- scheduler runs every 5 minutes
- jobs are collected from at least one real source
- jobs are stored in PostgreSQL
- duplicate jobs are prevented
- only new jobs generate alerts
- Telegram notification is received
- dashboard reflects live data
- collector retries after transient failures
- `/health` reports connector and scheduler status

## Tomorrow

Only after local stability:

1. Deploy a small staging environment
2. Put the frontend and backend behind HTTPS
3. Run the scheduler remotely
4. Keep PostgreSQL and environment variables managed there

`tryapplypilot.com` is the candidate staging target once the local loop is dependable.

## Current sequencing

`Phase 1`, `Phase 2A`, `Phase 2B`, `Phase 3`, `Phase 4`, and `Phase 5` Recruiter Intelligence are now in place.

Applications are now the canonical workflow object, and recruiter communication is attached to that workflow instead of creating a parallel system. Provider status, recruiter thread review, deterministic workflow suggestions, and versioned communication drafts now live in the same workspace.

`Phase 6: Interview Intelligence` is now active with the canonical `Interview Workspace`, `Personalized Preparation`, `Question Generation`, and `Story Builder` slices in place.

Recommended `Phase 6` sprint sequence:

1. Interview Workspace
   Implemented: canonical interview records, schedule metadata, preparation checklist state, timeline and audit history, dedicated APIs, upcoming interview queries, and a minimum user workspace.
2. Personalized Preparation
   Implemented: versioned preparation plans, deterministic focus-area detection, knowledge-platform evidence retrieval, resume-highlight selection from the submitted version metadata, generated questions-to-ask, risk analysis, and dedicated generate/update/regenerate APIs plus workspace UI.
3. Question Generation
   Implemented: versioned interview question sets, deterministic category coverage, grounded resume-claim deep dives, evidence-backed follow-up prompts, question-set APIs, and Question Bank review UI.
4. Story Builder
   Implemented: canonical interview stories, deterministic generation from approved evidence, question-to-story coverage mapping, profile-evolution follow-up prompts, story quality scoring, version history, and Story Library review APIs plus workspace UI.
5. Mock Interview
6. Feedback Engine

Interview preparation should be grounded in:

- submitted resume version
- job description
- application package
- recruiter communication
- company context
- approved evidence from the knowledge platform

Parallel roadmap tracks should continue without changing the primary phase order:

- `Market Intelligence`: public hiring signals, trend detection, emerging skills, recommendation freshness
- `Platform Intelligence`: evaluation, prompt versioning, quality metrics, cost and latency monitoring, explainability, and AI safety guardrails

## Post-launch versions

1. `Version 1.5`: Resume Intelligence
2. `Version 2.0`: Application Intelligence
3. `Version 3.0`: Recruiter Intelligence
4. `Version 4.0`: Interview Intelligence
5. `Version 5.0`: Career Intelligence
6. `Version 6.0` future direction: Career Agent

`Phase 8`: `Career Agent` is the long-range convergence point for the roadmap.

It should continuously combine:

- user intelligence
- market intelligence
- workflow intelligence
- interview intelligence

The result is an always-on system that can find roles, improve the profile, watch recruiter communication, track hiring trends, support interview preparation, and stay useful after the user lands a job.
