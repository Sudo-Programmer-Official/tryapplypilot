# TryApplyPilot Roadmap

> Every new capability must answer one question: Does it help the AI understand the user better, discover better opportunities, reduce manual work, or improve long-term career growth? If not, it does not belong in TryApplyPilot.

As of July 21, 2026, this repository has completed the major product foundations through `Phase 5`, and `Phase 6`: Interview Intelligence is now underway. The current build frontier inside `Phase 6` has reached structured question generation and is moving next into story building.

North star:

> Build an AI Career Operating System that continuously discovers opportunities, understands each user's professional journey, automates repetitive job-search work, manages recruiter communication, improves interview readiness, and stays useful throughout the user's career.

## Product Constitution

Every capability must strengthen at least one of these pillars:

1. Understand the user better.
2. Understand the market better.
3. Reduce manual work.
4. Improve long-term career outcomes.

If a feature does not clearly strengthen one of these pillars, it does not belong in the core product.

## Three Product Pillars

- `Understand Me`: Career Knowledge Graph, AI Profile Evolution, memory, evidence, and career history
- `Understand the Market`: Discovery Engine, Recruiter Intelligence, and Market Intelligence
- `Bridge the Gap`: Resume Intelligence, Application Intelligence, Interview Intelligence, and Career Intelligence

## AI Career Operating System Loop

```text
                Market Intelligence
                       ▲
                       │
                       │
Job Discovery ──► Matching Engine
       │                 │
       ▼                 ▼
Applications ◄── Resume Intelligence
       │                 │
       ▼                 ▼
Recruiter Intelligence   Knowledge Graph
       │                 ▲
       ▼                 │
Interview Intelligence ──┘
       │
       ▼
Career Intelligence
       │
       ▼
Profile Evolution
       │
       └──────────────► Better Job Matching
```

## System Intelligence Layers

Layer 1: `User Intelligence`

- understands skills, projects, experience, goals, preferences, and work history
- source of truth is the Career Knowledge Graph

Layer 2: `Market Intelligence`

- understands hiring trends, recruiter advice, interview patterns, emerging skills, company expectations, and industry changes
- source of truth is aggregated public hiring signals

Layer 3: `Decision Intelligence`

- combines user profile, market intelligence, job requirements, recruiter communication, and previous outcomes to produce recommendations
- this is the reasoning layer that turns raw signals into product behavior

Decision engine:

```text
Career Knowledge Graph
↓
Market Intelligence
↓
Job Requirements
↓
Recruiter Communication
↓
Previous Outcomes
↓
Decision Engine
↓
AI Recommendation
```

## Planning model

- Plan in capabilities, not disconnected features.
- Make the knowledge graph the shared system foundation, not just a later feature.
- Separate data-platform milestones from AI-behavior milestones.
- Establish trust and permissions before asking the AI to act on behalf of users.
- Keep one active build frontier at a time.
- Keep `AI recommends, human decides` as a product rule across every phase.

## Product boundaries

TryApplyPilot is not:

- a generic AI chatbot
- a LinkedIn replacement
- a traditional job board
- an ATS for employers
- a recruiter CRM
- a social network
- a resume template marketplace

Every feature should strengthen the AI Career Operating System instead of pulling the product toward adjacent but disconnected categories.

## AI principles

- AI augments, never replaces, user judgment.
- AI must explain its recommendations.
- AI quality must be measurable before release and monitored after release.
- AI should cite evidence from the user's profile whenever possible.
- AI should continuously learn through conversation and feedback.
- AI should minimize repetitive work.
- Users remain in control of high-impact actions.

## Explainability Standard

Every recommendation should answer:

- why
- based on what evidence
- how confident the system is
- what changes if the recommendation is ignored

The AI should never feel like a black box.

## User Feedback and Continuous Learning

Every recommendation should make the system better.

Learning loop:

```text
User Uses Product
↓
AI Makes Recommendation
↓
User Accepts / Rejects
↓
Outcome Happens
↓
Evidence Captured
↓
Knowledge Graph Updated
↓
Models Improve
↓
Better Recommendations
```

Examples of learning signals:

- resume change accepted
- resume change rejected
- applied
- ignored
- interview obtained
- offer received
- rejection received

## AI Evaluation and Quality

Every AI capability should be continuously evaluated.

Quality loop:

```text
User Feedback
↓
Offline Evaluation
↓
Production Metrics
↓
Prompt Improvements
↓
Model Improvements
```

Shared metrics include:

- resume recommendation quality
- match quality
- false positive rate
- false negative rate
- resume improvement acceptance rate
- recruiter email classification accuracy
- interview preparation usefulness
- hallucination rate
- user satisfaction
- time saved

No AI capability should be treated as production-ready without offline benchmarks, human review, safety checks, and production monitoring.

The detailed quality standard lives in [EVALUATION.md](EVALUATION.md).

## Shared foundation: Career Knowledge Graph

The knowledge graph is the central user model that every agent should read from and write back to. It is not merely a `Phase 2` feature. It is the coherence layer for the whole product.

Core graph domains:

- user identity, preferences, permissions, and connected accounts
- professional profile and career history
- projects, skills, technologies, leadership, and achievements
- resume variants and supporting evidence
- applications, recruiters, and interview history
- learning history, goals, and long-term growth signals

Implementation note:

- `Phase 1` can still use relational operational tables, but new schemas should stay compatible with the graph-first model instead of creating isolated feature silos

## AI memory layer

The AI should not rely on raw chat history as its long-term memory. It should extract durable facts and write them into the knowledge graph.

Memory flow:

```text
Conversation
↓
Facts
↓
Knowledge Graph
↓
Resume
↓
Applications
↓
Recruiters
↓
Career Intelligence
```

## Current status

- `Phase 1`: Discovery Engine is complete.
- `Phase 2A`: Career Knowledge Platform is complete.
- `Phase 2B`: AI Profile Evolution is effectively complete, with remaining work focused on polish rather than new foundations.
- `Phase 3`: Resume Intelligence is complete enough to serve as the evidence-backed resume orchestration layer.
- `Phase 4`: Application Intelligence is complete enough to serve as the canonical workflow layer.
- `Phase 5`: Recruiter Intelligence is complete enough to serve as the canonical recruiter-workflow enrichment layer.
- `Phase 6`: Interview Intelligence is now active, with canonical interview workspaces, personalized preparation, and versioned question banks already implemented.
- The repo already has early profile signals through resumes, preferences, watchlists, and user-specific matching.
- The discovery engine already includes reusable ATS connectors for `Greenhouse`, `Lever`, `Ashby`, `Workday`, `SmartRecruiters`, and `iCIMS`, plus dedicated company-career connectors for `Microsoft`, `Google Careers`, and `Amazon Jobs`. `Meta Careers` remains planned until a higher-confidence public source is validated.
- `Market Intelligence` should continue as a parallel recommendation-freshness track rather than a blocking sequential phase gate.
- `Platform Intelligence` should continue as a cross-cutting track covering evaluation, explainability, latency, cost, experimentation, and safety.

## End-to-end user journey

```text
Onboard
↓
Import Resume
↓
Connect Gmail
↓
Connect LinkedIn
↓
AI Interviews You
↓
Knowledge Graph
↓
Resume Evolves
↓
Jobs Found
↓
AI Matches
↓
Notification
↓
Apply
↓
Recruiter Email
↓
Interview Prep
↓
Offer
↓
Career Growth
↓
Repeat
```

## Phase 0: Foundation

Goal: align the company, repo, and product language before platform scope expands.

Deliverables:

- `MANIFESTO.md`
- `VISION.md`
- `ARCHITECTURE.md`
- `AI_AGENTS.md`
- `EVALUATION.md`
- `KNOWLEDGE_GRAPH.md`
- `PRODUCT_PRINCIPLES.md`
- `DECISIONS.md`
- shared glossary, KPIs, and version boundaries

Exit gate:

- the team can explain the product, system boundaries, and agent responsibilities consistently
- major architecture choices are written down before later phases add operational complexity

Success metrics:

- every core strategy document exists and is internally consistent
- major product and architecture decisions are recorded before downstream teams depend on them
- roadmap, architecture, and AI-agent language are consistent across docs

## Phase 0.5: Identity and Trust

Goal: establish the trust layer before AI starts acting on behalf of users.

Deliverables:

- resume import foundations
- connected account model
- Gmail and Outlook authorization scaffolding
- privacy settings
- AI permissions and action scopes
- notification preferences
- visibility into what the AI can access, modify, and send
- approval and audit rules for high-trust actions

Exit gate:

- users can see what data the AI can access
- users can see what the AI can modify
- users can see what actions require approval
- connected account permissions are explicit enough to support later automation safely

Success metrics:

- 100% of connected data sources expose clear permission scopes to the user
- every high-impact AI action has an explicit approval mode
- users can revoke connected access and automated behaviors without support intervention

## Data ownership

The user's career data belongs to the user. TryApplyPilot exists to organize, improve, and use that information only with explicit permission. Every connected account and every automated action should be transparent, reviewable, and revocable.

## Phase 1: Discovery Engine

Goal: make TryApplyPilot reliable enough to serve as a user's only job discovery tool.

Deliverables:

- production-grade connector framework
- reusable ATS coverage across `Greenhouse`, `Lever`, `Ashby`, `Workday`, `SmartRecruiters`, and `iCIMS`
- dedicated high-value company-career coverage for `Microsoft`, `Google Careers`, and `Amazon Jobs`
- connector health, retry, and scheduler reliability
- normalized job ingestion, deduplication, and lifecycle handling
- user-specific job scoring and thresholding
- fast notification loop with Telegram first
- user onboarding, preferences, watchlists, resumes, and admin workflows
- dashboard for jobs, alerts, source health, and setup readiness

Exit gate:

- a user can rely on the product for 30 days without missing important opportunities
- notifications are relevant and low-noise
- admin operations are manageable without manual database intervention

Notes:

- detailed Phase 1 execution lives in [docs/roadmap.md](docs/roadmap.md)
- the Version 1 scope freeze lives in [docs/v2.md](docs/v2.md)

Success metrics:

- `99%+` scheduler uptime
- `<5 minute` job freshness from source to visible pipeline state
- `<1%` duplicate jobs after normalization and deduplication
- `<5%` clearly irrelevant alerts after user thresholds and filtering are configured

Notification policy for `Phase 1`:

- push notifications must respect the user's notification freshness setting
- dashboard and review queues may show older jobs within a separate user-controlled search window
- recovery or rediscovery flows must not send a Telegram alert for an older posting that falls outside the user's notification freshness window
- alert copy should distinguish between when TryApplyPilot discovered a job and when the company originally posted it

## Phase 2A: Career Knowledge Platform

Goal: build the structured career data platform before layering AI behavior on top.

Deliverables:

- graph-backed profile schema
- entity and relationship model
- graph APIs for reads, writes, and evidence retrieval
- structured profile editor
- resume parser
- LinkedIn import
- voice and conversation ingestion
- evidence and provenance model
- future-ready import hooks for sources like GitHub

Explicit non-goal:

- no AI-driven enrichment magic in this milestone

Exit gate:

- the platform knows the user better than their resume
- downstream systems can read one consistent structured profile instead of scattered files and fields

Phase 2A exit checklist:

- canonical entity model implemented
- resume ingestion populates structured knowledge
- entity linking and merge policies are in place
- evidence is stored and ranked
- version history and audit trail are available
- knowledge query APIs and SDK are stable
- profile completeness scoring exists
- health checks detect inconsistencies
- timeline and internal domain events are available
- documentation is complete
- future agents depend on the knowledge platform rather than raw resume parsing

Success metrics:

- AI-understandable profile coverage reaches `90%+` of core user experience and background
- resume imports require fewer than `5` manual corrections for a typical user
- knowledge graph coverage and evidence density improve week over week for active users

## Phase 2B: AI Profile Evolution

Goal: make the profile improve continuously without forcing users into long forms.

Deliverables:

- AI follow-up questions
- achievement extraction
- project enrichment
- skill inference
- leadership detection
- automatic profile update suggestions
- conversation-to-graph writebacks
- review controls for accepting or rejecting inferred updates

Exit gate:

- the profile improves over time without requiring long forms
- updates stay grounded in evidence and remain reviewable by the user

Success metrics:

- most accepted profile improvements come from AI follow-up and enrichment rather than manual form entry
- inferred updates remain evidence-backed and reviewable
- active-user profile completeness improves over time without requiring long setup sessions

Implementation note:

- the first production slice for this phase is documented in [docs/profile_evolution.md](docs/profile_evolution.md)

Status note:

- `Phase 2B` is now close enough to complete that the remaining work should focus on planner quality, skip/defer handling, and interaction polish rather than new foundations

## Phase 3: Resume Intelligence

Goal: turn a high-match job alert into an application-ready, evidence-backed resume in under 60 seconds.

Deliverables:

- resume intelligence service triggered automatically for high-match jobs
- one orchestrated pipeline for selection, gap analysis, evidence retrieval, change generation, critique, and validation
- evidence-backed change suggestions with required provenance on every proposed factual edit
- deterministic validation for unsupported claims, structural integrity, and PDF generation
- async, resumable run lifecycle with review-ready and failure states
- versioned resume outputs, audit trail, and reusable accepted improvements
- review UI for accepting, editing, and saving structured changes

Exit gate:

- a user can move from a high-match job notification to a reviewed resume variant without starting from a blank page
- every suggested claim is traceable to user evidence or explicitly flagged as unsupported
- the system can conclude no changes are needed when the existing resume is already strongest
- accepted improvements are saved back into the knowledge graph so later resumes start stronger instead of repeating work

Success metrics:

- time from high-match job detection to reviewable resume draft is under `60 seconds` for the primary flow
- suggested changes maintain high evidence fidelity to the knowledge graph
- user acceptance rate for suggested changes is high enough to prove the system is improving resume quality instead of creating cleanup work
- resume-backed match quality and interview conversion improve when graph-backed variants are available

Phase 3 operating rule:

- optimize evidence first, then optimize the resume presentation layer

Implementation note:

- the first vertical slice for this phase is documented in [docs/resume-intelligence-v1.md](docs/resume-intelligence-v1.md)

Recommended sprint sequence:

1. Sprint 1: Resume Selection + Gap Analysis
2. Sprint 2: Evidence Retrieval + Structured Change Set
3. Sprint 3: Resume Critic + Review UI
4. Sprint 4: Versioning + PDF Generation
5. Sprint 5: Evaluation, benchmarks, and quality improvements

## Phase 4: Application Intelligence

Goal: reduce the manual work between discovery and submission.

Deliverables:

- application tracker and state machine
- application package builder for resume, cover letter, and supporting answers
- task queue for deadlines, assessments, and follow-ups
- autofill and workflow strategy for supported ATS surfaces
- application timeline written back into the user graph

Exit gate:

- matched roles can move into a tracked application workflow with low friction
- the product can answer what was applied to, when, with which materials, and what happened next

Success metrics:

- users can complete a tracked application workflow with minimal repeated data entry
- application package preparation time decreases significantly versus manual workflows
- application timeline completeness stays high across active users

## Phase 5: Recruiter Intelligence

Goal: understand inbound recruiter communication and keep the application timeline current automatically.

Deliverables:

- Gmail and Outlook integrations on top of the trust layer from `Phase 0.5`
- email sync pipeline
- email classifier
- intent detection
- recruiter memory tied to company, role, and conversation history
- automatic application timeline updates
- knowledge-graph writebacks from recruiter communication
- notification and reminder routing for required user actions
- draft assistance for acknowledgements, follow-ups, and scheduling replies

Core architecture:

- Gmail or Outlook
- email sync
- email classifier
- intent detection
- recruiter memory
- application timeline
- knowledge graph
- notification engine

Intent coverage:

- new application confirmation
- recruiter outreach
- interview scheduling
- coding assessment
- offer
- rejection
- follow-up request

Expected outcomes:

- update application status automatically
- remember recruiter information automatically
- suggest or draft replies
- prepare interview materials
- remind the user when action is needed

Exit gate:

- users no longer need spreadsheets or manual status tracking for recruiter communication
- recruiter context is available across jobs, conversations, and next actions

Success metrics:

- `95%+` recruiter email classification accuracy across supported intent categories
- `90%+` automatic timeline update accuracy for supported email-driven events
- `<1 minute` from recruiter email ingestion to user notification for actionable events

## Phase 5.5: Market Intelligence

Goal: continuously understand what the hiring market values and improve recommendations using public hiring trends.

Deliverables:

- Market Intelligence Agent
- public hiring signal ingestion
- recruiter and hiring-manager trend analysis
- emerging skills and role-requirement detection
- resume and interview trend recommendations
- confidence scoring and evidence aggregation
- Hiring Knowledge Base
- structured outputs for Resume Intelligence, Matching, Interview Intelligence, and Career Intelligence

Sources:

- public recruiter posts and newsletters
- engineering blogs and company hiring guidance
- public interview reports
- official hiring guidance
- public labor market reports

Guardrails:

- only use publicly available information
- aggregate multiple sources before making a recommendation
- distinguish opinion from repeated pattern
- record confidence levels and supporting evidence
- keep users in control of adopting recommendations

Exit gate:

- resume, matching, interview, and career recommendations reflect verified hiring trends instead of static assumptions

Success metrics:

- market-driven recommendations cite aggregated public evidence
- downstream recommendation usefulness improves without overreacting to single-source noise

## Phase 6: Interview Intelligence

Goal: convert resume, role, recruiter, application, company, and evidence context into highly personalized interview readiness.

Deliverables:

- canonical interview object and interview workspace
- interview scheduling metadata: round, type, interviewer, meeting link, timezone, and notes
- versioned preparation plans tied to canonical interview records
- evidence-backed preparation sections derived from the submitted resume version, job context, recruiter communication, and approved knowledge-platform facts
- generated focus areas, questions-to-ask, checklist tasks, and risk areas that explain why they were produced
- preparation checklist and agenda tied to the active application timeline
- likely-question generation grounded in the user's own background and the live role context
- versioned interview question sets with deterministic category coverage, evidence references, follow-up probes, and review state
- story builder that converts approved evidence into STAR-ready interview stories
- mock interview workflows that already know the user's resume, recruiter context, projects, and application package
- feedback engine for clarity, completeness, technical depth, evidence usage, and communication quality
- post-interview note capture and graph updates
- assessment and prep tracking tied to the active application

Exit gate:

- every interview is prepared with relevant application, recruiter, and evidence context
- every interview outcome strengthens the long-term user profile

Current implemented slices as of Tuesday, July 21, 2026:

- Sprint 1: Interview Workspace
- Sprint 2: Personalized Preparation

Success metrics:

- interview prep artifacts are generated before the majority of scheduled interviews
- generated prep consistently references verified user evidence instead of generic advice
- post-interview notes consistently feed the graph and future prep context
- users report materially reduced prep time without loss of confidence or quality

## Phase 7: Career Intelligence

Goal: stay useful after the immediate job search and become a continuous career system.

Deliverables:

- recurring check-ins and conversational career memory
- skill-gap analysis and learning plan generation
- long-range career planning and role progression guidance
- coaching experiences for active career decisions
- analytics for funnel conversion, source performance, interview performance, and growth trends
- growth tracking that continues during employment, not only during unemployment

Exit gate:

- the product remains valuable even when the user is not actively applying
- coaching, analytics, and memory create compounding value over months and years

Success metrics:

- meaningful engagement continues after job placement
- users receive ongoing coaching or planning value outside active job search windows
- long-term profile, learning, and career-history coverage compounds over time

## Phase 8: Career Agent

Goal: evolve the platform into an always-on career partner that compounds value across the full professional lifecycle.

Capabilities:

- continuously discover opportunities
- improve the user profile automatically through guided workflows
- monitor hiring trends and recruiter communication
- suggest learning, promotion, and career moves
- prepare users for interviews and active applications
- stay useful during employment, transitions, and long-term planning

Operating rule:

- `Phase 8` is not a separate foundation effort
- it is the convergence of User Intelligence, Market Intelligence, and Workflow Intelligence into one persistent decision engine

## Parallel track: Platform Intelligence

Goal: improve every AI workflow in measurable ways while controlling quality, cost, and risk.

Deliverables:

- evaluation framework and offline benchmarks
- prompt versioning and regression tracking
- recommendation quality metrics
- cost and latency monitoring
- experimentation and A/B infrastructure
- explainability standards
- AI safety guardrails

Operating rule:

- `Platform Intelligence` runs alongside product phases instead of waiting until the roadmap is otherwise complete
- no major AI workflow should ship without measurable quality, safety, and monitoring coverage

## Automation maturity model

1. `Level 1`: AI recommends.
2. `Level 2`: AI drafts.
3. `Level 3`: AI prepares.
4. `Level 4`: AI executes after approval.
5. `Level 5`: AI executes automatically within user-defined rules.

This ladder is how the product earns the right to automate more over time without taking control away from the user.

## Sequencing rules

1. `Phase 1` must be production-reliable before the roadmap expands materially.
2. The knowledge graph is a system foundation from the start, even though `Phases 2A` and `2B` deliver the full platform.
3. `Phase 0.5` trust and permission work must exist before AI actions on connected accounts.
4. `Phase 2A` must land before `Phase 2B`.
5. `Phases 2A` and `2B` are platform dependencies for `Phases 3-7`.
6. `Phase 5` depends on account trust, email authorization, and a real application timeline.
7. `Phase 6` depends on a stable application workspace plus recruiter-aware workflow context.
8. `Market Intelligence` depends on enough public-signal coverage and evaluation to separate trend from noise.
9. `Phase 7` needs enough longitudinal data to produce meaningful coaching and analytics.
10. `Platform Intelligence` should tighten quality and safety continuously rather than waiting for a late-phase cleanup.

## Planning horizons

- `Horizon 1` (`0-12 months`): Discovery Engine, Career Knowledge Platform, AI Profile Evolution, Resume Intelligence
- `Horizon 2` (`1-3 years`): Application Intelligence, Recruiter Intelligence, Interview Intelligence, Market Intelligence, and Platform Intelligence
- `Horizon 3` (`3-10 years`): Career Intelligence, lifelong professional memory, AI career partner, and full professional-lifecycle support

## Post-Phase-2B sequencing

After `Phase 2B`, the sequencing should stay disciplined:

1. Finish the last interaction-quality work in `Phase 2B`, especially question planning and skip/defer behavior.
2. Build `Phase 3` as the first major orchestration layer on top of completed foundations.
3. Let `Phase 4` and `Phase 5` turn resumes into applications and recruiter-aware workflow intelligence.
4. Use `Phase 6` to turn application and recruiter context into personalized interview readiness.
5. Use `Phase 7` to stay valuable beyond active job search.
6. Let `Market Intelligence` and `Platform Intelligence` run in parallel so downstream recommendations stay current, measurable, and safe.

The strategic shift at this point is important:

- `Phase 1` made the platform understand the market
- `Phase 2A` made the platform understand the user
- `Phase 2B` made the platform continuously improve that understanding
- every later phase should primarily compose those capabilities rather than inventing new foundations

## Near-term operating rule

Until `Phase 1` is live and trusted in production, do not spend the main engineering path on:

- browser extension work
- ATS autofill
- recruiter CRM surfaces
- interview prep surfaces
- career intelligence surfaces
- broad analytics layers

Those belong on the roadmap, but not ahead of a dependable discovery engine. The main exception is trust and permission scaffolding that de-risks later integrations without widening the active product surface.

## Vision beyond job search

The product should outlive any single job search. Over time, it should support the full professional journey:

```text
Student
↓
First Job
↓
Promotion
↓
Leadership
↓
Career Change
↓
Founder
↓
Advisor
↓
Retirement
```

The goal is a lifelong professional companion, not a tool users abandon after they accept an offer.

## 10-year vision

Ten years from now, when someone thinks about managing their professional life, they should not think about resumes, job boards, spreadsheets, or recruiter emails. They should think about their AI Career Operating System.
