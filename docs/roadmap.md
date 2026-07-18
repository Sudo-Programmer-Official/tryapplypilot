# Phase 1 Roadmap

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
- posted time
- match score
- top reasons
- recommended resume
- direct apply link

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

Today that means the local env should decide which sources are active. Enabling Microsoft later should be a config update, not a new architecture pass.

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

## Version boundary after Phase 1

Treat the current Phase 1 scope as Version 1.0.

Do not start new major features until the current product is deployed and used in production long enough to validate the daily workflow.

The Version 1 boundary and post-launch roadmap are documented in [V2 planning notes](v2.md).

## Post-launch versions

Only after Phase 1 is stable and used in production:

1. `Version 1.5`: Resume Intelligence
2. `Version 2.0`: Application Copilot
3. `Version 3.0`: Networking Intelligence
4. `Version 4.0`: Career Intelligence Platform
