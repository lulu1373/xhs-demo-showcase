# Xiaohongshu Comment Crawler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable Xiaohongshu comment crawler that discovers notes from the desktop app or direct note input, then captures first-level and second-level comments through app-side pagination with verification.

**Architecture:** Reuse the existing Xiaohongshu scripts as extraction backends, but move orchestration into a single job-driven CLI. Use a desktop-app discovery layer to identify target notes, a live-session capture layer to keep app headers fresh, and an app-comment pagination layer backed by persisted job state and verification.

**Tech Stack:** Python 3, standard library HTTP/JSON/CSV/path handling, existing Xiaohongshu scripts in this repo, desktop screenshot/automation helpers, Proxyman CLI export flow, app API capture

---

## File Structure

Planned files and responsibilities:

- Create: `/Users/lulu/AIWork/xhs_crawler/__init__.py`
  Purpose: Package marker for the crawler modules.
- Create: `/Users/lulu/AIWork/xhs_crawler/models.py`
  Purpose: Typed job, note, verification, and comment state helpers.
- Create: `/Users/lulu/AIWork/xhs_crawler/storage.py`
  Purpose: Read/write job manifests, note manifests, merged exports, and atomic checkpoint persistence.
- Create: `/Users/lulu/AIWork/xhs_crawler/normalize.py`
  Purpose: Centralize note ID parsing, timestamp conversion, comment normalization, and dedupe keys.
- Create: `/Users/lulu/AIWork/xhs_crawler/app_api.py`
  Purpose: Wrap the app-style comment API logic from `xhs_export_comments_app_api.py`.
- Create: `/Users/lulu/AIWork/xhs_crawler/session_capture.py`
  Purpose: Export fresh app traffic, extract reusable headers, and refresh session state when signatures expire.
- Create: `/Users/lulu/AIWork/xhs_crawler/app_discovery.py`
  Purpose: Attach to the desktop app, drive keyword search and sort selection, and collect the top note identifiers in ranked order.
- Create: `/Users/lulu/AIWork/xhs_crawler/verify.py`
  Purpose: Runtime anomaly checks, note completeness checks, and verification summaries.
- Create: `/Users/lulu/AIWork/xhs_crawler/runner.py`
  Purpose: Serial orchestration for jobs, retries, session refresh, resume, and progress updates.
- Create: `/Users/lulu/AIWork/xhs_comment_crawler.py`
  Purpose: Main CLI entry point exposing `discover-top-notes`, `crawl-note-comments`, `crawl-batch`, `resume-job`, and `verify-job`.
- Create: `/Users/lulu/AIWork/tests/test_xhs_normalize.py`
  Purpose: Unit tests for note ID parsing, timestamps, and normalization.
- Create: `/Users/lulu/AIWork/tests/test_xhs_storage.py`
  Purpose: Unit tests for manifest persistence and resume semantics.
- Create: `/Users/lulu/AIWork/tests/test_xhs_session_capture.py`
  Purpose: Unit tests for header extraction and refresh behavior.
- Create: `/Users/lulu/AIWork/tests/test_xhs_runner.py`
  Purpose: Unit tests for session refresh, pause/resume behavior, and note status updates.
- Modify: `/Users/lulu/AIWork/xhs_export_comments_app_api.py`
  Purpose: Extract reusable app API functions into library-safe helpers or import from the new module.
- Modify: `/Users/lulu/AIWork/parse_proxyman_har_xhs_comments.py`
  Purpose: Reuse or expose HAR parsing helpers for fresh app header extraction.
- Modify: `/Users/lulu/AIWork/watch_xhs_proxyman_cli.py`
  Purpose: Reuse or expose Proxyman export helpers for session capture.

## Task 1: Extract Shared Normalization Helpers

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/__init__.py`
- Create: `/Users/lulu/AIWork/xhs_crawler/normalize.py`
- Test: `/Users/lulu/AIWork/tests/test_xhs_normalize.py`

- [ ] **Step 1: Write the failing normalization tests**

```python
from xhs_crawler.normalize import normalize_note_id, format_ts_iso


def test_normalize_note_id_accepts_note_id():
    assert normalize_note_id("6919e2470000000005002ee1") == "6919e2470000000005002ee1"


def test_normalize_note_id_accepts_explore_url():
    url = "https://www.xiaohongshu.com/explore/6919e2470000000005002ee1"
    assert normalize_note_id(url) == "6919e2470000000005002ee1"


def test_format_ts_iso_handles_empty_values():
    assert format_ts_iso("") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_normalize.py -v`
Expected: FAIL with import errors because the package does not exist yet

- [ ] **Step 3: Write minimal implementation**

Implement `normalize_note_id`, `format_ts_iso`, and initial normalization helpers in `/Users/lulu/AIWork/xhs_crawler/normalize.py`. Add package marker in `/Users/lulu/AIWork/xhs_crawler/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_normalize.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/__init__.py xhs_crawler/normalize.py tests/test_xhs_normalize.py
git -C /Users/lulu/AIWork commit -m "feat: add xhs crawler normalization helpers"
```

## Task 2: Add Job and Note State Models

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/models.py`
- Test: `/Users/lulu/AIWork/tests/test_xhs_storage.py`

- [ ] **Step 1: Write the failing model/storage tests**

```python
from xhs_crawler.models import JobState, NoteState


def test_job_state_defaults_to_running():
    job = JobState(job_id="job-1", mode="direct", input_payload={})
    assert job.status == "running"


def test_note_state_defaults_to_pending():
    note = NoteState(note_id="6919e2470000000005002ee1")
    assert note.status == "pending"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_storage.py -v`
Expected: FAIL because the model module does not exist

- [ ] **Step 3: Write minimal implementation**

Implement serializable state containers for jobs and notes, including:

- status fields
- retry counters
- cursor fields
- verification placeholders

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_storage.py -v`
Expected: PASS for the current model assertions

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/models.py tests/test_xhs_storage.py
git -C /Users/lulu/AIWork commit -m "feat: add xhs crawler state models"
```

## Task 3: Implement Persistent Storage and Checkpointing

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/storage.py`
- Modify: `/Users/lulu/AIWork/tests/test_xhs_storage.py`

- [ ] **Step 1: Extend tests for manifest persistence**

```python
from pathlib import Path

from xhs_crawler.models import JobState
from xhs_crawler.storage import save_job_state, load_job_state


def test_save_and_load_job_state(tmp_path: Path):
    job = JobState(job_id="job-1", mode="direct", input_payload={"notes": ["n1"]})
    save_job_state(tmp_path, job)
    loaded = load_job_state(tmp_path / "job.json")
    assert loaded.job_id == "job-1"
    assert loaded.input_payload["notes"] == ["n1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_storage.py -v`
Expected: FAIL because storage helpers do not exist

- [ ] **Step 3: Write minimal implementation**

Implement:

- output directory layout creation
- atomic JSON save helpers
- load/save for job and note manifests
- merged comments JSON/CSV writing

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/storage.py tests/test_xhs_storage.py
git -C /Users/lulu/AIWork commit -m "feat: add xhs crawler persistent storage"
```

## Task 4: Refactor the App Comment API into a Reusable Adapter

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/app_api.py`
- Modify: `/Users/lulu/AIWork/xhs_export_comments_app_api.py`
- Test: `/Users/lulu/AIWork/tests/test_xhs_runner.py`

- [ ] **Step 1: Add the failing app adapter tests**

```python
from xhs_crawler.app_api import sanitize_app_headers


def test_sanitize_app_headers_sets_host_when_missing():
    headers = sanitize_app_headers({"Accept": "*/*"})
    assert headers["Host"] == "edith.xiaohongshu.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: FAIL because the app adapter module does not exist

- [ ] **Step 3: Write minimal implementation**

Move or copy the reusable pieces from `/Users/lulu/AIWork/xhs_export_comments_app_api.py` into `/Users/lulu/AIWork/xhs_crawler/app_api.py`:

- header sanitization
- request helper
- top-level pagination
- sub-comment pagination
- normalized record emission

Keep `/Users/lulu/AIWork/xhs_export_comments_app_api.py` runnable by importing from the new adapter where practical.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: PASS for the adapter assertion

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/app_api.py xhs_export_comments_app_api.py tests/test_xhs_runner.py
git -C /Users/lulu/AIWork commit -m "feat: add reusable xhs app comment adapter"
```

## Task 5: Add Session Capture and Header Refresh

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/session_capture.py`
- Modify: `/Users/lulu/AIWork/parse_proxyman_har_xhs_comments.py`
- Modify: `/Users/lulu/AIWork/watch_xhs_proxyman_cli.py`
- Test: `/Users/lulu/AIWork/tests/test_xhs_session_capture.py`

- [ ] **Step 1: Write the failing session-capture tests**

```python
from xhs_crawler.session_capture import extract_comment_headers


def test_extract_comment_headers_reads_latest_comment_request(sample_har):
    headers = extract_comment_headers(sample_har)
    assert headers["Host"] == "edith.xiaohongshu.com"
    assert "shield" in headers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_session_capture.py -v`
Expected: FAIL because the session capture module does not exist

- [ ] **Step 3: Write minimal implementation**

Implement helpers that:

- clear Proxyman sessions
- export recent app traffic
- parse HAR for comment-list and sub-comment requests
- extract a fresh reusable header set
- return a structured refresh result with timestamp and source file

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_session_capture.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/session_capture.py parse_proxyman_har_xhs_comments.py watch_xhs_proxyman_cli.py tests/test_xhs_session_capture.py
git -C /Users/lulu/AIWork commit -m "feat: add xhs app session capture helpers"
```

## Task 6: Build Desktop App Discovery

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/app_discovery.py`
- Modify: `/Users/lulu/AIWork/tests/test_xhs_runner.py`

- [ ] **Step 1: Add the failing discovery tests**

```python
from xhs_crawler.app_discovery import normalize_ranked_note


def test_normalize_ranked_note_preserves_rank():
    note = normalize_ranked_note({"note_id": "n1", "title": "t"}, rank=3)
    assert note["rank"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: FAIL because the discovery module does not exist

- [ ] **Step 3: Write minimal implementation**

Implement desktop-app discovery helpers that:

- attach to the running app
- capture window bounds and screenshots
- click known search and sort targets
- collect the first 10 ranked note identifiers
- output normalized note records

Keep app control logic isolated so the runner can replace it later without rewriting pagination code.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: PASS for the discovery assertion

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/app_discovery.py tests/test_xhs_runner.py
git -C /Users/lulu/AIWork commit -m "feat: add xhs desktop app discovery helpers"
```

## Task 7: Add Verification Helpers

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/verify.py`
- Modify: `/Users/lulu/AIWork/tests/test_xhs_runner.py`

- [ ] **Step 1: Extend tests for note completeness**

```python
from xhs_crawler.verify import summarize_note_status


def test_summarize_note_status_marks_partial_on_large_gap():
    summary = summarize_note_status(expected_comments=1000, fetched_comments=200, errors=[])
    assert summary["status"] == "partial"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: FAIL because the verify module does not exist

- [ ] **Step 3: Write minimal implementation**

Implement:

- duplicate cursor detection
- suspicious early-stop detection
- status summary generation
- reason-code selection for partial and failed notes

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/verify.py tests/test_xhs_runner.py
git -C /Users/lulu/AIWork commit -m "feat: add xhs crawler verification helpers"
```

## Task 8: Build the Job Runner

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/runner.py`
- Modify: `/Users/lulu/AIWork/tests/test_xhs_runner.py`

- [ ] **Step 1: Extend tests for refresh and resume**

```python
from xhs_crawler.runner import should_refresh_headers


def test_should_refresh_headers_on_signature_error():
    assert should_refresh_headers({"error_code": "signature_expired"}) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: FAIL because the runner module does not exist

- [ ] **Step 3: Write minimal implementation**

Implement serial orchestration that:

- creates jobs from discovery or direct input
- fetches top-level and sub-level comments note by note
- refreshes session headers on signature failures
- checkpoints progress after every stable pagination step
- marks note status using the verification layer

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/runner.py tests/test_xhs_runner.py
git -C /Users/lulu/AIWork commit -m "feat: add xhs crawler job runner"
```

## Task 9: Add the CLI Entry Point

**Files:**
- Create: `/Users/lulu/AIWork/xhs_comment_crawler.py`
- Modify: `/Users/lulu/AIWork/tests/test_xhs_runner.py`

- [ ] **Step 1: Add the failing CLI tests**

```python
from xhs_comment_crawler import build_parser


def test_build_parser_supports_discover_top_notes():
    parser = build_parser()
    args = parser.parse_args(["discover-top-notes", "亲子关系"])
    assert args.command == "discover-top-notes"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: FAIL because the CLI entry point does not exist

- [ ] **Step 3: Write minimal implementation**

Implement the CLI with commands for:

- app discovery by keyword
- direct note crawl
- batch crawl
- resume job
- verify job

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_comment_crawler.py tests/test_xhs_runner.py
git -C /Users/lulu/AIWork commit -m "feat: add xhs crawler CLI"
```

## Task 10: Manual End-to-End Shakeout

**Files:**
- Modify: `/Users/lulu/AIWork/docs/superpowers/plans/2026-03-22-xiaohongshu-comment-crawler.md`

- [ ] **Step 1: Run a direct-note smoke test**

Run: `python /Users/lulu/AIWork/xhs_comment_crawler.py crawl-note-comments 66548ea90000000005006e41`
Expected: Job starts, captures fresh headers if needed, and writes note output under `output/xhs-comment-jobs/<job_id>/`

- [ ] **Step 2: Run a keyword discovery test**

Run: `python /Users/lulu/AIWork/xhs_comment_crawler.py discover-top-notes 亲子关系 --limit 10`
Expected: The crawler attaches to the desktop app, collects 10 ranked notes, and writes a discovery manifest

- [ ] **Step 3: Run a full job test**

Run: `python /Users/lulu/AIWork/xhs_comment_crawler.py crawl-batch output/xhs-comment-jobs/<job_id>/notes.txt`
Expected: The crawler runs notes serially, checkpoints state, and writes merged JSON output

- [ ] **Step 4: Verify output completeness**

Run: `python /Users/lulu/AIWork/xhs_comment_crawler.py verify-job <job_id>`
Expected: A verification report is written, with each note marked `complete`, `partial`, or `failed`

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add docs/superpowers/plans/2026-03-22-xiaohongshu-comment-crawler.md
git -C /Users/lulu/AIWork commit -m "docs: update xhs crawler manual verification steps"
```
