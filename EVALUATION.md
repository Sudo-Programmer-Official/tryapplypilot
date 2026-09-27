# AI Evaluation Standard

As of July 20, 2026, every AI capability in TryApplyPilot is expected to meet this evaluation standard before it is promoted and while it operates in production.

## Purpose

This document defines how AI features are measured, reviewed, and monitored so quality improves over time instead of drifting.

## Evaluation philosophy

- every AI capability must be measurable
- offline evaluation is required before launch
- production monitoring is required after launch
- high-impact recommendations require human-review pathways
- regressions block promotion
- explainability quality matters as much as output completion

## Required artifacts for every AI capability

Each capability spec should define:

- task definition and intended user outcome
- golden datasets
- offline benchmarks
- human review rubric
- acceptance thresholds
- regression tests
- safety and hallucination checks
- production monitoring plan
- rollback plan

## Core evaluation loop

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

## Common metrics

Use the relevant subset for each capability:

- recommendation quality
- match quality
- false positive rate
- false negative rate
- user acceptance rate
- user satisfaction
- time saved
- classification accuracy
- explainability completeness
- hallucination rate

## Human review process

- sample outputs from both offline datasets and production traffic
- review whether the recommendation is correct, useful, evidence-backed, and safe
- verify that the explanation answers why, based on what evidence, how confident, and what changes if ignored
- compare reviewer findings against automated metrics before promotion decisions

## Safety and hallucination policy

- unsupported claims must be blocked, not softened with uncertain language
- evidence-backed features must preserve provenance to user data or approved public signals
- high-impact actions should degrade to review-required mode when confidence is low
- safety regressions should stop rollout even when task-completion metrics look good

## Production monitoring

Track ongoing quality using:

- accepted versus rejected recommendations
- applied versus ignored opportunities
- interview and offer outcomes where available
- misclassification reports
- user feedback signals
- latency and failure rates

## Promotion rule

No AI capability is production-ready until:

- offline thresholds are met
- regression checks pass
- human review is acceptable
- hallucination and safety checks pass
- production monitoring is wired before rollout

## Initial capability scorecards

The first capability scorecards should cover:

- job matching
- resume intelligence
- recruiter intelligence
- interview intelligence
- market intelligence

## Resume Intelligence baseline scorecard

The Resume Intelligence offline scorecard should evaluate at least:

- selection confidence
- requirement coverage
- supported evidence coverage
- evidence integrity for blocked versus supported claims
- change explainability completeness
- ATS score delta before and after
- time to reviewable draft

Representative benchmark cases must include:

- strong existing resume with few or no changes
- resume with supported missing evidence that can be strengthened safely
- job asking for skills the user does not possess
