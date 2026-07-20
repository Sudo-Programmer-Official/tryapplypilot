# AI Job Radar

As of July 18, 2026, this repo is intentionally scoped to Phase 1 only: one agent that discovers new jobs, scores fit, and notifies quickly.

- `backend/`: FastAPI service modeling the `Market Scout Agent`, supported sources, user settings, job scoring, and alerts.
- `frontend/`: Vue 3 + TypeScript radar dashboard for configuration, live opportunities, source health, and notification previews.
- `docs/`: MVP roadmap and architecture notes for the Phase 1 build.
- [docs/ui-guardrails.md](docs/ui-guardrails.md): page-level UI and performance guardrails for every new user or admin screen.
- [docs/connector-checklist.md](docs/connector-checklist.md): source-validation, runtime-wiring, and test checklist for every new connector.
- [ROADMAP.md](ROADMAP.md): multi-phase product roadmap from Job Discovery to AI Career Operating System.

## MVP philosophy

The product goal is narrow on purpose:

> Never miss a high-quality job again.

Until this works reliably, nothing else matters. The system should:

1. Poll configured sources every 5 minutes.
2. Detect only newly posted jobs.
3. Normalize and deduplicate them.
4. Score them against the candidate profile.
5. Notify only when a role clears the configured threshold.

No resume tailoring, cover letters, CRM, or application tracking are part of the active build target. The Version 1 boundary and the Version 2 roadmap live in [docs/v2.md](docs/v2.md).

The broader product roadmap lives in [ROADMAP.md](ROADMAP.md). This repo is still executing the `Phase 1` slice of that plan.

## What is implemented

- One `Market Scout Agent` view with cadence, rollout focus, and last-run status
- A prototype source rollout model centered on `one real connector first`
- Company and role configuration models for the initial watchlist
- Job feed built around `discover -> score -> notify`
- A simple `Apply Now / Review / Ignore` priority queue
- Notification history and high-match alert preview
- A small dashboard focused on today's jobs, queue state, source health, and notification readiness

## Run locally

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### Deploy backend on Render

This repo is a monorepo, so the safest Render setup is:

- `Root Directory`: `backend`
- `Build Command`: `pip install -r requirements.txt`
- `Start Command`: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

If you leave `Root Directory` blank and deploy from the repo root, the committed top-level `requirements.txt` installs the backend package with `pip install -r requirements.txt`, so the same start command still works.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard expects the backend at `http://localhost:8000` by default. Override with `VITE_API_BASE_URL`.

### Deploy frontend on Vercel

This frontend uses Vue Router history mode, so Vercel must rewrite deep links back to `index.html`.

- `Root Directory`: `frontend`
- `Framework Preset`: `Vite`
- `Build Command`: `npm run build`
- `Output Directory`: `dist`
- `vercel.json`: committed in `frontend/` with an SPA rewrite for `/user/*`, `/admin/*`, and `/auth/*` refreshes

## Verify

Backend unit tests:

```bash
cd backend
python3 -m unittest discover -s tests
```

## Phase roadmap

The full company roadmap is in [ROADMAP.md](ROADMAP.md). The sprint-level execution plan for the active phase remains in [docs/roadmap.md](docs/roadmap.md).

`Phase 1` now starts with `Phase 1.0`: one real source end-to-end.

1. `Sprint 1`: PostgreSQL schema, `jobs`, `seen_jobs`, and `alerts` tables, connector framework, logging, and retry framework.
2. `Sprint 2`: one real collector, with `Greenhouse` as the first priority, then Lever, then Ashby.
3. `Sprint 3`: scheduler loop every 5 minutes to collect, normalize, persist, compare, and decide whether to notify.
4. `Sprint 4`: Telegram as the first production notification channel.
5. `Sprint 5`: LLM matching with structured JSON output and a simple priority queue:
   `APPLY_NOW (>= 90)`, `REVIEW (75-89)`, `IGNORE (< 75)`.

The system should not widen scope until these are true:

1. Scheduler runs every 5 minutes.
2. Jobs are collected from at least one real source.
3. Jobs are stored in PostgreSQL.
4. Duplicate jobs are prevented.
5. Only new jobs generate alerts.
6. Telegram notifications are received.
7. The dashboard reflects live data.
8. Collector retries work after transient failures.
9. `/health` reports connector status.

Only after that is reliable:

1. `Version 1.5`: Resume Intelligence
2. `Version 2.0`: Application Copilot
3. `Version 3.0`: Networking Intelligence
4. `Version 4.0`: Career Intelligence Platform

The full Version 1 scope freeze, exclusions, success metric, and dashboard readiness checklist are documented in [docs/v2.md](docs/v2.md).
New page-level UX and performance rules are documented in [docs/ui-guardrails.md](docs/ui-guardrails.md).
New connector delivery rules are documented in [docs/connector-checklist.md](docs/connector-checklist.md).
