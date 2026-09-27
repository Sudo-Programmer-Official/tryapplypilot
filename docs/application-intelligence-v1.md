# Application Intelligence V1

## Goal

Turn an approved resume version into a reviewable application package with clear state tracking.

This slice does not automate submission. It prepares the package, keeps the user in control, and records application progress after submission.

## V1 flow

```text
High-match job
↓
Approved resume version
↓
Application package
↓
Open official apply link
↓
User submits manually
↓
Track status
```

## Included in Sprint 1

- application package builder
- state machine for application progress
- versioned resume attachment reference
- direct apply link artifact
- user-scoped application history
- audit trail for package creation and status changes

## Included in Sprint 2

- explicit task updates inside the application workflow
- persistent application notes
- timeline events for task activity and notes
- richer submission checklist for post-submit follow-up

## Included in Sprint 3

- structured application answers with reusable and sensitive flags
- structured application metadata for recruiter, portal, confirmation, and deadlines
- explicit application artifact model for answers, confirmations, and supporting references
- validated `submit` action for `ready_to_apply -> applied`
- automatic deadline and follow-up task generation from structured dates
- reusable answer library endpoint foundation

## Workflow model

The package should now support three layers of history:

- status transitions such as `applied` or `interviewing`
- task-level progress such as opening the form or capturing confirmation details
- free-form notes such as recruiter messages, deadlines, or portal references

It should also preserve:

- the exact resume version that was submitted
- the exact structured answers used during submission
- the structured confirmation details captured after submission

## Not included yet

- ATS autofill
- cover letter generation
- form-answer generation
- browser automation
- one-click application submission

## Product rules

- application packages must reference approved resume versions, not raw drafts
- official apply links must come from connector-collected job data
- state changes must be explicit and auditable
- package creation should be idempotent for the same job plus resume version pair
