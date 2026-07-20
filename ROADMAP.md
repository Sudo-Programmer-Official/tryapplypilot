# TryApplyPilot Roadmap

> Every new capability must answer one question: Does it help the AI understand the user better, discover better opportunities, reduce manual work, or improve long-term career growth? If not, it does not belong in TryApplyPilot.

As of July 19, 2026, this repository is still executing `Phase 1`, but the product vision is larger than a job alert tool.

North star:

> Build an AI Career Operating System that continuously discovers opportunities, understands each user's professional journey, automates repetitive job-search work, manages recruiter communication, improves interview readiness, and stays useful throughout the user's career.

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
- AI should cite evidence from the user's profile whenever possible.
- AI should continuously learn through conversation and feedback.
- AI should minimize repetitive work.
- Users remain in control of high-impact actions.

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
Career Coach
```

## Current status

- `Phase 1` is the active build target in this repo.
- The repo already has early profile signals through resumes, preferences, watchlists, and user-specific matching.
- The discovery engine already includes reusable ATS connectors for `Greenhouse`, `Lever`, `Ashby`, `Workday`, `SmartRecruiters`, and `iCIMS`, plus dedicated company-career connectors for `Microsoft`, `Google Careers`, and `Amazon Jobs`. `Meta Careers` remains planned until a higher-confidence public source is validated.
- The system is not graph-native yet, and later AI surfaces are not first-class product flows yet.

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

## Phase 3: Resume Intelligence

Goal: turn the knowledge graph into living, role-aware resume assets.

Deliverables:

- resume agent with role-targeted resume generation
- reusable bullet and accomplishment library
- tailored summaries, skills sections, and experience emphasis by role family
- review UI for accepting, editing, and saving variants
- provenance from graph evidence to generated resume output

Exit gate:

- a user can generate and maintain high-quality resume variants with minimal manual rewriting
- resume changes improve matching quality instead of drifting from the source profile

Success metrics:

- resume generation time drops materially compared with manual tailoring
- generated resumes preserve evidence fidelity to the knowledge graph
- match quality improves when graph-backed resume variants are available

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

I think this roadmap is now at the point where it can become the canonical product roadmap. I wouldn’t make structural changes anymore. Instead, I’d add three strategic sections that came out of our recent discussions and will become major differentiators.

⸻

1. Add a New Capability: Market Intelligence

I would add this between Phase 5 (Recruiter Intelligence) and Phase 6 (Interview Intelligence) because it serves both resumes and interviews.

Phase 5.5: Market Intelligence

Goal: Continuously understand what the hiring market values and use evidence-based trends to improve user outcomes.

Deliverables

* Market Intelligence Agent
* Public hiring signal ingestion
* Recruiter and hiring-manager trend analysis
* Hiring pattern detection
* Resume recommendation engine driven by market trends
* Interview trend detection
* Skill demand tracking
* Industry-specific hiring insights
* Confidence scoring and evidence aggregation
* Internal Hiring Knowledge Base

Public Sources

* Public recruiter and hiring manager posts
* Engineering leadership articles
* Company engineering blogs
* Public interview experiences
* Official hiring guidance
* Public labor market reports
* Technical community discussions (where appropriate)

Core Pipeline

Public Hiring Signals
        ↓
Content Collection
        ↓
AI Classification
        ↓
Evidence Aggregation
        ↓
Trend Detection
        ↓
Hiring Knowledge Base
        ↓
Resume Agent
Interview Agent
Career Coach
Matching Agent

Expected Outcomes

* Detect evolving hiring expectations.
* Recommend resume improvements backed by market evidence.
* Identify emerging technologies and skills.
* Improve interview preparation using current hiring patterns.
* Continuously improve AI recommendations without relying on a single opinion.

Guardrails

* Only use publicly available information.
* Aggregate multiple sources before forming recommendations.
* Record confidence levels.
* Distinguish opinion from repeated hiring patterns.
* Keep users in control of adopting recommendations.

Exit Gate

* Resume, interview, and coaching recommendations reflect verified hiring trends instead of static assumptions.

⸻

2. Add a New AI Agent

In AI_AGENTS.md and reference it in the roadmap:

Market Intelligence Agent

Responsibilities:

* Monitor public hiring trends.
* Detect changes in resume expectations.
* Track emerging technologies and role requirements.
* Identify recurring recruiter advice.
* Feed structured insights into:
    * Resume Agent
    * Matching Agent
    * Interview Agent
    * Career Coach

This becomes another shared intelligence layer, just like the Career Knowledge Graph.

⸻

3. Add a “Decision Engine”

One thing we’ve discussed repeatedly is that the AI shouldn’t blindly automate. Every recommendation should combine multiple sources of evidence.

I would document a Decision Engine like this:

Career Knowledge Graph
        │
        │
Market Intelligence
        │
        │
Job Requirements
        │
        │
Recruiter Communication
        │
        ▼
Decision Engine
        ▼
AI Recommendation

This means a recommendation isn’t based solely on:

* the user’s profile,
* the job description, or
* one recruiter post.

Instead, it considers all available evidence before making a suggestion.

⸻
## Phase 6: Interview Intelligence

Goal: convert company, recruiter, role, and application context into interview readiness.

Deliverables:

- interview briefs per role and stage
- likely-question generation grounded in the user's own background
- mock interview workflows
- post-interview note capture and graph updates
- assessment and prep tracking tied to the active application

Exit gate:

- every interview is prepared with relevant context
- every interview outcome strengthens the long-term user profile

Success metrics:

- interview prep artifacts are generated before the majority of scheduled interviews
- post-interview notes consistently feed the graph and future prep context
- users report materially reduced prep time without loss of confidence or quality

## Phase 7: Career Coach and Analytics

Goal: stay useful after the immediate job search and become a continuous career system.

Deliverables:

- recurring check-ins and conversational career memory
- skill-gap analysis and learning plan generation
- long-range career planning and role progression guidance
- analytics for funnel conversion, source performance, interview performance, and growth trends
- coaching loops that continue during employment, not only during unemployment

Exit gate:

- the product remains valuable even when the user is not actively applying
- coaching, analytics, and memory create compounding value over months and years

Success metrics:

- meaningful engagement continues after job placement
- users receive ongoing coaching or planning value outside active job search windows
- long-term profile, learning, and career-history coverage compounds over time

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
7. `Phase 7` needs enough longitudinal data to produce meaningful coaching and analytics.

## Planning horizons

- `Horizon 1` (`0-12 months`): Discovery Engine, Career Knowledge Platform, AI Profile Evolution, Resume Intelligence
- `Horizon 2` (`1-3 years`): Application Intelligence, Recruiter Intelligence, Interview Intelligence
- `Horizon 3` (`3-10 years`): Career Coach, lifelong professional memory, AI career partner, and full professional-lifecycle support

## Near-term operating rule

Until `Phase 1` is live and trusted in production, do not spend the main engineering path on:

- browser extension work
- ATS autofill
- recruiter CRM surfaces
- interview prep surfaces
- career coaching flows
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
