# Xiaohongshu Comment Crawler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable Xiaohongshu comment crawler that discovers notes from keyword search or direct note input, then captures first-level and second-level comments through a job-based workflow with verification.

**Architecture:** Reuse the existing Xiaohongshu scripts as extraction backends, but move orchestration into a single job-driven CLI. Use a shallow browser discovery layer to find note IDs, a comment-fetch layer with web/app API adapters, and a persisted job state model that supports resume and completeness checks.

**Tech Stack:** Python 3, standard library HTTP/JSON/CSV/path handling, existing Xiaohongshu scripts in this repo, Chrome profile reuse, optional browser automation layer

---

## File Structure

Planned files and responsibilities:

- Create: `/Users/lulu/AIWork/xhs_crawler/__init__.py`
  Purpose: Package marker for the new crawler modules.
- Create: `/Users/lulu/AIWork/xhs_crawler/models.py`
  Purpose: Typed job, note, verification, and comment state helpers.
- Create: `/Users/lulu/AIWork/xhs_crawler/storage.py`
  Purpose: Read/write job manifests, note manifests, merged exports, and atomic checkpoint persistence.
- Create: `/Users/lulu/AIWork/xhs_crawler/normalize.py`
  Purpose: Centralize note ID parsing, timestamp conversion, comment normalization, and dedupe keys.
- Create: `/Users/lulu/AIWork/xhs_crawler/web_api.py`
  Purpose: Wrap the existing web comment API logic from `xhs_export_comments.py`.
- Create: `/Users/lulu/AIWork/xhs_crawler/app_api.py`
  Purpose: Wrap the existing app-style comment API logic from `xhs_export_comments_app_api.py`.
- Create: `/Users/lulu/AIWork/xhs_crawler/discovery.py`
  Purpose: Discovery entry points, initially direct note input and a pluggable search-note workflow.
- Create: `/Users/lulu/AIWork/xhs_crawler/verify.py`
  Purpose: Runtime anomaly checks, note completeness checks, and verification summaries.
- Create: `/Users/lulu/AIWork/xhs_crawler/runner.py`
  Purpose: Serial orchestration for jobs, retries, resume, backend fallback, and progress updates.
- Create: `/Users/lulu/AIWork/xhs_comment_crawler.py`
  Purpose: Main CLI entry point exposing `search-top-notes`, `crawl-note-comments`, `crawl-batch`, `resume-job`, and `verify-job`.
- Create: `/Users/lulu/AIWork/tests/test_xhs_normalize.py`
  Purpose: Unit tests for note ID parsing, timestamps, and normalization.
- Create: `/Users/lulu/AIWork/tests/test_xhs_storage.py`
  Purpose: Unit tests for manifest persistence and resume semantics.
- Create: `/Users/lulu/AIWork/tests/test_xhs_verify.py`
  Purpose: Unit tests for completeness and anomaly detection.
- Create: `/Users/lulu/AIWork/tests/test_xhs_runner.py`
  Purpose: Unit tests for backend fallback, pause/resume behavior, and note status updates.
- Modify: `/Users/lulu/AIWork/xhs_export_comments.py`
  Purpose: Extract reusable web API functions into library-safe helpers or import from the new module.
- Modify: `/Users/lulu/AIWork/xhs_export_comments_app_api.py`
  Purpose: Extract reusable app API functions into library-safe helpers or import from the new module.
- Modify: `/Users/lulu/AIWork/xhs_export_comments_from_chrome.py`
  Purpose: Keep as debugging/fallback utility, but align normalization/output schema with the new package where useful.

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

## Task 4: Refactor the Web Comment API into a Reusable Adapter

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/web_api.py`
- Modify: `/Users/lulu/AIWork/xhs_export_comments.py`
- Test: `/Users/lulu/AIWork/tests/test_xhs_runner.py`

- [ ] **Step 1: Write the failing adapter tests**

```python
from xhs_crawler.web_api import build_web_headers


def test_build_web_headers_includes_cookie_and_referer():
    headers = build_web_headers("a=b", "https://www.xiaohongshu.com/explore/x")
    assert headers["Cookie"] == "a=b"
    assert headers["Referer"].startswith("https://www.xiaohongshu.com/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: FAIL because the adapter module does not exist

- [ ] **Step 3: Write minimal implementation**

Move or copy the reusable pieces from `/Users/lulu/AIWork/xhs_export_comments.py` into `/Users/lulu/AIWork/xhs_crawler/web_api.py`:

- header construction
- request helper
- top-level pagination
- sub-comment pagination
- normalized record emission

Keep `/Users/lulu/AIWork/xhs_export_comments.py` runnable by importing from the new adapter where practical.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: PASS for the web adapter assertion

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/web_api.py xhs_export_comments.py tests/test_xhs_runner.py
git -C /Users/lulu/AIWork commit -m "feat: add reusable xhs web comment adapter"
```

## Task 5: Refactor the App Comment API into a Reusable Adapter

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/app_api.py`
- Modify: `/Users/lulu/AIWork/xhs_export_comments_app_api.py`
- Modify: `/Users/lulu/AIWork/tests/test_xhs_runner.py`

- [ ] **Step 1: Add the failing app adapter tests**

```python
from xhs_crawler.app_api import sanitize_app_headers


def test_sanitize_app_headers_sets_host_when_missing():
    headers = sanitize_app_headers({"Accept": "*/*"})
    assert headers["Host"] == "edith.xiaohongshu.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: FAIL because the app adapter does not exist

- [ ] **Step 3: Write minimal implementation**

Move or copy the reusable app-request pieces from `/Users/lulu/AIWork/xhs_export_comments_app_api.py` into `/Users/lulu/AIWork/xhs_crawler/app_api.py`:

- header loading/sanitization
- request helpers
- top-level pagination
- second-level pagination
- normalized record emission

Keep `/Users/lulu/AIWork/xhs_export_comments_app_api.py` runnable by importing from the new adapter where practical.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/app_api.py xhs_export_comments_app_api.py tests/test_xhs_runner.py
git -C /Users/lulu/AIWork commit -m "feat: add reusable xhs app comment adapter"
```

## Task 6: Implement Verification Rules

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/verify.py`
- Create: `/Users/lulu/AIWork/tests/test_xhs_verify.py`

- [ ] **Step 1: Write the failing verification tests**

```python
from xhs_crawler.verify import detect_repeated_cursor_loop, summarize_note_verification


def test_detect_repeated_cursor_loop_when_cursor_repeats():
    assert detect_repeated_cursor_loop(["a", "b", "b"]) is True


def test_summarize_note_verification_marks_partial_on_mismatch():
    summary = summarize_note_verification(expected_visible_count=100, fetched_count=60)
    assert summary["status"] == "partial"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_verify.py -v`
Expected: FAIL because the verification module does not exist

- [ ] **Step 3: Write minimal implementation**

Implement:

- repeated cursor detection
- early termination heuristics
- visible-count mismatch evaluation
- reason-code generation

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_verify.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/verify.py tests/test_xhs_verify.py
git -C /Users/lulu/AIWork commit -m "feat: add xhs crawler verification rules"
```

## Task 7: Implement the Job Runner and Backend Fallback

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/runner.py`
- Modify: `/Users/lulu/AIWork/tests/test_xhs_runner.py`

- [ ] **Step 1: Write the failing runner tests**

```python
from xhs_crawler.runner import choose_backend_order


def test_choose_backend_order_prefers_web_then_app():
    assert choose_backend_order() == ["web", "app"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: FAIL because the runner does not exist

- [ ] **Step 3: Write minimal implementation**

Implement:

- serial note processing
- backend order selection
- web-to-app fallback
- note status updates
- retry counters
- checkpoint save after each note and safe pagination boundaries

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/runner.py tests/test_xhs_runner.py
git -C /Users/lulu/AIWork commit -m "feat: add xhs crawler job runner"
```

## Task 8: Implement Discovery Inputs

**Files:**
- Create: `/Users/lulu/AIWork/xhs_crawler/discovery.py`
- Modify: `/Users/lulu/AIWork/tests/test_xhs_runner.py`

- [ ] **Step 1: Write the failing discovery tests**

```python
from xhs_crawler.discovery import normalize_direct_note_inputs


def test_normalize_direct_note_inputs_accepts_note_urls():
    notes = normalize_direct_note_inputs([
        "https://www.xiaohongshu.com/explore/6919e2470000000005002ee1"
    ])
    assert notes == ["6919e2470000000005002ee1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: FAIL because the discovery module does not exist

- [ ] **Step 3: Write minimal implementation**

Implement:

- direct note input normalization
- search request placeholders and result schema
- search manifest generation for future browser-backed discovery

For v1, it is acceptable for `search-top-notes` to require a dedicated implementation stub if the browser search path is not yet fully automated, but the command contract and data shape must be in place.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_crawler/discovery.py tests/test_xhs_runner.py
git -C /Users/lulu/AIWork commit -m "feat: add xhs crawler discovery inputs"
```

## Task 9: Build the Unified CLI

**Files:**
- Create: `/Users/lulu/AIWork/xhs_comment_crawler.py`
- Modify: `/Users/lulu/AIWork/tests/test_xhs_runner.py`

- [ ] **Step 1: Write the failing CLI tests**

```python
from xhs_comment_crawler import build_parser


def test_cli_exposes_expected_commands():
    parser = build_parser()
    help_text = parser.format_help()
    assert "crawl-note-comments" in help_text
    assert "resume-job" in help_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: FAIL because the CLI module does not exist

- [ ] **Step 3: Write minimal implementation**

Implement:

- parser construction
- subcommands
- wiring to discovery, runner, storage, and verify modules
- output directory selection
- user-facing error messaging

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_comment_crawler.py tests/test_xhs_runner.py
git -C /Users/lulu/AIWork commit -m "feat: add unified xhs crawler cli"
```

## Task 10: Align Legacy Scripts to the Unified Modules

**Files:**
- Modify: `/Users/lulu/AIWork/xhs_export_comments.py`
- Modify: `/Users/lulu/AIWork/xhs_export_comments_app_api.py`
- Modify: `/Users/lulu/AIWork/xhs_export_comments_from_chrome.py`

- [ ] **Step 1: Add a smoke test target for legacy imports**

```python
def test_legacy_scripts_import_without_runtime_side_effects():
    import xhs_export_comments  # noqa: F401
    import xhs_export_comments_app_api  # noqa: F401
```

- [ ] **Step 2: Run test to verify it fails if import side effects remain**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: FAIL only if top-level side effects or import problems exist

- [ ] **Step 3: Write minimal implementation**

Ensure the legacy scripts:

- delegate reusable logic to the new package
- keep their current CLI behavior where possible
- do not duplicate normalization or pagination code unnecessarily

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add xhs_export_comments.py xhs_export_comments_app_api.py xhs_export_comments_from_chrome.py tests/test_xhs_runner.py
git -C /Users/lulu/AIWork commit -m "refactor: align legacy xhs scripts with crawler package"
```

## Task 11: End-to-End Manual Validation

**Files:**
- Modify: `/Users/lulu/AIWork/docs/superpowers/plans/2026-03-22-xiaohongshu-comment-crawler.md`

- [ ] **Step 1: Run targeted unit tests**

Run: `pytest /Users/lulu/AIWork/tests/test_xhs_normalize.py /Users/lulu/AIWork/tests/test_xhs_storage.py /Users/lulu/AIWork/tests/test_xhs_verify.py /Users/lulu/AIWork/tests/test_xhs_runner.py -v`
Expected: PASS

- [ ] **Step 2: Run a direct-note smoke test**

Run: `python /Users/lulu/AIWork/xhs_comment_crawler.py crawl-note-comments 6919e2470000000005002ee1 --output-dir /Users/lulu/AIWork/output/xhs-comment-jobs/manual-smoke`
Expected: Job manifest and note output created; note status is `complete`, `partial`, or `failed` with explicit reason

- [ ] **Step 3: Run a resume smoke test**

Run: `python /Users/lulu/AIWork/xhs_comment_crawler.py resume-job manual-smoke`
Expected: Existing job is loaded and resumed without duplicating prior results

- [ ] **Step 4: Run verification report generation**

Run: `python /Users/lulu/AIWork/xhs_comment_crawler.py verify-job manual-smoke`
Expected: `verification.json` and summary output are generated

- [ ] **Step 5: Commit**

```bash
git -C /Users/lulu/AIWork add docs/superpowers/plans/2026-03-22-xiaohongshu-comment-crawler.md
git -C /Users/lulu/AIWork commit -m "docs: update xhs crawler plan after validation"
```
