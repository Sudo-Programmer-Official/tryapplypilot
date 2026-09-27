# Profile Evolution

## Purpose

Profile Evolution is the first `Phase 2B` capability built on top of the Knowledge Platform.

Its job is to improve profile quality through short, evidence-backed conversations instead of long setup forms or opaque chat transcripts.

The output is not free-form memory. The output is staged, reviewable knowledge.

## Product Rules

1. Every conversation should target a specific knowledge gap.
2. Every extracted fact must produce evidence.
3. No conversational write is applied directly to canonical knowledge.
4. Users review suggested changes before approval.
5. Future agents consume structured knowledge, not raw chat history.

Design rule:

- this is a guided interview, not a chatbot
- the product loop is question -> answer -> extracted facts -> staged review -> next question
- UI should optimize for transparency and knowledge gain, not conversational novelty

## Scope Of The First Slice

Implemented package: `backend/app/profile_evolution/`

- `completeness.py`: strategic gap analysis on top of the knowledge platform completeness report
- `planner.py`: prioritizes the highest-value topic and follow-up question
- `conversation.py`: topic schemas, session model, progress tracking, and submission result types
- `extraction.py`: deterministic fact extraction from structured answers
- `evidence.py`: conversation provenance metadata
- `staging.py`: evidence-backed staged knowledge updates
- `scoring.py`: knowledge gain scoring
- `services.py`: orchestration and persistence
- `interfaces.py`: store contract

## Topic Model

Current enrichment topics:

- `project`
- `architecture`
- `leadership`
- `scale`
- `cloud`
- `ai_ml`
- `performance`
- `mentoring`
- `business_impact`

Each topic defines:

- an initial question
- required fields
- optional fields
- follow-up prompts
- completion threshold
- priority

## Flow

```text
Knowledge Platform
  -> Completeness Analysis
  -> Gap Prioritization
  -> Question Planning
  -> User Answer
  -> Fact Extraction
  -> Conversation Evidence
  -> Staged Knowledge Updates
  -> User Review
  -> Canonical Knowledge
```

## Session Persistence

Table: `profile_evolution_sessions`

Stored per user:

- active topic
- pending, completed, and skipped topics
- extracted fields by topic
- asked follow-ups
- staged version ids
- confidence
- extracted entity summary

This keeps conversations resumable without forcing downstream systems to mine raw message history.

## Developer APIs

The service surface for the first slice is:

- `get_state()`
- `get_remaining_topics()`
- `get_next_question()`
- `extract_facts()`
- `submit_answer()`
- `stage_updates()`
- `calculate_knowledge_gain()`
- `complete_topic()`

All downstream orchestration should use these APIs instead of writing directly into the knowledge platform.

## Acceptance Standard

The Phase 2B slice is only considered complete when:

- profile gaps are explicit and prioritized
- questions are topic-aware and incremental
- answers become structured facts
- facts create evidence
- suggested writes stay staged
- canonical knowledge changes still require approval
- conversation progress persists across requests

## What This Enables Next

This slice is the bridge between the canonical knowledge layer and later intelligence workflows.

It directly unlocks:

- conversational achievement extraction
- richer project and architecture evidence
- stronger resume intelligence inputs
- structured user feedback loops
- higher-confidence explainable recommendations
