# UI Page Guardrails

Use this checklist before shipping any new user or admin page.

The recent UI fixes exposed the same failures multiple times:

- duplicate headers or repeated page titles
- oversized summary cards that waste the first screen
- cards without enough internal padding
- blank pages while data is loading
- large datasets rendered all at once
- pages fetching full records just to show one count

New pages should not repeat those mistakes.

## Core page rules

### 1. One page header only

Every page gets one primary title block.

Allowed:

- global app header
- one in-page `PageHeader`

Not allowed:

- a second hero that repeats the same title
- duplicate subtitles that restate the same purpose

If the page needs quick stats, place them in a compact summary row under the main header instead of creating a second hero.

### 2. Above-the-fold density matters

The first screen should show useful content immediately.

Targets:

- at least 2 to 3 real rows, cards, or records should be visible without scrolling on desktop
- filters should not consume a full screen by themselves
- avoid giant whitespace gaps between header, filters, and content

### 3. Prefer compact summary rows over giant metric blocks

For inventory-style pages, do not use oversized single-number cards unless the page is a dashboard KPI surface.

Prefer:

- `94 jobs • 1 saved • updated 2 min ago`
- `35 companies • 22 enabled • 18 monitored`

Use large metric cards only when multiple KPIs together are the main point of the page.

### 4. Every card must have safe internal padding

Text, badges, inputs, and tables must never touch card edges.

Default rules:

- card headers need horizontal padding
- card bodies need separate body padding
- tables inside cards need breathing room before the first row
- mobile layouts must keep padding, not collapse to edge-to-edge text

If a page uses custom card styling, verify header padding and body padding separately.

### 5. Loading state is required

Async pages must never appear empty while waiting for data.

Required:

- skeletons, loading rows, or compact loading cards on first paint
- explicit loading text for refresh actions
- no blank white cards with only changing subtitles

Use skeleton placeholders for:

- tables
- activity feeds
- metric summaries
- form-heavy admin pages

### 6. Empty state and error state are separate from loading state

Do not reuse a blank page for all three conditions.

Each page should distinguish:

- loading
- empty but healthy
- error

This prevents confusing "nothing loaded" with "no data exists."

## Data and performance rules

### 7. Never load thousands of rows by default

For large inventories, fetch a limited batch first.

Default behavior:

- initial load: 20 items
- load more on demand or near-scroll
- show total count separately

Examples:

- jobs
- alerts
- logs
- company inventories

### 8. Do not fetch full datasets just to compute summary counts

If the UI only needs a number, fetch a number or use an aggregated workspace payload.

Bad pattern:

- fetch every job record to show company job count

Preferred pattern:

- use aggregated inventory counts
- use summary endpoints
- use server-side totals

### 9. Filtering and sorting should happen server-side for large pages

Once a page represents operational inventory, do not assume full client-side filtering is acceptable.

Large-data pages should support:

- query
- decision/status filters
- freshness filters
- sort order
- paged responses with `total`, `limit`, `offset`, and `has_more`

### 10. Page payloads should match what the page renders

Do not send hundreds or thousands of records if the page only renders five.

Examples:

- dashboard "recent jobs" panels should receive a small slice
- summary cards should use aggregated counts
- detail drawers can fetch deeper data only when opened

## Layout and interaction rules

### 11. Filters belong in one toolbar when possible

For list pages, combine related controls into one compact toolbar.

Typical pattern:

- search
- status/decision
- freshness
- minimum score
- sort

Avoid stacking large single-purpose filter cards unless the workflow truly requires it.

### 12. Information hierarchy must be scannable

Each list row or card should answer, in order:

1. what is it
2. why it matters
3. how fresh it is
4. what action to take

For jobs, this usually means:

- company
- role title
- score or recommendation
- freshness
- key tags
- apply or save action

### 13. Admin pages should optimize for operations, not decoration

Admin surfaces should be denser and more summary-driven than user pages.

That means:

- counts instead of full datasets when possible
- fast scan tables
- compact summary strips
- clear loading and refresh states

## Reusable implementation guidance

### 14. Prefer shared layout primitives

Use shared building blocks first:

- `AppPage`
- `PageHeader`
- `PageSection`
- `AppCard`
- `AppGrid`
- `AppEmptyState`
- `AppSkeleton`

Do not hand-roll a page shell unless the layout is truly unique.

### 15. Responsive behavior is part of the definition of done

Before merging, verify:

- desktop spacing
- tablet wrapping
- mobile card padding
- toolbar stacking
- button overflow
- table overflow behavior

## New page definition of done

A new page is not ready until all of these are true:

- one page title only
- no text touches card edges
- loading, empty, and error states are distinct
- large lists are paged or incrementally loaded
- summary numbers do not require full-record fetches
- at least 2 to 3 meaningful content items are visible above the fold on desktop
- filters are compact and readable
- mobile spacing still looks intentional

## Review checklist for PRs

Ask these questions before approving any new page:

1. Is the page repeating a title or hero that already exists?
2. Can the user see real content immediately without scrolling too far?
3. Are cards padded correctly on both desktop and mobile?
4. Does the page show a real loading state?
5. Is the page loading more data than it actually renders?
6. Are totals and counts computed efficiently?
7. If the dataset grows 10x, will the page still feel fast?

If any answer is "no", the page needs another pass before merge.
