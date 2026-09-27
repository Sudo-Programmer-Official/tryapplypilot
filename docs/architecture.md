# Architecture Notes

## Current platform boundary

The platform is no longer `Phase 1` only.

As of July 21, 2026, the implemented foundations are:

1. `Phase 1`: Discovery Engine
2. `Phase 2A`: Career Knowledge Platform
3. `Phase 2B`: AI Profile Evolution
4. `Phase 3`: Resume Intelligence
5. `Phase 4`: Application Intelligence
6. `Phase 5`: Recruiter Intelligence

The current active phase is now:

7. `Phase 6`: Interview Intelligence

That means the system now understands:

- the market through discovery, matching, notifications, and job lifecycle
- the user through canonical profile entities, evidence, and versioning
- how to improve user understanding continuously through guided profile evolution
- how to generate evidence-backed resume versions for specific roles
- how to manage the canonical application workflow
- how recruiter communication should enrich applications instead of creating a parallel tracker
- how provider sync, workflow suggestions, and versioned recruiter drafts fit into one reviewable workspace
- how canonical interview workspaces attach preparation state, schedule details, and timeline history directly to applications
- how versioned interview preparation plans compose approved resume context, recruiter communication, application state, and knowledge-platform evidence into one grounded review surface
- how versioned interview question banks now layer deterministic category coverage, resume-claim deep dives, and evidence-backed follow-up prompts on top of the preparation plan
- how evidence-backed interview stories now organize approved knowledge, resume claims, question coverage, gap prompts, and version history into a reusable Story Library
The next major architecture target inside `Phase 6` is now mock interviews and feedback on top of the implemented workspace, preparation, question-bank, and story-library layers.

## Active implementation order

The remaining roadmap should build by composing these foundations, not by inventing new storage or workflow layers.

Recommended sequence:

1. Continue `Phase 6`: Interview Intelligence
2. Build `Phase 7`: Career Intelligence
3. Converge in `Phase 8`: Career Agent

Parallel intelligence tracks:

- `Market Intelligence` should keep recommendation freshness and hiring-trend awareness current without blocking the primary workflow phases.
- `Platform Intelligence` should measure quality, safety, cost, latency, and explainability across every AI capability.

## What changed

The hardest platform work is already done:

- discovery infrastructure exists
- knowledge infrastructure exists
- evidence-backed profile enrichment exists
- resume orchestration exists
- application workflow infrastructure exists
- recruiter workflow enrichment exists
- recruiter workspace operations, provider sync visibility, and grounded communication drafts exist

Everything after this point should mainly orchestrate existing capabilities:

- select context
- retrieve evidence
- compare against goals or requirements
- stage proposed changes
- keep the human in the approval loop

## Architecture target after `Phase 5`

`Interview Intelligence` should now build directly on top of the completed resume, application, and recruiter workflow layers.

The first slice is the `Interview Workspace`:

1. Create a canonical interview object attached to an application
2. Track scheduling details, round, interview type, interviewer, meeting link, and timezone
3. Keep notes, preparation checklist items, and agenda in one workspace
4. Make the application timeline the canonical chronological record
5. Preserve auditability without turning interview prep into a generic chatbot

This slice is now implemented as a canonical Interview domain with:

- application-linked interview records
- dedicated interview APIs
- interview timeline and audit history
- preparation checklist state
- upcoming interview queries
- a dedicated user workspace for creating and updating interview records

The second slice, `Personalized Preparation`, is now implemented on top of that workspace with:

- versioned interview preparation plans linked to canonical interview records
- deterministic focus-area detection from job context, interview type, round, and recruiter communication
- knowledge-platform evidence retrieval for projects, leadership examples, achievements, cloud depth, and recent experience
- evidence-backed resume highlights sourced from the submitted resume version metadata rather than rereading raw files
- generated questions-to-ask, checklist tasks, and risk areas that point to evidence gaps instead of invented weaknesses
- dedicated preparation APIs for generate, fetch, update, and regenerate flows
- a user workspace that renders preparation sections, trackable checklist progress, and risk review directly beside the interview record

The architecture rule is:

- interview preparation must be grounded in approved resume versions, application context, recruiter communication, company context, and verified user evidence

The third slice, `Question Generation`, is now implemented on top of the preparation layer with:

- versioned interview question sets tied to canonical interview records
- deterministic category coverage based on interview type instead of free-form LLM selection
- resume deep-dive prompts derived from the submitted resume version's approved claims
- question evidence references that point back to job requirements, preparation-plan evidence, and approved knowledge-platform examples
- follow-up probes and expected-answer outlines that stay reusable for later mock interview workflows
- question-set, current-version, regenerate, question-update, and note APIs
- a workspace review surface for filtering, reprioritizing, marking prepared, and storing notes without rewriting source evidence

The fourth slice, `Story Builder`, is now implemented on top of the question layer with:

- canonical interview stories tied to interviews, applications, question coverage, and resume versions
- deterministic story generation from approved knowledge-platform evidence and submitted resume claims instead of free-form story invention
- structured story sections for situation, task, action, result, and reflection, with linked evidence on each story
- deterministic story quality scoring, gap detection, and follow-up prompts that route missing details back through Profile Evolution review
- story versioning, approval, archive, and regenerate flows that never overwrite approved stories
- Story Library APIs and a workspace review surface for editing, approving, archiving, and reviewing version history

## Current architecture

### Discovery Engine

The `Discovery Engine` remains the market-ingestion layer. Its loop is:

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

### Knowledge Platform

The `Career Knowledge Platform` is now the canonical user model.

It owns:

- canonical entities
- evidence
- version history
- merge logic
- alias resolution
- health checks
- audit and timeline
- query APIs and SDK

No future AI agent should parse resumes or profile text directly if the knowledge platform can answer the question.

### Profile Evolution

`AI Profile Evolution` is the first intelligence layer built on top of the knowledge platform.

Its loop is:

1. Measure completeness
2. Identify the highest-value knowledge gap
3. Ask one focused question
4. Extract structured facts
5. Create evidence
6. Stage updates
7. Require user review
8. Update canonical knowledge

Design rule:

- this is a guided interview, not a chatbot

### Priority queue

The MVP should reduce notification fatigue with a simple queue:

- `APPLY_NOW`: match >= 90
- `REVIEW`: match 75-89
- `IGNORE`: match < 75

Only `APPLY_NOW` should interrupt by default. The dashboard should still retain `REVIEW` and `IGNORE` items for later inspection.

### Product surfaces

The dashboard and user workspace are no longer just operational wrappers around polling.

They now need to support:

- What new opportunities appeared today?
- Which ones are high matches?
- What does the system know about the user?
- Which profile gaps still block stronger recommendations?
- What evidence-backed updates are waiting for review?
- Which companies, roles, sources, and notification channels are active?
- Is the discovery and knowledge infrastructure healthy?

## Current API shape

- `GET /health`
- `GET /api/dashboard`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/settings`
- `GET /api/alerts`
- `GET /api/sources`

`/health` should evolve from a basic liveness check into a connector-and-scheduler status surface. `/api/dashboard` remains the primary frontend contract for the Phase 1 radar workflow.

## Next architecture target

The next major user-facing AI capability is `Phase 6`: `Interview Intelligence`.

It should be built as orchestration on top of what already exists:

1. Resume version submitted
2. Job description and role requirements
3. Knowledge platform evidence
4. Application package
5. Recruiter communication and timeline
6. Company context
7. Verified project and achievement evidence

Recommended implementation sequence:

1. Sprint 1: Interview Workspace
   Implemented: canonical interview records, schedule metadata, checklist state, timeline history, dedicated APIs, and a user workspace.
2. Sprint 2: Personalized Preparation
   Implemented: versioned preparation plans, focus-area detection, evidence retrieval, risk analysis, generate/regenerate APIs, and a preparation review surface.
3. Sprint 3: Question Generation
   Implemented: versioned question banks, deterministic coverage, resume deep-dives, follow-up prompts, review APIs, and Question Bank workspace UI.
4. Sprint 4: Story Builder
   Implemented: canonical interview stories, deterministic story generation from approved evidence, gap prompts routed through Profile Evolution, story quality scoring, version history, review APIs, and Story Library workspace UI.
5. Sprint 5: Mock Interview
6. Sprint 6: Feedback Engine

Interview output should never invent experience. Every suggested story, question focus, and preparation prompt should point back to stored evidence or explicit application context.

## Cross-cutting Platform Intelligence

`Platform Intelligence` should run alongside product phases, not after them.

It should own:

- evaluation framework
- prompt versioning
- recommendation quality metrics
- cost and latency monitoring
- A/B testing and experimentation discipline
- explainability standards
- AI safety guardrails

This is the control layer that keeps `Resume Intelligence`, `Recruiter Intelligence`, and `Interview Intelligence` improving in measurable ways instead of drifting into opaque behavior.

## Future convergence target

`Phase 8`: `Career Agent` should be treated as the synthesis layer, not as a new standalone foundation.

It should continuously coordinate:

- job discovery and matching
- profile and resume improvement
- recruiter communication awareness
- market trend awareness
- interview preparation
- long-term career planning

The architecture rule is:

1. user intelligence remains grounded in the knowledge platform, evidence, and approved profile or resume updates
2. market intelligence remains grounded in discovery signals and hiring-trend learning
3. workflow intelligence remains grounded in applications, recruiter timelines, and interview state
4. interview intelligence remains grounded in submitted resume context, recruiter communication, and verified stories
5. platform intelligence measures quality, safety, and cost across the stack
6. the career agent composes those systems through one decision layer instead of bypassing them

Product rule:

- keep `AI recommends, human decides` even when the future agent becomes proactive
