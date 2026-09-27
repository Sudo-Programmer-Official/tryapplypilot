# Knowledge Platform

## Purpose

The Knowledge Platform is the canonical profile layer for TryApplyPilot.

Its job is to turn uploaded resumes, profile updates, and future structured inputs into reusable knowledge entities with traceable evidence so downstream AI systems query knowledge instead of reparsing raw documents.

## Design Principles

1. Every fact must be traceable to evidence.
2. Canonical entities are the source of truth.
3. New uploads enrich knowledge rather than overwrite it.
4. Ambiguous changes are staged for review.
5. Future AI agents query this platform instead of reading resumes directly.

## Design Philosophy

The platform is intentionally conservative.

- prefer structured knowledge over repeated parsing
- prefer deterministic linking before fuzzy AI behavior
- prefer staged review over destructive auto-merge
- prefer evidence-ranked answers over best-effort text generation
- prefer one stable SDK surface over direct table access

## Package Layout

`backend/app/knowledge_platform/`

- `services.py`: canonical service API, approvals, alias registration, query methods, completeness, health checks
- `store.py`: in-memory and Postgres persistence
- `interfaces.py`: storage contract
- `linking.py`: deterministic normalization and alias resolution
- `merge.py`: merge classification and conflict detection
- `queries.py`: reusable query helpers, evidence ranking, completeness scoring
- `health.py`: data quality validation
- `ingestion.py`: resume/profile ingestion pipeline
- `errors.py`: domain-specific exceptions
- `utils.py`: serialization and normalization helpers

## Entity Model

Core table: `knowledge_entities`

Each entity represents a canonical fact cluster for one user.

Key fields:

- `entity_type`: `user`, `experience`, `project`, `skill`, `technology`, `achievement`, `leadership`, `education`, `certification`, `award`, `resume`, and future profile types
- `canonical_name`: stable human-readable identity
- `content`: structured payload for that entity
- `evidence_ids`: supporting evidence references
- `current_version`: currently approved version number
- `approval_status`: `suggested`, `approved`, or `rejected`

Examples:

- Technology: `React`
- Skill: `Distributed Systems`
- Experience: `Staff Software Engineer`
- Project: `AI Scheduling Platform`

## Alias Model

Table: `knowledge_aliases`

Aliases map user-scoped variants onto canonical names.

Examples:

- `ReactJS` -> `React`
- `React.js` -> `React`
- `MS SQL` -> `SQL Server`
- `Amazon Web Services` -> `AWS`

Alias resolution order:

1. Manual override
2. Stored alias
3. Deterministic built-in alias map
4. Normalized fallback

Manual overrides always win over automatic rules.

## Evidence Model

Table: `knowledge_evidence`

Evidence stores provenance for every extracted or approved fact.

Supported sources:

- `resume`
- `profile`
- `project`
- `conversation`
- `manual_entry`

Each evidence record includes:

- source type
- source id
- excerpt
- metadata
- created timestamp

Evidence ranking priority:

1. user-approved edits
2. resume evidence
3. structured profile
4. project descriptions
5. conversation-derived facts

## Versioning And Audit Model

Table: `knowledge_entity_versions`

Every proposed change is versioned before approval.

Version records include:

- previous content
- new content
- reason
- evidence ids
- confidence
- actor
- reviewer
- review notes

Audit events are recorded for:

- change staged
- change approved
- change rejected

This makes the knowledge layer reviewable and safe for future AI orchestration.

## Entity Lifecycle

1. Source input arrives from resume upload, profile edit, or future connectors.
2. Evidence is created first.
3. Entity linking resolves the canonical identity.
4. Merge policy classifies the change.
5. New entities are approved into the canonical graph.
6. Updates, removals, and conflicts are versioned and staged.
7. Approval or rejection updates the timeline and audit trail.
8. Downstream agents read the canonical result through the service or SDK.

## Ingestion Flow

Resume upload flow:

1. Extract text from uploaded resume
2. Parse sections such as summary, experience, projects, skills, education, certifications, awards
3. Extract structured knowledge items
4. Create evidence records
5. Resolve canonical names through alias linking
6. Merge against existing approved knowledge
7. Auto-approve new entities
8. Stage updates, removals, and conflicts for review
9. Compute completeness and merge summaries

Profile update flow:

1. Create profile evidence
2. Upsert the canonical `user` entity
3. Preserve version history

## Merge Flow

Merge classification happens per entity type.

Possible outcomes:

- `added`
- `updated`
- `unchanged`
- `removed`
- `conflict`

Rules:

- nothing is silently deleted
- removals are staged only
- conflicting identity fields are staged for review
- list fields are union-merged
- richer strings win over shorter placeholders

## Query Flow

The Knowledge Platform service exposes query APIs for downstream agents.

Current examples:

- `find_projects_by_skill()`
- `find_projects_by_technology()`
- `find_best_leadership_examples()`
- `find_quantified_achievements()`
- `find_cloud_experience()`
- `find_backend_projects()`
- `find_ai_projects()`
- `find_resume_evidence()`
- `find_recent_experience()`
- `find_domain_experience()`
- `get_profile_completeness()`
- `run_health_checks()`

Rule:

No future agent should parse resumes directly if the knowledge platform can answer the question.

### SDK examples

```python
knowledge = build_knowledge_platform_client()

profile = await knowledge.get_profile(user_id)
projects = await knowledge.find_projects(user_id, technology="Kubernetes")
examples = await knowledge.find_best_examples(user_id, topic="Leadership")
evidence = await knowledge.find_evidence(user_id, query="payment systems")
metrics = await knowledge.get_metrics(user_id)
timeline = await knowledge.get_timeline(user_id)
```

## Completeness Model

The platform exposes two completeness views.

Baseline area completeness:

- experience
- project
- skill
- technology
- achievement
- leadership
- education
- certification

Strategic completeness report:

- overall score
- experience
- projects
- leadership
- achievements
- architecture
- ai_experience

This prepares Phase 2B for conversational enrichment and gap-closing workflows.

## Health Checks

Health checks currently detect:

- duplicate canonical entities
- orphaned evidence
- missing provenance
- overlapping experience ranges when dates are present
- unsupported achievements without strong metric signals

The health report is designed to run before AI layers consume profile knowledge at scale.

## Event Model

The platform emits internal domain events and stores them in the knowledge timeline.

Current events include:

- `EvidenceAdded`
- `EntityCreated`
- `KnowledgeUpdated`
- `MergeApproved`
- `KnowledgeRejected`
- `ResumeUploaded`
- `ProfileCompleted`
- `AliasRegistered`

This keeps business logic compatible with a future event bus without requiring a redesign now.

## Performance Notes

Schema indexes are optimized for current usage patterns:

- entity lookups by user, type, status, and canonical name
- evidence lookups by user, source type, and source id
- alias lookups by user, type, and normalized alias
- version lookups by entity and user

As the graph grows, query APIs should prefer canonical lookups and constrained entity sets over broad scans.

## Extension Guidelines

When adding a new ingestion source or downstream agent:

1. Add evidence first.
2. Reuse canonical entity types when possible.
3. Register deterministic aliases for repeated variants.
4. Stage destructive or ambiguous changes.
5. Add tests for queryability, traceability, and health.
6. Update this document if the model or flow changes.

## Anti-patterns

Do not do these things in future AI features:

- do not parse resume PDFs directly if the knowledge platform already contains the fact
- do not invent unsupported claims when evidence lookup fails
- do not bypass versioning for high-impact user profile changes
- do not overwrite canonical entities without merge classification
- do not query database tables directly from agents when the SDK or service already provides the read path

## Phase 2A Exit Standard

Phase 2A is complete when:

- resume uploads populate canonical entities
- duplicate aliases resolve consistently
- merge behavior stages updates instead of overwriting
- all critical facts remain evidence-backed
- downstream systems can query knowledge directly
- completeness is measurable
- health checks surface quality issues before AI layers depend on the data
