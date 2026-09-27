# AI Job Radar

As of July 21, 2026, this repo has completed the major product foundations through `Phase 5`, and `Phase 6` is now underway:

- `Phase 1`: Discovery Engine
- `Phase 2A`: Career Knowledge Platform
- `Phase 2B`: AI Profile Evolution
- `Phase 3`: Resume Intelligence
- `Phase 4`: Application Intelligence
- `Phase 5`: Recruiter Intelligence

Current active phase:

- `Phase 6`: Interview Intelligence

- `backend/`: FastAPI service modeling the `Market Scout Agent`, supported sources, user settings, job scoring, and alerts.
- `frontend/`: Vue 3 + TypeScript radar dashboard for configuration, live opportunities, source health, and notification previews.
- `docs/`: roadmap, architecture, and implementation notes for the active platform phases.
- [docs/codex-master-execution-prompt.md](docs/codex-master-execution-prompt.md): long-running implementation handoff prompt for Codex to continue the remaining phases with disciplined sequencing and verification.
- [docs/ui-guardrails.md](docs/ui-guardrails.md): page-level UI and performance guardrails for every new user or admin screen.
- [docs/connector-checklist.md](docs/connector-checklist.md): source-validation, runtime-wiring, and test checklist for every new connector.
- [ROADMAP.md](ROADMAP.md): multi-phase product roadmap from Job Discovery to AI Career Operating System.
- [EVALUATION.md](EVALUATION.md): shared evaluation, safety, and monitoring standard for every AI capability.

## Product progression

The product started with a narrow goal on purpose:

> Never miss a high-quality job again.

That foundation is now in place. The platform now spans workflow and intelligence layers:

- market understanding through discovery, matching, and notifications
- user understanding through the knowledge platform
- continuous user understanding improvement through AI profile evolution
- role-specific resume optimization through Resume Intelligence
- canonical application workflow through Application Intelligence
- recruiter-aware workflow enrichment through Recruiter Intelligence
- canonical interview workspaces, evidence-backed preparation, versioned question banks, and evidence-backed Story Library workflows through Interview Intelligence Sprints 1-4

The next major user-facing milestone inside `Interview Intelligence` is Mock Interview on top of the implemented workspace, preparation, question-bank, and story-library layers. The broader roadmap lives in [ROADMAP.md](ROADMAP.md).

## What is implemented

- Discovery Engine: connectors, scheduler, matching, notifications, admin operations, job lifecycle
- Career Knowledge Platform: canonical entities, evidence, versioning, merge logic, query SDK, timeline, health, audit, APIs
- AI Profile Evolution: completeness analysis, guided follow-up questions, fact extraction, staged updates, review workflow, frontend review surface
- Resume Intelligence: selection, gap analysis, evidence retrieval, structured changes, review workflow, versioning, PDF output
- Application Intelligence: package builder, state machine, answer artifacts, notes, tasks, timeline, submission workspace
- Recruiter Intelligence: canonical recruiter model, deterministic classification, conservative application matching, workflow intelligence, email integration platform
- Interview Intelligence Sprint 1: canonical interview workspace, dedicated interview APIs, linked application timeline events, preparation checklist state, upcoming interview workspace
- Interview Intelligence Sprint 2: versioned preparation plans, grounded focus-area detection, evidence retrieval from the knowledge platform, generated questions-to-ask, risk analysis, generate/regenerate APIs, and a preparation review workspace
- Interview Intelligence Sprint 3: versioned interview question banks, deterministic category coverage, resume-claim deep dives, evidence-backed follow-up prompts, question-set APIs, and a review workspace for preparation status and notes
- Interview Intelligence Sprint 4: canonical interview stories, deterministic story generation from approved evidence, gap prompts routed through Profile Evolution review, story quality scoring, version history, and Story Library APIs plus workspace UI
- User and admin dashboards for jobs, notifications, resumes, companies, preferences, and connector operations

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

Completed foundations:

- `Phase 1`: Discovery Engine
- `Phase 2A`: Career Knowledge Platform
- `Phase 2B`: AI Profile Evolution
- `Phase 3`: Resume Intelligence
- `Phase 4`: Application Intelligence

Current active phase:

- `Phase 6`: Interview Intelligence

Next major phase:

1. `Phase 7`: Career Intelligence
2. `Phase 8`: Career Agent

Recommended `Phase 6` sprint sequence:

1. Interview Workspace
   Implemented: canonical interview records, schedule metadata, checklist state, timeline history, dedicated APIs, and a user workspace.
2. Personalized Preparation
   Implemented: versioned preparation plans, focus-area detection, evidence retrieval, risk analysis, and a preparation review workspace.
3. Question Generation
   Implemented: versioned question banks, deterministic category coverage, grounded resume deep-dives, follow-up prompts, and question review APIs plus workspace UI.
4. Story Builder
   Implemented: canonical interview stories, deterministic evidence-backed story generation, profile-evolution gap prompts, quality scoring, version history, and Story Library UI.
5. Mock Interview
6. Feedback Engine

Parallel tracks:

1. `Market Intelligence`: hiring trends, emerging skills, recommendation freshness
2. `Platform Intelligence`: evaluation, quality metrics, latency and cost monitoring, explainability, safety guardrails

The full Version 1 scope freeze, exclusions, success metric, and dashboard readiness checklist are documented in [docs/v2.md](docs/v2.md).
New page-level UX and performance rules are documented in [docs/ui-guardrails.md](docs/ui-guardrails.md).
New connector delivery rules are documented in [docs/connector-checklist.md](docs/connector-checklist.md).
The first Application Intelligence slice is documented in [docs/application-intelligence-v1.md](docs/application-intelligence-v1.md).
