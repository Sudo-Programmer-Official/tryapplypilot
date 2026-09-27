# Codex Master Execution Prompt

Use this prompt when you want Codex to continue the remaining product phases with minimal supervision while preserving disciplined sequencing, verification, and documentation.

Status baseline for this prompt: July 21, 2026.

Paste the following into Codex:

```text
TryApplyPilot — Complete Remaining Product Phases

Mission

Continue implementing the remaining TryApplyPilot roadmap sequentially without waiting for approval after every small sprint.

The goal is to complete the functional backend and minimum end-to-end product flows for:

1. Finish Phase 5 — Recruiter Intelligence
2. Phase 6 — Interview Intelligence
3. Phase 7 — Career Intelligence
4. Phase 8 — Career Agent foundation
5. Parallel Market Intelligence foundation
6. Parallel Platform Intelligence foundation

After these phases are functionally complete, we will perform a separate product-hardening cycle focused on:

- full-system testing
- bug fixing
- frontend consistency
- UI/UX polish
- accessibility
- performance
- production readiness

Do not spend significant time redesigning or polishing existing UI during this execution cycle. Build only the minimum usable interfaces required to validate complete workflows.

Operating Rules

1. Work continuously

Proceed from sprint to sprint without asking for confirmation after each successful slice.

After finishing a sprint:

1. run relevant tests
2. review the implementation
3. update documentation and roadmap status
4. identify the next dependency
5. continue into the next sprint

Only stop when:

- a decision could create destructive or irreversible behavior
- credentials or provider configuration are required
- an external service cannot be safely mocked
- a major architecture conflict is discovered
- tests expose a foundational regression that must be resolved first
- the remaining work requires product clarification that cannot reasonably be inferred

For ordinary implementation choices, follow existing repository patterns and continue.

2. Preserve the architecture

The system already has canonical domain layers:

Discovery Engine
        ↓
Knowledge Platform
        ↓
Profile Evolution
        ↓
Resume Intelligence
        ↓
Application Intelligence
        ↓
Recruiter Intelligence
        ↓
Interview Intelligence
        ↓
Career Intelligence
        ↓
Career Agent

Do not build parallel stores or duplicate workflow models.

Each new phase must build on the existing canonical services.

Canonical ownership

- Knowledge Platform owns user career facts and evidence.
- Resume Intelligence owns resume recommendations and versions.
- Application Intelligence owns applications, tasks, artifacts, statuses, and timelines.
- Recruiter Intelligence owns communication interpretation.
- Interview Intelligence owns interview preparation and performance.
- Career Intelligence owns long-term career planning.
- Career Agent coordinates approved capabilities across these domains.

3. Human control remains mandatory

The product principle remains:

AI recommends, human decides.

Do not implement:

- automatic job submission
- automatic email sending
- automatic application-status mutation from inferred events
- silent canonical knowledge updates
- fabricated achievements
- invented interview stories
- unsupported resume claims
- autonomous destructive actions

All high-impact changes must be:

- explainable
- evidence-backed
- reviewable
- auditable
- reversible where practical

4. Keep provider integrations isolated

External providers must use adapter interfaces.

Examples:

EmailProvider
CalendarProvider
JobProvider
LLMProvider
MarketSignalProvider

Domain services must not call Gmail, Outlook, Google Calendar, OpenAI, or another external provider directly.

Use mocks or import-first implementations when credentials are unavailable.

Reuse the existing provider packages already present in the repository where possible. Do not refactor stable code purely to match a suggested folder name from planning notes.

5. Backend before polished frontend

For each capability:

1. domain models
2. service layer
3. persistence
4. API contract
5. tests
6. minimal frontend integration
7. documentation

Do not build large UI surfaces before the service and API contracts are stable.

Current Status

Treat the repository state and documentation as the source of truth.

Current architectural status:

- Phase 1 — Discovery Engine: complete foundation
- Phase 2A — Career Knowledge Platform: complete foundation
- Phase 2B — Profile Evolution: complete foundation
- Phase 3 — Resume Intelligence: complete functional foundation
- Phase 4 — Application Intelligence: complete functional foundation
- Phase 5 — Recruiter Intelligence: active frontier
- Phase 6 — Interview Intelligence: next major target
- Phase 7 — Career Intelligence: later sequential phase
- Phase 8 — Career Agent: long-range coordination layer
- Market Intelligence: parallel track
- Platform Intelligence: parallel track

Before changing code, inspect the actual repository and confirm what is already implemented. Do not recreate completed work.

If a sprint is partially implemented, finish the remaining acceptance criteria before moving to the next sprint.

Phase 5 — Recruiter Intelligence

Complete the remaining Recruiter Intelligence work.

Sprint 3 — Email Integration Platform

Inspect the existing email integration layer first. If Sprint 3 is already functionally complete, move directly to Sprint 4. If it is only partially complete, close the remaining acceptance criteria without rebuilding the existing provider-neutral foundation.

Required capabilities:

- Gmail-ready provider interface
- Outlook-ready provider interface
- mock/import provider
- provider connection records
- secure token-reference model
- incremental synchronization
- retry-safe imports
- deduplication by immutable provider message ID
- canonical thread mapping
- attachment metadata references
- synchronization history
- synchronization health
- disconnect and reconnect behavior

Keep or extend the current repository package structure if it already satisfies these requirements.

Minimum APIs

- GET    /api/auth/me/recruiter/providers
- GET    /api/auth/me/recruiter/providers/status
- POST   /api/auth/me/recruiter/providers/{provider}/connect when useful, while preserving current provider routes if they already exist
- DELETE /api/auth/me/recruiter/providers/{provider} when useful, while preserving current provider routes if they already exist
- POST   /api/auth/me/recruiter/sync
- GET    /api/auth/me/recruiter/sync/history

Sprint 4 — Communication Assistant

Build user-reviewed communication assistance.

Capabilities:

- thread summaries
- message summaries
- reply-draft generation interface
- follow-up draft generation
- interview confirmation draft
- thank-you draft
- recruiter relationship context
- tone selection
- grounding evidence
- confidence and explanation
- draft versioning
- user edits
- approval status

Do not send emails.

Drafts should be portable later to Gmail or Outlook sending integrations.

Each generated draft should identify:

- the source thread
- intended recipient
- communication objective
- evidence used
- assumptions
- confidence
- generated timestamp
- model or strategy version

Sprint 5 — Recruiter Intelligence Workspace

Build the minimum usable frontend experience.

Include:

- recruiter inbox or communication queue
- linked application
- conversation state
- health
- suggestions
- latest recruiter activity
- communication timeline
- recruiter profile
- generated draft review
- provider sync status

Reuse existing design-system components.

Do not heavily polish the UI yet.

Phase 5 exit criteria

Phase 5 is functionally complete when:

- provider-neutral ingestion exists
- incremental and idempotent synchronization is supported
- recruiter messages link conservatively to applications
- conversation state and health are visible
- communication suggestions are available
- user-reviewed reply drafts can be generated
- no messages are sent automatically
- applications remain the canonical workflow record
- core backend and route tests pass
- the minimum frontend flow is usable

Phase 6 — Interview Intelligence

Build Phase 6 sequentially.

Sprint 1 — Interview Workspace

Create a canonical interview entity connected to an application.

Support:

- interview type
- round
- status
- start and end time
- timezone
- location or meeting link
- interviewer contacts
- recruiter contact
- notes
- agenda
- preparation checklist
- timeline
- source
- confidence
- audit history

Suggested statuses:

planned
scheduled
completed
cancelled
rescheduled
no_show

Suggested interview types:

recruiter_screen
hiring_manager
technical
coding
system_design
behavioral
panel
executive
onsite
final
other

Do not duplicate application records.

Sprint 2 — Personalized Preparation

Generate evidence-backed preparation using:

- job description
- submitted resume version
- Knowledge Platform
- recruiter communication
- application artifacts
- company context
- interview round
- interviewer context when known

Preparation should include:

- role summary
- likely focus areas
- required skills
- resume areas likely to be challenged
- project evidence
- leadership examples
- architecture examples
- questions to ask
- risks or gaps
- preparation tasks

Every recommendation must include evidence and explanation.

Sprint 3 — Question Generation

Generate structured interview-question sets.

Categories:

- recruiter screening
- behavioral
- technical
- coding
- system design
- leadership
- architecture
- product judgment
- domain-specific
- company-specific

Each question should include:

- reason it may be asked
- related requirement
- difficulty
- expected answer dimensions
- relevant user evidence
- follow-up questions
- confidence

Avoid generic question lists when contextual data exists.

Sprint 4 — Story Builder

Build evidence-grounded interview stories.

Support:

Situation
Task
Action
Result
Reflection

Stories must come from approved Knowledge Platform facts.

Capabilities:

- story candidate retrieval
- evidence selection
- missing-detail detection
- follow-up questions
- structured story generation
- user review
- versioning
- reuse across interviews
- job-specific framing without changing facts

Never invent metrics or responsibilities.

Sprint 5 — Mock Interview Engine

Build a provider-neutral mock interview engine.

Support:

- interview configuration
- question queue
- follow-up questions
- typed answers
- resumable sessions
- session transcript
- answer timing
- evidence usage
- deterministic session state
- configurable interviewer style

Keep voice out of scope unless the repository already has a reusable voice abstraction.

Start with text.

Sprint 6 — Feedback Engine

Evaluate interview answers using explicit rubrics.

Dimensions:

- relevance
- clarity
- structure
- evidence
- technical depth
- business impact
- conciseness
- confidence
- completeness
- unsupported claims

Feedback should include:

- score
- strengths
- missing information
- problematic claims
- improved outline
- suggested retry
- evidence references

Store progress across sessions.

Sprint 7 — Interview Workspace UI

Build the minimum end-to-end frontend:

- upcoming interviews
- interview detail
- preparation plan
- question bank
- story library
- mock interview
- feedback
- tasks
- timeline

Reuse existing application and profile patterns.

Phase 6 exit criteria

Phase 6 is complete when:

- interviews are canonical application-linked objects
- preparation is personalized and evidence-backed
- questions are context-specific
- stories use approved career facts
- mock interviews are resumable
- feedback is rubric-based
- progress can be tracked
- the minimum frontend workflow is usable
- tests cover services, APIs, state transitions, and user scoping

Phase 7 — Career Intelligence

Build a long-term career-planning layer.

Do not turn this into generic motivational coaching.

Sprint 1 — Career Goals

Create structured career goals:

- target roles
- industries
- compensation
- locations
- work arrangement
- leadership goals
- skill goals
- timeline
- priority
- status
- constraints

Goals should be versioned and user-approved.

Sprint 2 — Skill Gap Intelligence

Compare:

Current Knowledge
        +
Target Role Requirements
        +
Market Signals
        ↓
Skill Gap Analysis

Produce:

- existing strengths
- missing skills
- weak evidence
- outdated skills
- recommended priorities
- estimated impact
- confidence
- evidence

Separate actual missing skill from missing proof.

Sprint 3 — Learning Plans

Build structured learning plans tied to goals.

Support:

- milestones
- learning tasks
- projects
- practice
- evidence targets
- due dates
- progress
- completion
- review cycles

Do not require external course integrations for V1.

Sprint 4 — Career Progress

Track:

- profile completeness
- resume strength
- job-match trends
- application outcomes
- recruiter response rate
- interview performance
- skill growth
- goal progress

Ensure metrics are explainable and do not imply false precision.

Sprint 5 — Promotion and Opportunity Readiness

Support:

- promotion readiness
- leadership evidence
- scope progression
- compensation goals
- missing proof
- recommended next experiences
- internal versus external opportunity comparison

Sprint 6 — Career Intelligence UI

Minimum frontend:

- goals
- skill gaps
- learning plan
- progress
- readiness
- next recommended actions

Phase 7 exit criteria

Phase 7 is complete when:

- users can define structured career goals
- gaps are calculated from canonical evidence
- learning plans connect to specific goals
- progress aggregates prior platform outcomes
- recommendations explain why they matter
- no unsupported career claim enters canonical knowledge

Phase 8 — Career Agent Foundation

Phase 8 should coordinate existing services, not recreate them.

The Career Agent is an orchestration layer.

Sprint 1 — Decision Engine

Create a recommendation contract combining:

- user knowledge
- goals
- applications
- recruiter communication
- interviews
- market signals
- preferences
- constraints

Every recommendation should include:

- action
- reason
- evidence
- confidence
- impact
- urgency
- required approval
- originating services

Sprint 2 — Action Queue

Create a unified user action queue.

Examples:

- review resume change
- answer profile question
- submit application
- reply to recruiter
- complete assessment
- prepare interview
- practice story
- learn missing skill
- follow up
- review career goal

Support:

- priority
- due date
- status
- source
- dependency
- dismissal
- snooze
- completion
- audit history

Do not execute high-impact actions automatically.

Sprint 3 — Daily Career Brief

Generate a daily brief from existing data:

- new strong job matches
- applications needing attention
- recruiter responses
- upcoming interviews
- overdue tasks
- profile gaps
- learning priorities
- recommended actions

Build the service and API first.

No notification-provider integration is required yet.

Sprint 4 — Safe Agent Orchestration

Add an orchestration service capable of calling domain capabilities.

The orchestrator may:

- retrieve jobs
- request resume analysis
- build application packages
- generate communication drafts
- generate interview preparation
- create recommendations
- add tasks

It may not:

- submit applications
- send messages
- accept offers
- reject offers
- alter canonical facts without approval
- delete user records

Add capability permissions explicitly.

Sprint 5 — Career Agent UI

Build a minimal home workspace:

- daily brief
- action queue
- recommendations
- progress
- upcoming deadlines
- explanation panel

Phase 8 exit criteria

Phase 8 foundation is complete when:

- the agent coordinates existing domain services
- recommendations are explainable
- permissions are explicit
- the user has a unified action queue
- no unsafe autonomous action exists
- all actions remain traceable to canonical data

Parallel Track — Market Intelligence Foundation

Implement this alongside later sequential phases only when it does not block them.

Scope

Build an ingestion and evidence layer for public hiring signals.

Sources may begin with:

- existing job data
- public job descriptions
- skills frequency
- location trends
- compensation data already available
- public hiring guidance
- application outcomes aggregated from the platform

Do not scrape restricted private sources.

Capabilities

- signal ingestion
- normalization
- source provenance
- confidence
- trend aggregation
- skill-demand trends
- role trends
- location trends
- compensation trends when supported
- resume requirement trends
- interview topic trends
- market snapshots

Market Intelligence must never directly overwrite user knowledge.

It provides evidence to:

- matching
- Resume Intelligence
- Interview Intelligence
- Career Intelligence
- Decision Engine

Parallel Track — Platform Intelligence

Implement the minimum platform layer needed to evaluate and operate AI capabilities.

Required foundations

Prompt and strategy versioning

Track:

- capability
- strategy version
- prompt version
- model/provider
- timestamp
- configuration

Evaluation records

Support evaluations for:

- resume changes
- job matches
- recruiter classification
- application matching
- interview questions
- story generation
- mock-interview feedback
- career recommendations

Core metrics

Track:

- correctness
- grounding
- unsupported-claim rate
- user approval rate
- user rejection rate
- confidence calibration
- latency
- cost when available
- failure rate

Safety and explainability

Every AI output must support:

- provenance
- evidence
- confidence
- assumptions
- strategy version

Provider abstraction

Avoid hard-coding AI services directly into domain logic.

Use a shared provider interface where practical.

Testing Requirements

For every sprint:

1. add focused unit tests
2. add service tests
3. add API access and user-scoping tests
4. test invalid state transitions
5. test idempotency where relevant
6. test evidence and audit behavior
7. run adjacent regression suites
8. run compilation or type checking
9. run frontend build when frontend changes
10. record tests run in the completion summary

At phase boundaries, run broader suites.

Do not claim the complete repository passes unless the full suite was actually run.

Clearly separate:

- tests passed
- tests not run
- pre-existing failures
- new failures

Database and Migration Rules

- Prefer normalized relational storage.
- Continue using PostgreSQL-compatible schema patterns.
- Add indexes for expected query paths.
- Preserve existing data.
- Avoid destructive migrations.
- Add schema-version visibility where required.
- Keep provider identifiers separate from canonical IDs.
- Ensure all user-owned records are scoped by user ID.
- Add uniqueness constraints for idempotent operations.

API Rules

- Keep route handlers thin.
- Put business logic in service packages.
- Use explicit request and response DTOs.
- Do not leak internal persistence models.
- Preserve backward compatibility where practical.
- Validate ownership on every user-scoped operation.
- Return explainable error responses.
- Never expose provider tokens or secrets.

Frontend Rules

Until the later UI hardening cycle:

- build only functional, minimal interfaces
- reuse existing design-system components
- avoid one-off styling
- break large components before they become unmanageable
- keep API types explicit
- handle loading, empty, success, and failure states
- do not hide backend errors
- keep server state authoritative
- do not reimplement backend rules in the browser

Documentation Rules

After each sprint:

- update the relevant phase document
- update architecture documentation when boundaries change
- update API documentation
- update schema documentation
- update README/ROADMAP status only when the sprint is genuinely complete
- document intentional omissions
- document configuration required for real provider integrations

Use consistent phase status language:

planned
active
functional foundation complete
complete
deferred
blocked

Do not mark a phase fully complete merely because its backend foundation exists.

Final Completion Report

After all phases and parallel foundations are implemented, provide one consolidated report containing:

1. Phase status

For every phase:

- completed capabilities
- partially completed capabilities
- intentionally deferred capabilities
- external configuration required

2. Architecture

- package map
- canonical ownership boundaries
- provider adapters
- major data flows
- event flows

3. Verification

- exact commands run
- passing suites
- suites not run
- known failures
- unresolved risks
```
