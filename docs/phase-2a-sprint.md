# Phase 2A Sprint

## Career Knowledge Platform Foundation

## Context

`Phase 1` is the discovery engine.

The next engineering objective should not be a user-facing AI feature. It should be the foundational platform that future AI capabilities will reuse.

This sprint prioritizes architecture over UI.

Future agents for resume intelligence, recruiter intelligence, market intelligence, interview intelligence, and career intelligence should all build on this layer instead of inventing separate storage and retrieval logic.

## Primary goal

Build the `Career Knowledge Platform`.

This becomes the system of record for what the AI knows about a user. It should replace scattered profile fields with structured, evidence-backed entities while staying on PostgreSQL.

## Guiding principles

- structured data before AI behavior
- facts before summaries
- evidence before generation
- one source of truth
- AI recommends; humans approve
- every fact is traceable
- every write is auditable

## Deliverables

### 1. Knowledge domain model

Design normalized entities for:

- user
- experience
- project
- skill
- technology
- achievement
- leadership
- resume
- resume variant
- application
- recruiter
- interview
- learning goal
- career goal

Each entity should support:

- unique ID
- timestamps
- source
- confidence
- evidence
- version history

Implementation rule:

- do not introduce graph database technology in this sprint
- remain on PostgreSQL
- model relationships so they can later support graph-style traversal

### 2. Evidence layer

Create a reusable evidence abstraction.

Supported evidence sources:

- resume
- profile
- project
- conversation
- manual entry

Product rule:

- every future AI recommendation must reference evidence
- unsupported claims are blocked

### 3. Knowledge APIs

Create internal APIs for:

- read profile
- search projects
- search achievements
- search skills
- retrieve evidence
- update entities
- approve changes
- reject changes

No UI is required in this sprint.

### 4. Profile ingestion pipeline

Implement ingestion interfaces for:

- resume
- profile
- future LinkedIn hook
- future GitHub hook
- future voice conversation hook

These can begin as adapters and interfaces rather than full integrations.

### 5. Versioning

Every modification should preserve:

- original
- suggested
- approved
- rejected
- source
- reason
- timestamp
- user

Product rule:

- never overwrite history

### 6. Audit trail

Every AI write should record:

- who
- when
- which agent
- why
- evidence
- confidence
- previous value
- new value

### 7. Knowledge query layer

Create reusable query services such as:

- find strongest project for Kubernetes
- find leadership examples
- find payment experience
- find distributed systems work
- find healthcare experience

These queries should become reusable across all later agents.

### 8. AI-ready interfaces

Define interfaces for future agents:

- Resume Agent
- Interview Agent
- Recruiter Agent
- Career Intelligence Agent
- Market Intelligence Agent

None of these should directly access database tables.

Everything should go through the knowledge platform.

## Out of scope

Do not build:

- resume rewriting
- cover letters
- application automation
- email integration
- interview preparation
- market intelligence behavior
- career intelligence behavior
- knowledge graph visualization

These capabilities depend on this platform but are not part of this sprint.

## Acceptance criteria

The sprint is complete when:

- all user knowledge has a canonical representation
- facts and evidence are separated
- every entity is versioned
- every change is auditable
- future agents can retrieve structured information without parsing resumes again
- no AI component needs to read raw resumes directly after ingestion

## Expected handoff

When this sprint is complete, the next major capability can build on:

- canonical entities
- reusable evidence retrieval
- auditable writes
- approval workflows
- versioned profile history
- AI-safe internal interfaces

This is the foundation for `Phase 3: Resume Intelligence` and the later intelligence layers that follow it.
