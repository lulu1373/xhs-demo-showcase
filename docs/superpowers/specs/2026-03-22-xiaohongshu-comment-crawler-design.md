# Xiaohongshu Comment Crawler Design

**Goal:** Build a Xiaohongshu crawling skill that can discover target notes from keyword search or direct note input, then capture first-level and second-level comments as completely as practical with resumable jobs and completeness verification.

**Status:** Approved at design level by user on 2026-03-22. Final completeness target is "best-effort full capture with automatic resume and explicit missing-data reporting", not zero-failure guarantees.

## Problem Statement

The user wants a reusable skill for Xiaohongshu that:

- Accepts a keyword and searches `https://www.xiaohongshu.com/explore`
- Sorts results by "most comments"
- Selects the top 10 notes
- Enters each note and captures all first-level and second-level comments
- Expands comments automatically without manual clicking
- Can also accept direct `note_url` or `note_id` inputs for targeted backfill
- Minimizes security-limit failures and supports resumable recovery

The user explicitly does **not** accept a workflow that silently loses comments or depends on manual comment expansion.

## Constraints

- Xiaohongshu uses dynamic anti-abuse controls, login checks, and changing client behavior.
- The system cannot guarantee literal zero failure probability.
- The design must prefer durability, resumability, and visibility of incompleteness over raw speed.
- The user accepts reuse of a dedicated logged-in Chrome profile.
- First version should focus on Xiaohongshu web discovery plus comment capture, not native desktop app automation.

## Recommended Approach

Use a hybrid architecture:

1. Browser automation for light discovery only
2. Logged-in session reuse for authenticated requests
3. Comment extraction through paginated comment APIs where available
4. Local job state persistence for restart and verification

This is preferred over pure DOM scraping because it reduces UI churn, reduces repeated heavy scrolling, and gives cleaner pagination control for first-level and second-level comments.

## Alternatives Considered

### Option A: Pure Playwright DOM scraping

Use Playwright to search, open notes, scroll the comments panel, click "show more replies", and extract visible comments from the DOM.

Pros:

- Straightforward mental model
- No API reverse engineering required

Cons:

- Highest instability
- Slowest runtime
- Most likely to trigger limits
- Hardest to verify completeness

### Option B: Hybrid browser discovery plus comment API capture

Use browser automation only for finding candidate notes, then fetch all comments through API pagination using the same authenticated session context.

Pros:

- Best balance of stability and completeness
- Easier resume behavior
- Easier duplicate detection and page-state validation
- Avoids repeatedly stressing the visual comment UI

Cons:

- Requires maintenance of request headers/cookies/session handling
- Requires fallback logic when one request path fails

### Option C: Fully API-driven search plus comments

Use APIs for both discovery and comment extraction.

Pros:

- Fastest in theory

Cons:

- Search path is likely to be more brittle
- Harder to bootstrap reliably in v1
- More likely to break unexpectedly

## Decision

Implement **Option B** for v1.

## User-Facing Capabilities

The skill should support two entry paths:

1. Search path
   - Search by keyword
   - Sort by "most comments"
   - Collect the top N notes, default 10
   - Crawl all comments for each note

2. Direct note path
   - Accept one or more `note_url` or `note_id` values
   - Crawl comments directly without search
   - Useful for backfill or retry workflows

## Proposed Command Surface

The first version should expose a small, task-oriented interface:

- `search-top-notes <keyword> --limit 10 --sort most_comments`
- `crawl-note-comments <note_url_or_id>`
- `crawl-batch <file>`
- `resume-job <job_id>`
- `verify-job <job_id>`

These commands may be exposed through a skill wrapper, a Python CLI, or both. The CLI should exist even if the skill is the main user interface.

## Architecture

### 1. Discovery Layer

Responsibility:

- Open Xiaohongshu web search
- Reuse a dedicated Chrome profile with persisted login
- Submit keyword
- Set the sort order to "most comments"
- Collect note metadata for the top N notes

Outputs:

- `note_id`
- note URL
- title if present
- author if present
- visible comment count if present
- rank position

This layer should remain intentionally shallow:

- No deep search-result pagination in v1
- No aggressive scrolling through many result pages
- No repeated refresh loops

### 2. Comment Capture Layer

Responsibility:

- Use authenticated session context to request first-level comments page by page
- For each first-level comment, request second-level comments page by page
- Normalize each comment into a stable internal schema

Preferred order:

1. Web comment API path
2. App-style comment API path using stored header templates
3. DOM fallback only for metadata or emergency debugging, not primary extraction

### 3. Job State Layer

Responsibility:

- Persist overall job progress
- Persist per-note pagination state
- Persist partial results incrementally
- Allow safe process interruption and later resume

The crawler must be able to stop after any completed request and continue later without discarding already collected data.

### 4. Verification Layer

Responsibility:

- Detect incomplete notes
- Detect duplicate page loops
- Detect suspicious early termination
- Produce note-level and job-level completeness summaries

## Data Model

### Job State

Each job should have a durable record containing:

- `job_id`
- `mode`: `search` or `direct`
- input payload
- creation time
- current status: `running`, `paused`, `completed`, `needs_review`, `failed`
- target note list
- current note pointer
- aggregate counters
- last error

### Note State

Each note should track:

- `note_id`
- URL
- note metadata
- discovery rank if applicable
- expected visible comment count if available
- top-comment cursor state
- sub-comment cursor state per parent comment
- fetched top-level count
- fetched sub-comment count
- dedupe fingerprint set or equivalent persisted summary
- note status: `pending`, `running`, `complete`, `partial`, `failed`
- retry count
- verification summary

### Comment Record

The normalized comment record should contain at least:

- `note_id`
- `comment_id`
- `parent_comment_id`
- `level`
- `nickname`
- `user_id`
- `avatar`
- `comment`
- `like_count`
- `reply_to_nickname`
- `create_time`
- `create_time_iso`
- `ip_location`
- `raw`

## Completeness Strategy

The goal is not to claim completeness by assumption. The crawler must actively test for it.

### Runtime checks

During fetching:

- Stop only on natural pagination termination
- Detect repeated cursor values
- Detect empty pages after non-empty pages
- Detect suspicious cursor rewinds
- Detect abnormal result collapse after transient errors

### Result checks

After each note:

- Compare fetched counts with visible note counts when available
- Flag mismatches beyond a tolerance threshold
- Flag notes where top-level comments fetched are unexpectedly low
- Flag notes where sub-comments terminate too early relative to known counts

### Recovery checks

For notes marked `partial`:

- Retry the note in a second pass
- Resume from last stable cursor where possible
- If still incomplete, persist an explicit reason code

Possible reason codes:

- `rate_limited`
- `login_invalid`
- `captcha_or_security_check`
- `api_shape_changed`
- `cursor_inconsistent`
- `count_mismatch_unresolved`

## Anti-Abuse Strategy

The design should reduce risk rather than pretending to eliminate it.

### Required practices

- Use a dedicated Chrome profile that stays logged in
- Reuse the same browser identity rather than reauthenticating repeatedly
- Keep browser discovery shallow
- Process notes serially in v1
- Add delay and jitter between requests
- Save after every note and at intermediate pagination checkpoints
- Pause on security events instead of hammering retries
- Resume later from saved state

### Explicit non-goals

V1 should not include:

- captcha solving
- forced bypass of security checks
- proxy rotation systems
- concurrent multi-account distribution
- native desktop app UI automation

## Error Handling

Expected failure modes:

- browser session expired
- comment endpoint returns auth error
- security challenge interrupts browsing
- endpoint schema changes
- note becomes unavailable
- comments are deleted or hidden between pages

Handling policy:

- Fail one note without failing the whole job
- Record note-local errors
- Mark note status conservatively
- Continue to next note where safe
- Keep final job output transparent about what is complete vs partial

## Output Artifacts

Each job should produce:

- job manifest JSON
- note manifest JSON files
- consolidated comments JSON
- optional CSV export
- verification report JSON
- human-readable summary report

Suggested directory shape:

```text
output/xhs-comment-jobs/<job_id>/
  job.json
  notes/
    <note_id>.json
    <note_id>.comments.json
  merged_comments.json
  merged_comments.csv
  verification.json
  summary.md
```

## First Version Scope

V1 includes:

- keyword search entry
- direct note entry
- "most comments" sort handling
- top 10 note discovery
- first-level comment pagination
- second-level comment pagination
- resumable job state
- completeness verification
- JSON export

V1 excludes:

- multiple keyword campaigns in one run
- scheduled recurring jobs
- desktop app automation
- auto-captcha handling
- unlimited search-result pagination
- claims of guaranteed zero-failure extraction

## Testing Strategy

Testing should cover:

- note ID parsing
- cursor pagination logic
- duplicate cursor detection
- merge and dedupe behavior
- job resume from interrupted state
- note verification outcomes
- serialization of manifests and output files

Manual verification should cover:

- browser search workflow with logged-in profile
- one low-comment note
- one high-comment note with second-level replies
- forced interruption followed by resume
- visible mismatch path producing `partial`

## Open Implementation Notes

- Existing local scripts already cover parts of the required behavior and should be reused where possible, especially comment export and captured header flows.
- The first implementation pass should unify those scripts behind one coherent job model instead of adding yet another standalone script.
- DOM scraping should remain a debugging aid, not the main completeness path.

## Success Criteria

The first release is successful if it can:

- discover the top 10 notes for a keyword from Xiaohongshu web search
- crawl comments for each discovered note or directly supplied note input
- capture first-level and second-level comments through resumable pagination
- pause and resume without losing prior results
- mark each note as `complete`, `partial`, or `failed`
- produce output that makes missing data explicit instead of hidden
