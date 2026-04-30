from __future__ import annotations

import re
from pathlib import Path

from supervisor.core.models import CheckRequest, CheckResult
from supervisor.checkers.assessment_common import (
    extract_quotes,
    infer_dimensions,
    parse_role2_dimension_names,
    parse_role2_ranges,
    parse_role3_dimension_names,
    parse_role3_item_counts,
    parse_role5_dimension_names,
    parse_role5_ranges,
    profile_segments,
    quote_library_lines,
    read_text,
    resolve_quote_library_path,
)


class AssessmentRole7Checker:
    name = "assessment_role7"

    def check(self, request: CheckRequest) -> CheckResult:
        chapter_path = Path(request.workflow_context["chapter_dir"])
        book = str(request.workflow_context["book"])
        chapter = str(request.workflow_context["chapter"])
        dimensions = int(request.user_inputs.get("dimensions") or infer_dimensions(chapter_path))
        expected_profiles = 2**dimensions

        role1_path = chapter_path / "role-1-output.md"
        role2_path = chapter_path / "role-2-output.md"
        role3_path = chapter_path / "role-3-output.md"
        role5_path = chapter_path / "role-5-output.md"
        progress_path = chapter_path / "role-5-progress.md"
        for path in [role1_path, role2_path, role3_path, role5_path, progress_path]:
            if not path.exists():
                raise SystemExit(f"Missing {path}")

        role1_text = read_text(role1_path)
        role2_text = read_text(role2_path)
        role3_text = read_text(role3_path)
        role5_text = read_text(role5_path)
        progress_text = read_text(progress_path)

        failures: list[str] = []
        warnings: list[str] = [
            "Coverage: deterministic subset only (V1/V2/V3/V5/V10). V4/V6/V7/V8/V9 remain manual."
        ]

        # V1
        role2_names = parse_role2_dimension_names(role2_text)
        role3_names = parse_role3_dimension_names(role3_text)
        role5_names = parse_role5_dimension_names(role5_text)
        if role2_names != role3_names or role2_names != role5_names:
            failures.append("V1 dimension name chain mismatch across Role 2/3/5")

        # V2
        role3_counts = parse_role3_item_counts(role3_text)
        invalid_dimensions = [
            item
            for item in role3_counts
            if item["total"] != 5 or item["positive"] != 4 or item["reverse"] != 1
        ]
        if invalid_dimensions:
            failures.append("V2 role-3 item distribution invalid")

        # V3
        role2_ranges = parse_role2_ranges(role2_text)
        role5_ranges = parse_role5_ranges(role5_text)
        profiles = profile_segments(role5_text)
        profile_codes = [code for code, _, _ in profiles]
        duplicate_profiles = sorted({code for code in profile_codes if profile_codes.count(code) > 1})
        if role2_ranges != role5_ranges:
            failures.append("V3 display score ranges mismatch between Role 2 and Role 5")
        if len(profiles) != expected_profiles or duplicate_profiles:
            failures.append("V3 profile math mismatch")

        # V5
        quote_library_path = resolve_quote_library_path(request.workflow_context)
        quote_library = quote_library_lines(quote_library_path)
        quotes = extract_quotes(role5_text)
        missing_quotes = [quote for quote in quotes if quote_library and quote not in quote_library]
        if missing_quotes:
            failures.append("V5 quote source validation failed")

        # V10
        placeholders = len(re.findall(r"<!--\s*PH-", role5_text))
        unchecked = len(re.findall(r"^-\s+\[\s\]\s+PH-", progress_text, flags=re.M))
        if placeholders != 0 or unchecked != 0:
            failures.append("V10 placeholders or unchecked progress remain")

        status = "PASS" if not failures else "FAIL"
        report = [
            f"【Role 7 · 跨文件结果校验 · {book} · {chapter}】",
            "",
            f"> 校验对象：{role5_path}",
            f"> 维度数 N = {dimensions}",
            f"> 期望画像数 = {expected_profiles}",
            "",
            "> 覆盖说明：本地 checker 仅覆盖可机械化项目（V1/V2/V3/V5/V10）。",
            "",
            "## V1 维度名链路一致性",
            f"- Role 2：{role2_names}",
            f"- Role 3：{role3_names}",
            f"- Role 5：{role5_names}",
            ("判定：✅ 一致" if role2_names == role3_names == role5_names else "判定：❌ 不一致"),
            "",
            "## V2 题目维度归属",
            *[
                f"- {item['name']}: 题目数={item['total']} 正向={item['positive']} 反向={item['reverse']}"
                for item in role3_counts
            ],
            ("判定：✅ 每维 5 题、4 正 1 反" if not invalid_dimensions else "判定：❌ 分布不符"),
            "",
            "## V3 分数-区间-画像数学一致性",
            f"- Role 2 展示分段：{role2_ranges}",
            f"- Role 5 展示分段：{role5_ranges}",
            f"- 画像数：{len(profiles)} / {expected_profiles}；去重：{len(set(profile_codes))} / {len(profiles)}",
            ("判定：✅ 数学一致" if role2_ranges == role5_ranges and len(profiles) == expected_profiles and not duplicate_profiles else "判定：❌ 数学不一致"),
            "",
            "## V5 金句来源",
            f"- 金句数量：{len(quotes)}",
            f"- 来源缺失：{len(missing_quotes)}",
            ("判定：✅ 金句均在金句库" if not missing_quotes else "判定：❌ 存在金句来源缺失"),
            "",
            "## V10 文件完整性",
            f"- 残留占位符：{placeholders}",
            f"- progress 未勾：{unchecked}",
            ("判定：✅ 文件完整" if placeholders == 0 and unchecked == 0 else "判定：❌ 文件未完成"),
            "",
            "## Failures",
            *([f"- {item}" for item in failures] or ["- None"]),
            "",
            "## Warnings",
            *([f"- {item}" for item in warnings] or ["- None"]),
            "",
            "## 综合结论",
            ("✅ Role 7 机械子集通过。" if not failures else "❌ Role 7 机械子集未通过。"),
        ]
        return CheckResult(
            ok=not failures,
            summary=status,
            report_markdown="\n".join(report),
            findings=failures,
            rework_payload={},
        )

