---
name: dycrawler
description: Use MediaCrawler to crawl Douyin / 抖音 single-post comments and export first-level plus second-level comments. Use when the user asks to 抓取/爬取/导出抖音评论, a Douyin video/post URL with modal_id, aweme_id, or wants the MediaCrawler Douyin comment workflow packaged as an executable skill.
---

# Dycrawler

Use this skill to execute the local MediaCrawler Douyin detail crawler for one or more explicit posts, then verify and export comments into JSONL, CSV, and XLSX.

## Default Assumptions

- MediaCrawler repo is discovered from `--mediacrawler-dir`, `MEDIACRAWLER_DIR`, the current directory, a nearby `MediaCrawler/` folder, or Carrie local fallback `/Users/lulu/AIWork/MediaCrawler`.
- Prefer a single Douyin post URL containing `modal_id=<aweme_id>`, a `/video/<aweme_id>` URL, or a bare aweme ID.
- Use `detail` mode, `platform=dy`, `save_data_option=jsonl`, `get_comment=true`, `get_sub_comment=true`.
- Default output root is under `<MediaCrawler>/output/`.
- Respect the MediaCrawler non-commercial learning license and avoid large-scale or disruptive crawling.

## First-Time Setup

If MediaCrawler, `uv`, Chrome/CDP, or the Douyin login state may be missing, run the bootstrap checker first:

```bash
python3 /Users/lulu/AIWork/.codex/skills/dycrawler/scripts/bootstrap_dycrawler.py
```

For a colleague's copied skill folder:

```bash
python3 scripts/bootstrap_dycrawler.py
```

The checker is non-destructive by default: it reports missing pieces and prints exact next steps. To let it clone MediaCrawler, run `uv sync`, and apply the Douyin reliability patch:

```bash
python3 scripts/bootstrap_dycrawler.py \
  --all \
  --install-dir "$HOME/AIWork"
```

Use explicit paths when needed:

```bash
python3 scripts/bootstrap_dycrawler.py \
  --clone \
  --sync \
  --apply-patch \
  --mediacrawler-dir "/path/to/MediaCrawler"
```

Bootstrap behavior:

1. Check `git`, `uv`, and Python.
2. Find or clone `https://github.com/NanmiCoder/MediaCrawler`.
3. Run `uv sync` when requested.
4. Apply the two-file Douyin comment patch when requested.
5. Check whether Chrome DevTools Protocol is reachable at `127.0.0.1:9222`.
6. Print Chrome launch commands and remind the user to open Douyin and finish login manually.

Do not claim the environment is ready until the bootstrap output shows MediaCrawler is valid, the patch is present, and CDP/login has been handled.

## Fast Path

Run the bundled script:

```bash
python3 /Users/lulu/AIWork/.codex/skills/dycrawler/scripts/run_douyin_comment_crawl.py \
  "<douyin_post_url_or_aweme_id>" \
  --sleep-sec 4 \
  --max-comments 99999
```

For a colleague's machine, replace the script path with their local skill path, or run from the copied skill folder:

```bash
python3 scripts/run_douyin_comment_crawl.py \
  "<douyin_post_url_or_aweme_id>" \
  --mediacrawler-dir "/path/to/MediaCrawler" \
  --sleep-sec 4 \
  --max-comments 99999
```

The script will:

1. Check that MediaCrawler has the required Douyin comment reliability patch.
2. Run MediaCrawler with one explicit `--specified_id`.
3. Save raw `detail_comments_*.jsonl`.
4. Export `douyin_comments_<aweme_id>.csv`, `douyin_comments_<aweme_id>.xlsx`, and `douyin_comments_<aweme_id>_summary.json`.
5. Print a final JSON summary with total, first-level, and second-level comment counts.

If only exporting a previous run:

```bash
python3 /Users/lulu/AIWork/.codex/skills/dycrawler/scripts/run_douyin_comment_crawl.py \
  --export-existing-jsonl "/absolute/path/detail_comments_YYYY-MM-DD.jsonl" \
  --source-url "<douyin_post_url_or_aweme_id>"
```

## Reuse Checklist

When sharing this skill with a colleague, send the whole `dycrawler/` folder. They need:

- A working MediaCrawler clone with `uv sync` completed.
- Chrome or Edge usable by MediaCrawler CDP mode, with Douyin login completed when needed.
- The required Douyin reliability patch below. The script checks this and aborts if missing.
- `openpyxl` available in the Python environment if XLSX output is desired; CSV still works without it.

If any of those are missing, have them run `scripts/bootstrap_dycrawler.py --all --install-dir "$HOME/AIWork"` first.

## Required MediaCrawler Patch

Before crawling, make sure these local changes exist. The bundled script checks them and aborts if they are missing.

- `/Users/lulu/AIWork/MediaCrawler/media_platform/douyin/core.py`
  - `batch_get_note_comments` must use `await asyncio.gather(*task_list)` instead of `asyncio.wait(task_list)` so task exceptions surface.
  - `get_comments` must re-raise `DataFetchError` and unexpected exceptions.
- `/Users/lulu/AIWork/MediaCrawler/media_platform/douyin/client.py`
  - `get_aweme_all_comments` must log `top_level_count`, `sub_comment_count`, page cursors, and final total.
  - Empty top-level or sub-comment pages should warn and `break`, not `continue`, to avoid silent infinite loops.

If a fresh MediaCrawler clone is missing these changes, patch those two files first, then run:

```bash
cd /path/to/MediaCrawler
uv run python -m py_compile media_platform/douyin/core.py media_platform/douyin/client.py
```

## Input Handling

- If the user gives one post URL, run the script directly.
- If the user gives a creator homepage and asks for the first N posts, first collect N post URLs with `modal_id`, then run this skill once per post. Do not rely on creator crawling when exact comment completeness matters.
- If the user asks why counts differ, compare the final MediaCrawler log line:
  - `top_level_count:<n>`
  - `sub_comment_count:<n>`
  - `total:<n>`
  - `has_more:<0|1>`
- Douyin's visible comment count can include both top-level and second-level comments. The export splits them with `level=1` and `level=2`.

## Troubleshooting

- Partial counts such as `112` for a post showing `314` usually mean the browser/page context closed mid-run or an exception was swallowed by unpatched `asyncio.wait`.
- Prefer single-post `modal_id` runs for completeness.
- Use `--sleep-sec 4` to `--sleep-sec 8` when Douyin returns empty pages or the run is unstable.
- If second-level comments make a run fragile, first establish top-level coverage with `--no-include-sub-comments`, then rerun with sub-comments enabled.
- If login or risk control appears, use the visible Chrome session and complete verification manually; do not invent missing rows.

## Final Response Pattern

Report only the useful artifacts and counts:

- Total comments, first-level comments, second-level comments, unique comment IDs.
- XLSX path.
- CSV path.
- Raw JSONL path.
- Any known limitation, especially if `has_more=1`, the run raised an exception, or the final total does not match the visible Douyin count.
