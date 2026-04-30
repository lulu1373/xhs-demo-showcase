from __future__ import annotations

import re
from pathlib import Path

from supervisor.core.models import CheckRequest, CheckResult
from supervisor.checkers.assessment_common import (
    CLICHE_FORBIDDEN,
    COMMON_BASE_FORBIDDEN,
    EXAGGERATION_FORBIDDEN,
    JUDGMENT_FORBIDDEN,
    NLP_DOMAIN_FORBIDDEN,
    PROFILE_FORBIDDEN,
    format_hits,
    infer_dimensions,
    is_quote_attribution_line,
    line_hits,
    profile_segments,
    read_text,
)


def build_rework_payload(book: str, chapter: str, failures: list[str]) -> dict[str, str]:
    failure_text = "\n".join(f"- {item}" for item in failures)
    prompt = f"""请只修复下面列出的违规，不要重写整章，不要改无关段落。

书名标识：{book}
章节号：{chapter}

必须遵守：
- 画像必须且只能有 `**特征描述**` 和 `**原因解析**` 两个加粗小标题
- 画像禁止 `↓`
- 画像禁止“第一步/第二步/第三步”
- 画像正文禁止出现“维度/高分/低分”
- 第一轮 4 条 grep 必须全部 0 命中：基础词、夸张词、套话句式、评判词
- `由于` 单独计数，期望 = 0（书内引用除外）
- 只修改失败段落，不要覆盖整个文件

本轮违规：
{failure_text}
"""
    return {"rework": prompt, "failure_text": failure_text}


class AssessmentRole5Checker:
    name = "assessment_role5"

    def check(self, request: CheckRequest) -> CheckResult:
        chapter_path = Path(request.workflow_context["chapter_dir"])
        book = str(request.workflow_context["book"])
        chapter = str(request.workflow_context["chapter"])
        output_path = chapter_path / "role-5-output.md"
        progress_path = chapter_path / "role-5-progress.md"
        if not output_path.exists():
            raise SystemExit(f"Missing {output_path}")
        if not progress_path.exists():
            raise SystemExit(f"Missing {progress_path}")

        dimensions = int(request.user_inputs.get("dimensions") or infer_dimensions(chapter_path))
        expected_profiles = 2**dimensions
        text = read_text(output_path)
        progress = read_text(progress_path)
        failures: list[str] = []
        warnings: list[str] = []
        details: list[str] = []

        placeholders = len(re.findall(r"<!--\s*PH-", text))
        unchecked = len(re.findall(r"^-\s+\[\s\]\s+PH-", progress, flags=re.M))
        details.append(f"- output placeholders: {placeholders}")
        details.append(f"- progress unchecked items: {unchecked}")
        if placeholders != unchecked:
            failures.append(
                f"role-5-output placeholders ({placeholders}) != progress unchecked ({unchecked})"
            )

        profiles = profile_segments(text)
        profile_codes = [code for code, _, _ in profiles]
        details.append(f"- profiles: actual {len(profiles)} / expected {expected_profiles}")
        if len(profiles) != expected_profiles:
            failures.append(f"profile count {len(profiles)} != expected {expected_profiles}")
        duplicates = sorted({code for code in profile_codes if profile_codes.count(code) > 1})
        if duplicates:
            failures.append(f"duplicate profile codes: {', '.join(duplicates)}")

        for code, line, segment in profiles:
            if "<!-- PH-PROFILE-" in segment:
                warnings.append(
                    f"profile {code} line {line}: profile placeholder present; heading check deferred"
                )
                continue
            feature_count = segment.count("**特征描述**")
            cause_count = segment.count("**原因解析**")
            if feature_count != 1 or cause_count != 1:
                failures.append(
                    f"profile {code} line {line}: headings must be exactly one 特征描述 and one 原因解析 (got {feature_count}/{cause_count})"
                )
            for bad_heading in ["**影响分析**", "**建议方向**"]:
                if bad_heading in segment:
                    failures.append(f"profile {code} line {line}: forbidden heading {bad_heading}")
            bad_terms = line_hits(segment, PROFILE_FORBIDDEN)
            if bad_terms:
                compact = "; ".join(f"+{offset}:{term}" for offset, term, _ in bad_terms[:12])
                failures.append(f"profile {code} line {line}: forbidden profile terms {compact}")

        base_hits = [
            hit
            for hit in line_hits(text, COMMON_BASE_FORBIDDEN)
            if not (hit[1] == "——" and is_quote_attribution_line(hit[2]))
        ]
        if base_hits:
            failures.append(f"common base forbidden terms hit {len(base_hits)} lines")
            details.extend(format_hits("common base forbidden", base_hits[:40]))

        exaggeration_hits = line_hits(text, EXAGGERATION_FORBIDDEN)
        if exaggeration_hits:
            failures.append(f"exaggeration forbidden terms hit {len(exaggeration_hits)} lines")
            details.extend(format_hits("exaggeration forbidden", exaggeration_hits[:40]))

        cliche_hits = line_hits(text, CLICHE_FORBIDDEN)
        if cliche_hits:
            failures.append(f"cliche sentence patterns hit {len(cliche_hits)} lines")
            details.extend(format_hits("cliche sentence patterns", cliche_hits[:40]))

        judgment_hits = line_hits(text, JUDGMENT_FORBIDDEN)
        if judgment_hits:
            failures.append(f"judgment forbidden terms hit {len(judgment_hits)} lines")
            details.extend(format_hits("judgment forbidden", judgment_hits[:40]))

        youyu_count = sum(1 for _, term, _ in base_hits if term == "由于")
        if youyu_count:
            failures.append(f"`由于` count expected 0, got {youyu_count}")

        domain_terms = NLP_DOMAIN_FORBIDDEN if book == "重塑心灵-NLP" else []
        domain_hits = line_hits(text, domain_terms)
        if domain_hits:
            failures.append(f"domain forbidden terms hit {len(domain_hits)} lines")
            details.extend(format_hits("domain forbidden", domain_hits[:40]))

        status = "PASS" if not failures else "FAIL"
        report = [
            "# Assessment Supervisor Check",
            "",
            f"- book: {book}",
            f"- chapter: {chapter}",
            "- role: 5",
            f"- status: {status}",
            f"- dimensions: {dimensions}",
            "",
            "## Mechanical Counts",
            *details,
            "",
            "## Failures",
            *([f"- {item}" for item in failures] or ["- None"]),
            "",
            "## Warnings",
            *([f"- {item}" for item in warnings] or ["- None"]),
            "",
        ]
        rework_payload = build_rework_payload(book, chapter, failures) if failures else {}
        if failures:
            report.append("## Rework Prompt")
            report.append(rework_payload["rework"])
            report.append("")
        return CheckResult(
            ok=not failures,
            summary=status,
            report_markdown="\n".join(report),
            findings=failures,
            rework_payload=rework_payload,
        )
