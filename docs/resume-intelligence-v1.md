# Resume Intelligence V1

## Goal

Build a job-aware resume engine that can turn a high-match opportunity into an application-ready, evidence-backed resume in under 60 seconds.

This is not a generic resume generator. The product advantage is that when the right job appears, the user already has the best possible resume foundation for that job and only needs a fast, reviewable refinement step.

## Product rule

Optimize evidence first, then optimize resume presentation.

The system must never invent claims. It should search for proof, improve phrasing, and show the user exactly what changed before anything is exported.

Most important rule:

- improve the presentation of verified experience
- never invent experience to improve the match

## V1 execution model

V1 should not be built as seven loosely coupled autonomous agents.

Build one `ResumeIntelligenceService` that orchestrates focused components through a single controlled path:

```text
High-Match Job
↓
Resume Selection
↓
Gap Analysis
↓
Evidence Retrieval
↓
Change Generation
↓
Resume Critique
↓
Deterministic Validation
↓
Structured Review
↓
Approved Resume Version
```

Each component can later become a more independent agent, but the first sprint should keep one orchestrated workflow, one run record, and one audit trail.

## Primary user flow

```text
New Job
↓
Matching Engine
↓
Resume Intelligence
↓
Select Best Resume
↓
Find Gaps
↓
Find Evidence
↓
Improve Bullets
↓
Critique + Score
↓
Show Diff
↓
User Approves
↓
Generate PDF
↓
Apply
```

## Run lifecycle

Resume analysis may involve multiple model calls and must be asynchronous and resumable.

Required run states:

- `queued`
- `selecting_resume`
- `analyzing_gaps`
- `finding_evidence`
- `generating_changes`
- `critiquing`
- `validating`
- `ready_for_review`
- `failed`

Product rule:

- the user must not lose the run if a component fails or the page refreshes

## Core components

### 1. Resume Selection

Question:

Which existing resume is closest to this job?

Inputs:

- normalized job description
- structured job requirements
- user's resume library
- structured profile and approved evidence signals

Outputs:

- selected resume variant
- confidence score
- short reason summary
- fallback behavior when confidence is low

Selection signals:

- semantic similarity between resume and job
- matching skills and technologies
- matching role family and seniority
- matching domain and platform experience
- recent user-approved variants for similar jobs

### 2. Gap Analysis

Question:

What does the job require that the selected resume does not emphasize well enough?

Outputs:

- covered requirements
- weakly represented requirements
- missing technologies, skills, or achievements
- keyword opportunities
- risk flags for unsupported requirements

Product rule:

- do not rewrite the whole resume when the real problem is emphasis, ordering, or missing evidence-backed detail

### 3. Evidence Retrieval

Question:

What truthful evidence already exists that can support a stronger version of this resume?

Evidence sources:

- uploaded resumes
- structured profile
- projects and achievements
- accepted past resume edits
- user conversations when facts are explicitly verified
- future knowledge graph entities
- connected sources such as GitHub, LinkedIn, or email when permissions exist

Outputs:

- evidence snippets with provenance
- reusable accomplishment candidates
- missing-proof flags when the system cannot support a claim

Product rule:

- unsupported claims must be blocked, not hallucinated

Required provenance fields for every suggestion:

- `source_type`
- `source_id`
- `source_excerpt`
- `confidence`

Example source types:

- existing resume bullet
- user profile
- project
- verified conversation fact
- manually approved achievement

### 4. Change Generation

Question:

How should the resume change to present the same truth more clearly and more persuasively for this job?

Responsibilities:

- strengthen bullets with clearer outcomes, scope, and metrics
- emphasize relevant technologies and domain language
- preserve factual accuracy
- avoid duplicated claims across sections
- keep changes explainable and diffable
- only modify content that has evidence support

### 5. Resume Critique

Question:

Would a recruiter or ATS reject this resume, and why?

Checks:

- keyword coverage
- action verb quality
- bullet length and readability
- formatting consistency
- repeated wording
- section clarity
- missing metrics
- unclear business impact
- leadership or ownership gaps when relevant

Outputs:

- ATS score
- readability score
- keyword coverage score
- concrete improvement suggestions
- critique summary

### 6. Structured Diff

Question:

How do we show the user the changes without surprises?

Outputs:

- added content
- removed content
- modified content
- reason for each change
- evidence source for each accepted claim

## Suggestion contract

Every suggested change should be serialized in a stable, reviewable structure:

```json
{
  "change_id": "change_123",
  "section": "experience",
  "entry_id": "experience_456",
  "operation": "modify",
  "original_text": "Built backend APIs for the platform.",
  "suggested_text": "Designed and delivered backend APIs supporting the platform's appointment and payment workflows.",
  "rationale": "Adds relevant domain context found in the target job.",
  "job_requirements": ["API design", "payments"],
  "evidence": [
    {
      "source_type": "project",
      "source_id": "project_789",
      "source_excerpt": "Implemented appointment and payment APIs.",
      "confidence": 0.97
    }
  ],
  "risk_level": "low",
  "status": "pending"
}
```

This contract should drive the review UI, audit history, and later evaluation of model quality.

## Deterministic validation

Agents may propose changes. Deterministic code must enforce integrity before review and before PDF export.

Validation rules:

- no unsupported company, metric, title, date, or technology may be introduced
- dates and employment history must remain consistent
- contact information must remain unchanged
- the final resume must stay within the configured page limit
- bullets must not be duplicated
- required sections must remain present
- PDF generation must succeed

## No-change outcome

The system must be allowed to conclude that no rewrite is needed.

Valid result:

- the current resume is already the strongest available version for this job

Product rule:

- do not rewrite content simply because the pipeline ran

## Review experience

The review screen should feel closer to a code diff than a black-box rewrite.

Minimum UX:

- before and after score comparison
- green additions
- red removals
- rationale per change
- evidence trace for strengthened claims
- approve, reject, or edit controls at the change level
- final PDF generation only after review

Example status entry:

```text
Anthropic
93% match
Resume Ready
View Changes
Apply
```

## Facts, wording, and evidence

Accepted wording must not automatically become new factual evidence.

Store separately:

- verified fact
- generated wording
- user-approved wording
- source evidence

Otherwise, an AI-written sentence could later be mistaken for proof of an achievement that was never verified.

## Resume versioning

Every generated resume must be versioned and reversible.

Save at minimum:

- source resume version
- target job
- selected changes
- rejected changes
- generated document version
- generation timestamp
- agent and model configuration

Product rule:

- the user must always be able to compare against the original and restore an earlier version

## Data writebacks

Accepted improvements should compound.

When the user accepts a change, the system should save:

- improved bullet variant
- mapped role family
- supporting evidence references
- acceptance outcome
- job context and requirements

This becomes reusable input for future resume selection and rewriting rather than one-off generation.

Use a simple knowledge-source abstraction in V1 so the system can read from:

- current resume
- structured profile
- projects
- approved prior resume outputs

This abstraction should be ready to connect to a broader knowledge graph later, but broad graph implementation is not required for this sprint.

## Metrics

Track at minimum:

- time to reviewable draft
- suggestion acceptance rate
- rejected change rate
- evidence coverage rate
- ATS score before and after
- callback and interview rate by resume variant
- bullet patterns that correlate with better outcomes

## Offline evaluation baseline

The first production scorecard for Resume Intelligence should be deterministic and attached to every analysis run.

Minimum checks:

- selection confidence
- requirement coverage rate
- supported evidence coverage rate
- evidence integrity for supported versus blocked claims
- change explainability completeness
- ATS score delta
- time to reviewable draft

The initial regression pack should cover:

- strong existing resume with few changes
- resume with supported missing evidence
- job asking for skills the user does not possess

## V1 vertical slice

Build this first:

1. Trigger a resume-intelligence run after a job exceeds the configured high-match threshold.
2. Select the closest existing resume variant using semantic similarity, structured criteria, and user preferences.
3. Compare the selected resume with the job and identify meaningful coverage gaps.
4. Retrieve supporting evidence from approved user sources through a knowledge-source abstraction.
5. Generate only evidence-backed modifications to existing resume content.
6. Evaluate the proposed resume for ATS compatibility, clarity, impact, readability, and job relevance.
7. Apply deterministic factual, structural, and formatting validation.
8. Produce a structured, evidence-linked change set with added, removed, modified, rationale, confidence, and risk fields.
9. Present every change for individual approval, rejection, or editing.
10. Generate a versioned final PDF using accepted changes only.
11. Preserve the original resume and full generation audit trail.
12. Save approved facts and wording separately so future generations can reuse them safely.
13. Support asynchronous execution, retry, failure visibility, and resumable review.
14. Permit a valid no-changes-recommended result.

## Sprint exit criteria

The sprint is complete only when:

- a high-match job automatically creates one resume-intelligence run
- the system selects an existing resume variant and explains why
- every proposed factual change has traceable evidence
- unsupported claims are rejected before reaching the user
- the user can approve, reject, or edit suggestions individually
- the system generates a valid final PDF from accepted changes only
- the original resume remains unchanged
- the accepted version is saved and can be reused
- rerunning the same job and resume does not create unnecessary duplicate suggestions
- at least three representative test cases pass

Required representative test cases:

- strong existing resume with few changes
- resume with supported missing evidence
- job asking for skills the user does not possess

## Non-goals for V1

- fully autonomous one-click resume submission
- cover letter generation as part of the first slice
- LinkedIn rewriting
- unsupported skills insertion
- creating entirely new experience entries
- market-intelligence-driven rewriting
- fully autonomous approval
- broad knowledge-graph implementation
- generic "write me a resume" flows disconnected from a live job
- broad automation on external accounts before the trust layer is complete
