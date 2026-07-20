# Connector Checklist

Use this checklist every time a new connector is proposed, implemented, or promoted.

This exists to prevent the same failures from repeating:

- adding a company before the source is actually pollable
- registering a connector without wiring runtime collection
- shipping admin metadata that hides the real blocker
- missing tests for catalog, registry, and validation state
- calling a connector `live` when the public source is still unstable

## 1. Confirm the source is real before writing code

Do this first.

- identify the official public source URL
- identify whether the source is an ATS feed, company API, or company careers frontend
- confirm whether the source is public and unauthenticated
- check for blockers:
  - login requirements
  - API keys
  - bot protection
  - AWS WAF or JavaScript challenge pages
  - CAPTCHA
  - geo restrictions
  - unstable client-only rendering
- confirm whether jobs can be fetched in a repeatable backend-safe way

Required outcome:

- `live candidate`: stable unauthenticated source exists
- `planned`: source is not safely pollable yet

If the source is blocked, document the blocker explicitly with a concrete date.

## 2. Decide the connector status honestly

Do not hide a blocked source under a generic connector.

Use these rules:

- `live`: production-grade public feed with high confidence
- `beta`: implemented and working, but still being watched for edge cases
- `planned`: no safe runtime collector yet

Never mark a connector `live` or `beta` if:

- the source still needs browser-executed challenge solving
- the public API is undocumented and not yet validated
- admin validation cannot perform a real sample fetch

## 3. Add connector metadata

If the source deserves its own connector identity, add all of these:

- connector definition in `backend/app/connectors/registry.py`
- connector display label in any summary/label mapping
- company catalog entry in `backend/app/company_catalog_defaults.py`
- implemented connector sets only if the runtime really supports it

Check:

- key naming is consistent
- display name is user-facing and clean
- layer is correct: `official_ats` or `company_careers`
- pagination mode is accurate
- rate limit is conservative
- rollout stage matches reality

## 4. Implement the collector only after source validation

New collector files belong in `backend/app/connectors/`.

Each collector should support:

- stable request headers and timeout handling
- normalized job records
- deterministic connector keys
- apply URL extraction
- published timestamp parsing
- location normalization
- partial inventory reporting
- cursor support if feasible

At minimum, verify the collector returns:

- `jobs`
- `requests_made`
- `pages_scanned`
- `expected_pages`
- `inventory_complete`
- `partial_reason`

## 5. Wire runtime orchestration

A connector is not finished when the collector file exists.

Wire all runtime surfaces:

- import in `backend/app/market_scout.py`
- connector runner mapping in `_connector_runner`
- company-specific runner function if needed
- due-company validation rules in `_due_companies_by_connector`
- connector key handling in summary and run metadata

If runtime does not support it yet, keep the connector `planned`.

## 6. Wire admin validation and monitoring

Admin must reflect the truth of the source.

Add or update:

- `RUNTIME_SUPPORTED_CONNECTORS` in `backend/app/services/admin_connectors.py` only for actually runnable connectors
- connector-specific validation path if implemented
- connector-specific blocker message if planned
- production readiness checks
- workspace rows and labels if needed

Rule:

- generic "planned" is not enough when there is a concrete blocker
- say exactly why it cannot be polled yet

## 7. Update catalog and user-facing summaries

If the connector appears in product surfaces, make sure naming is consistent.

Check:

- source labels in `backend/app/repositories/postgres.py`
- catalog-generated company defaults
- connector counts and summaries
- admin connector tables
- any health/status views

Do not add the company as enabled by default unless the connector is genuinely runnable.

## 8. Add tests before calling it done

Every connector change needs targeted tests.

Required test coverage:

- connector registry exposure
- catalog/default company state
- admin validation result
- collector-specific parsing tests if implemented
- market scout wiring tests if implemented

Minimum files to consider:

- `backend/tests/test_runtime_infrastructure.py`
- `backend/tests/test_catalog.py`
- `backend/tests/test_admin_connectors.py`
- `backend/tests/test_market_scout.py`
- `backend/tests/test_<connector>_connector.py`

## 9. Run the verification commands

Before merge, run the smallest relevant set at minimum:

```bash
cd backend
python -m unittest tests.test_catalog tests.test_runtime_infrastructure tests.test_admin_connectors -q
python -m py_compile app/connectors/registry.py app/company_catalog_defaults.py app/services/admin_connectors.py app/repositories/postgres.py
```

If a new collector was added, also run its direct tests.

## 10. Document the decision

For every new connector, leave a short note in the PR or task record:

- source checked
- official URL
- status chosen: `live`, `beta`, or `planned`
- main blocker if not runnable
- date verified
- tests run

Example:

```text
IBM Careers
- Official source: https://www.ibm.com/careers/search
- Status: planned
- Verified: July 20, 2026
- Blocker: public careers flow returns AWS WAF JavaScript challenge
- Result: added as explicit planned connector, not runtime-enabled
```

## 11. Promotion checklist for planned to beta/live

When revisiting a planned connector, do not just flip metadata.

Re-check:

- public source still exists
- blocker is gone
- request shape is still valid
- validation can fetch a real sample job
- runtime collection works end-to-end
- counts and labels still render correctly

## PR checklist

Before approving a connector PR, answer all of these:

1. Did we verify the official public source first?
2. Is the connector status honest?
3. Is the runtime actually wired if the connector is marked runnable?
4. Will admin show the real blocker if it is still planned?
5. Did we avoid enabling the company by default unless it truly works?
6. Are registry, catalog, labels, and tests all updated together?
7. If this source breaks tomorrow, will the product fail transparently instead of silently lying?

If any answer is `no`, the connector is not ready.
