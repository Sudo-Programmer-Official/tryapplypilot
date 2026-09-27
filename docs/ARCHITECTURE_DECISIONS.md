# Architecture Decisions

## ADR-001: PostgreSQL As The Primary Datastore

Status: Accepted

TryApplyPilot uses PostgreSQL as the primary persistent store for jobs, users, knowledge entities, evidence, and audits.

Reason:

- transactional consistency
- straightforward schema migrations
- strong query flexibility during product discovery
- one operational store for the current stage

## ADR-002: Knowledge Platform As The Canonical User Model

Status: Accepted

The Career Knowledge Platform is the canonical source of truth for structured user career data.

Reason:

- downstream agents need stable reads
- resume parsing should happen once, not on every workflow
- evidence and versioning must be centralized

## ADR-003: Evidence-Backed Recommendations

Status: Accepted

Any future AI recommendation that changes a user-facing career artifact must be grounded in stored evidence.

Reason:

- reduces hallucination risk
- improves explainability
- supports human review and auditability

## ADR-004: Human Approval For High-Impact AI Changes

Status: Accepted

High-impact profile and resume changes must be staged and reviewable before becoming canonical when ambiguity or conflict exists.

Reason:

- protects user trust
- avoids destructive knowledge corruption
- keeps AI behavior accountable

## ADR-005: Internal Domain Events Before External Event Infrastructure

Status: Accepted

The platform emits internal Python domain events and stores them as timeline records before introducing a distributed event bus.

Reason:

- preserves a clean business contract early
- avoids premature infrastructure complexity
- future-proofs integrations with Resume Intelligence, Recruiter Intelligence, and analytics
