---
name: douban-book-review-crawler
description: Crawl Douban Book multi-version ratings, short comments, and full reviews, then generate reusable Chinese reader persona outputs. Use when the user asks to crawl 豆瓣读书 comments/reviews/ratings, all editions/versions of a book, or make a user persona report like the previous Douban workflow.
---

# Douban Book Review Crawler

Use this skill for 豆瓣读书图书评论/评分爬取 and follow-up 用户画像分析. The target output is not just raw scraping: it should leave reproducible tables, coverage notes, and a persona report that can be compared across platforms.

## Required Inputs

Confirm or infer:

- `search_keyword`: book title or Douban search URL.
- `author_filter`: author/editor/translator filter when user says a specific author, for example `李中莹`.
- `scope`: all relevant editions/versions unless user asks for one subject only.
- `output_slug`: stable lowercase slug, for example `douban_lizhongying_reshaping_mind_YYYYMMDD`.

If the user provides a Douban URL, still run search/discovery unless they explicitly says "only this URL". Different editions may have separate subject IDs and separate comment/review pages.

## Workflow

### 1. Discover Editions

1. Fetch `https://search.douban.com/book/subject_search?search_text=<keyword>&cat=1001&start=0`.
2. Parse `window.__DATA__` from the search page.
3. For each candidate, fetch `https://book.douban.com/subject/<subject_id>/`.
4. Parse title, author, publisher, pub year, ISBN, pages, binding, price, rating, rating count, star distribution, and collection counts.
5. Apply relevance filter using title + author + publisher. Do not include same-title unrelated books.
6. Save the edition table before crawling comments so the scope is auditable.

### 2. Crawl Short Comments

For each relevant subject:

- Crawl `comments/` for `读过`, `在读`, and `想读` status when counts exist.
- Preserve status, rating star, comment text, comment time, useful count, user name, user URL, comment URL, subject ID, and edition title.
- Stop by expected count, no-new-rows, or blocked page detection.
- Record blocked/empty pages into a separate `blocked_pages.csv`.

Implementation notes:

- Use a realistic desktop `User-Agent`, `Accept-Language`, and Douban referer.
- Sleep between requests with random jitter.
- If logged-in browser state is needed, use Playwright/browser export only with user-visible context; do not invent missing rows.
- For Chinese CSV output, write both normal UTF-8 and UTF-8-BOM when the user may open files in Excel.

### 3. Crawl Full Reviews

For each relevant subject:

- Crawl `/reviews` index pages and parse review ID, title, author, rating, useful count, useless count, reply count, summary, and review URL.
- De-duplicate reviews by `review_id` across editions.
- Fetch each full review page and extract full text when available.
- Save blocked review pages separately.

### 4. Export Raw Data

Create an output folder under `/Users/lulu/AIWork/output/<output_slug>/` containing:

- `<slug>_editions.csv`
- `<slug>_comments.csv`
- `<slug>_comments_utf8_bom.csv`
- `<slug>_reviews.csv`
- `<slug>_reviews_utf8_bom.csv`
- `<slug>.xlsx` with `editions`, `comments`, `reviews`, `blocked_pages`, `blocked_review_pages`
- `<slug>_summary.json`

The summary must include candidate count, relevant subject count, subject IDs, row counts, blocked page counts, and file paths.

### 5. Build Reader Persona

Use `social-user-profile-universe` for the user persona layer, then adapt the book-specific reader taxonomy. For 《重塑心灵》 the proven five-class taxonomy is:

- `轻表态收藏型读者`: short "want/read/liked/recommended" or low-evidence feedback.
- `方法工具实践型读者`: focuses on actionable methods, exercises, communication, emotion, goals, or self-value tools.
- `NLP学习整理型读者`: treats the book as NLP concept framework, notes, excerpts, assumptions, chapter summaries.
- `自我修复成长型读者`: narrates personal growth, self-acceptance, inner change, relationship repair, emotional work.
- `专业真实性鉴别型读者`: questions NLP, evidence, pseudo-science, success-study packaging, marketing, or credibility.

Required persona outputs:

- `<persona_slug>_comment_layer.csv`
- `<persona_slug>_user_profiles.csv`
- `<persona_slug>_tables.xlsx`
- `<persona_slug>_user_persona_report.md`
- Optional visual dashboard: brief/detail HTML + PNG + PDF if the user asks for 可视化.

Persona rules:

- Label comments first, then aggregate to users by stable user URL or user ID.
- Single-comment users are `单次发声`; do not infer stable personality.
- Do not infer age, gender, city, job, income, or psychological diagnosis from comments.
- Preserve representative original comments as evidence.
- Mention platform and coverage limits explicitly.

### 6. Verification

Before final response:

- Check raw row counts against summary JSON.
- Check duplicate `review_id` and duplicate comment URLs.
- Check empty comment/review text counts.
- Check edition coverage and blocked page CSVs.
- Open/read the Markdown report head and at least one persona section.
- State any known limitations, for example Douban anti-crawl blocks or pages requiring login.

## Proven Local Templates

Use these local scripts as working examples, adapting constants and filenames for the new book:

- `/Users/lulu/AIWork/scripts/douban_lizhongying_reshaping_mind.py`
- `/Users/lulu/AIWork/scripts/build_douban_lizhongying_persona_dashboard.py`
- `/Users/lulu/AIWork/output/douban_lizhongying_persona_20260429/douban_lizhongying_user_persona_report.md`

If adapting the crawler, replace hard-coded search URL, output paths, relevance filter, and filename slug first. Do not leave 李中莹/重塑心灵-specific names in a new task unless the user asks for the same book.

## Final Response Pattern

Return concise paths and counts:

- Raw crawl folder.
- Persona report Markdown.
- Main CSV/XLSX files.
- Coverage limitations and what was not inferred.

Do not paste full CSV content into chat.
