# Xiaohongshu Comment Crawler Design

**Goal:** Build a Xiaohongshu crawler that automatically finds target notes and captures first-level and second-level comments as completely as practical, with resumable execution and explicit completeness reporting.

**Status:** Revised on 2026-03-23 after scope correction from web-first discovery to app-first capture. Final completeness target remains "best-effort full capture with automatic resume and explicit missing-data reporting", not zero-failure guarantees.

## Problem Statement

The user wants a reusable workflow that:

- Searches a keyword in the Xiaohongshu desktop app
- Chooses the equivalent of "most comments"
- Selects the top 10 notes in ranked order
- Enters each note one by one
- Captures all first-level and second-level comments
- Does not require the user to manually click, scroll, or expand comments
- Does not silently undercount or present partial data as complete

The user explicitly prioritizes near-full comment capture over the choice of discovery surface. If app-side interface automation is needed only to identify target notes, that is acceptable. The primary requirement is that comment extraction itself must use the route most likely to reach full pagination.

## Constraints

- Xiaohongshu uses dynamic anti-abuse controls, login checks, and changing request signatures.
- The system cannot guarantee literal zero failure probability.
- The design must prefer durability, resumability, and visibility of incompleteness over raw speed.
- The user does not want to participate in the run once it starts.
- Native desktop app automation is harder to stabilize than browser DOM automation because accessibility exposure is weak and some controls may require coordinate-driven interaction.
- Web DOM comment expansion has already been shown to underexpose large comment trees and is therefore not acceptable as the primary comment-capture path.

## Recommended Approach

Use an app-first hybrid architecture:

1. Native app automation only for finding target notes
2. Fresh app-session request capture for authenticated comment traffic
3. Direct comment extraction through paginated app APIs
4. Local job state persistence for restart and verification

This is preferred over DOM scraping because the desktop app shows higher visible comment counts than the web DOM exposes, while API pagination gives better control over first-level and second-level comment coverage.

## Alternatives Considered

### Option A: Continue with web DOM expansion

Use browser automation to search, open notes, scroll the comments panel, click "show more replies", and extract visible comments from the DOM.

Pros:

- Straightforward mental model
- No request-signature maintenance

Cons:

- Already proven incomplete on high-comment notes
- Slowest runtime
- Weakest completeness guarantees
- Not acceptable for the user's target

### Option B: Native app discovery plus app API comment capture

Use the desktop app to search and identify target notes, then capture fresh authenticated request context from the running app and fetch all comments through paginated app endpoints.

Pros:

- Best match to the user's observed comment totals
- Most likely to support full first-level and second-level pagination
- Easier to detect and retry partial runs
- Avoids relying on the app UI for repeated comment expansion

Cons:

- Requires fresh signed headers from live app traffic
- Requires more operational care around anti-abuse events
- App-side UI automation may need screenshot or coordinate based fallbacks

### Option C: Reverse web signatures and use web APIs only

Use web-side discovery and web comment APIs after reproducing request signing.

Pros:

- Potentially cleaner automation surface than the desktop app
- Less dependency on screenshot-driven desktop control

Cons:

- Higher reverse-engineering cost
- Current evidence suggests web-side comment exposure is less trustworthy for this use case
- Not the fastest path to a practical v1

## Decision

Implement **Option B** for v1.

## User-Facing Capabilities

The workflow should support two entry paths:

1. Keyword discovery path
   - Search by keyword in the desktop app
   - Choose the equivalent of "most comments"
   - Collect the top N notes, default 10
   - Crawl all comments for each note

2. Direct note path
   - Accept one or more `note_url` or `note_id` values
   - Crawl comments directly without discovery
   - Useful for backfill or retry workflows

The keyword path is the main user scenario. The direct note path is retained because it is operationally useful when a note must be retried or backfilled without rediscovery.

## Proposed Command Surface

The first version should expose a small, task-oriented interface:

- `discover-top-notes <keyword> --limit 10 --sort most_comments`
- `crawl-note-comments <note_url_or_id>`
- `crawl-batch <file>`
- `resume-job <job_id>`
- `verify-job <job_id>`

These commands may be exposed through a skill wrapper, a Python CLI, or both. The CLI should exist even if the skill is the main user interface.

## Architecture

### 1. Discovery Layer

Responsibility:

- Launch or attach to the Xiaohongshu desktop app
- Search the keyword inside the app
- Select the "most comments" sort equivalent
- Collect metadata for the top N notes
- Preserve ranked order so notes are crawled one by one

Outputs:

- `note_id`
- note URL if derivable
- title if present
- author if present
- visible comment count if present
- rank position

This layer should remain intentionally shallow:

- No deep result pagination in v1
- No aggressive list scrolling beyond what is needed for the top 10
- No manual user intervention once the run starts

### 2. Session Capture Layer

Responsibility:

- Observe fresh comment-related app traffic from the running desktop app
- Extract current headers, cookies, and signed fields required for comment pagination
- Refresh those fields when signatures expire or the app rotates them

This layer exists because replaying stale app headers returns authorization or signature errors. The crawler therefore needs a current, runtime-derived request context rather than static templates.

### 3. Comment Capture Layer

Responsibility:

- Use current app-session context to request first-level comments page by page
- For each first-level comment, request second-level comments page by page
- Normalize each comment into a stable internal schema

Preferred order:

1. App comment API path with fresh live headers
2. App comment API retry with refreshed live headers
3. DOM fallback only for metadata checks or debugging, never as the primary completeness path

### 4. Job State Layer

Responsibility:

- Persist overall job progress
- Persist per-note pagination state
- Persist partial results incrementally
- Allow safe process interruption and later resume

The crawler must be able to stop after any completed request and continue later without discarding already collected data.

### 5. Verification Layer

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
- URL if known
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
- Refresh app-session headers before retry
- Resume from last stable cursor where possible
- If still incomplete, persist an explicit reason code

Possible reason codes:

- `rate_limited`
- `login_invalid`
- `captcha_or_security_check`
- `api_shape_changed`
- `cursor_inconsistent`
- `signature_expired`
- `count_mismatch_unresolved`

## Anti-Abuse Strategy

The design should reduce risk rather than pretending to eliminate it.

### Required practices

- Reuse a stable logged-in desktop app session
- Discover only the target top 10 notes rather than crawling broad result sets
- Process notes serially in v1
- Add delay and jitter between comment requests
- Save after every note and at intermediate pagination checkpoints
- Pause on security events instead of hammering retries
- Refresh request context from live app traffic when signatures expire
- Resume later from saved state

### Explicit non-goals

V1 should not include:

- captcha solving
- forced bypass of security checks
- proxy rotation systems
- concurrent multi-account distribution
- reliance on web DOM expansion as the main capture path

## Error Handling

Expected failure modes:

- desktop app session expired
- comment endpoint returns auth error
- signature fields expire mid-run
- security challenge interrupts app traffic
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

- desktop app keyword search entry
- direct note entry
- "most comments" sort handling
- top 10 note discovery
- fresh app request-context capture
- first-level comment pagination
- second-level comment pagination
- resumable job state
- completeness verification
- JSON export

V1 excludes:

- multiple keyword campaigns in one run
- scheduled recurring jobs
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
- header-refresh behavior after signature expiration

Manual verification should cover:

- desktop app search workflow
- app-side "most comments" selection
- one low-comment note
- one high-comment note with second-level replies
- forced interruption followed by resume
- visible mismatch path producing `partial`

## Open Implementation Notes

- Existing local scripts already cover parts of the required behavior and should be reused where possible, especially comment export, HAR parsing, and captured-header flows.
- The first implementation pass should unify those scripts behind one coherent job model instead of adding yet another standalone script.
- Native app automation should be treated as a discovery aid. Comment completeness should come from app API pagination rather than UI expansion.

## Success Criteria

The first release is successful if it can:

- discover the top 10 notes for a keyword from the Xiaohongshu desktop app
- crawl comments for each discovered note or directly supplied note input
- capture first-level and second-level comments through resumable app-side pagination
- refresh live request context when signatures expire
- pause and resume without losing prior results
- mark each note as `complete`, `partial`, or `failed`
- produce output that makes missing data explicit instead of hidden
