from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from supervisor.core.models import CheckRequest, CheckResult
from supervisor.checkers.assessment_common import (
    CLICHE_FORBIDDEN,
    COMMON_BASE_FORBIDDEN,
    EXAGGERATION_FORBIDDEN,
    JUDGMENT_FORBIDDEN,
    NLP_DOMAIN_FORBIDDEN,
    PROFILE_FORBIDDEN,
    extract_quotes,
    format_hits,
    infer_dimensions,
    is_quote_attribution_line,
    line_hits,
    profile_segments,
    quote_library_lines,
    read_text,
    resolve_quote_library_path,
    top_repeated_prefixes,
    normalize_prefix,
)


def parse_dimension_blocks(text: str) -> list[dict[str, str]]:
    matches = list(re.finditer(r"^###\s+维度\s+\d+：(?P<name>.+)$", text, flags=re.M))
    blocks: list[dict[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else text.find("## 三、画像详写", start)
        if end == -1:
            end = len(text)
        chunk = text[start:end]
        high_match = re.search(r"####\s+高分版\s*(.*?)(?=^####\s+低分版)", chunk, flags=re.M | re.S)
        low_match = re.search(r"####\s+低分版\s*(.*)\Z", chunk, flags=re.M | re.S)
        blocks.append(
            {
                "name": match.group("name").strip(),
                "high": high_match.group(1).strip() if high_match else "",
                "low": low_match.group(1).strip() if low_match else "",
            }
        )
    return blocks


def extract_intro_text(section: str) -> str:
    marker = "**特征描述**"
    if marker not in section:
        return ""
    return section.split(marker, 1)[0].strip()


def extract_suggestion_lead(section: str) -> str:
    marker = "**建议方向**"
    if marker not in section:
        return ""
    tail = section.split(marker, 1)[1].strip()
    lines = [line.strip() for line in tail.splitlines() if line.strip()]
    for line in lines:
        if line.startswith(">"):
            continue
        return line
    return ""


class AssessmentRole6Checker:
    name = "assessment_role6"

    def check(self, request: CheckRequest) -> CheckResult:
        chapter_path = Path(request.workflow_context["chapter_dir"])
        book = str(request.workflow_context["book"])
        chapter = str(request.workflow_context["chapter"])
        output_path = chapter_path / "role-5-output.md"
        if not output_path.exists():
            raise SystemExit(f"Missing {output_path}")
        text = read_text(output_path)
        dimensions = int(request.user_inputs.get("dimensions") or infer_dimensions(chapter_path))
        expected_profiles = 2**dimensions
        expected_dimension_versions = dimensions * 2
        failures: list[str] = []
        warnings: list[str] = [
            "Coverage: deterministic subset only (C1/C2/C4/C5/C6/C8). C3 and C7 remain manual."
        ]
        details: list[str] = []

        # C1
        base_hits = [
            hit
            for hit in line_hits(text, COMMON_BASE_FORBIDDEN)
            if not (hit[1] == "——" and is_quote_attribution_line(hit[2]))
        ]
        exaggeration_hits = line_hits(text, EXAGGERATION_FORBIDDEN)
        cliche_hits = line_hits(text, CLICHE_FORBIDDEN)
        judgment_hits = line_hits(text, JUDGMENT_FORBIDDEN)
        domain_terms = NLP_DOMAIN_FORBIDDEN if book == "重塑心灵-NLP" else []
        domain_hits = line_hits(text, domain_terms)
        details.extend(
            [
                f"- 通用基础词: {len(base_hits)} 命中",
                f"- 夸张词: {len(exaggeration_hits)} 命中",
                f"- 套话句式: {len(cliche_hits)} 命中",
                f"- 评判词: {len(judgment_hits)} 命中",
                f"- 领域禁用词: {len(domain_hits)} 命中",
            ]
        )
        if any([base_hits, exaggeration_hits, cliche_hits, judgment_hits, domain_hits]):
            failures.append("C1 chapter-wide forbidden terms not clean")

        # C2
        profiles = profile_segments(text)
        profile_prefixes = []
        for _, _, segment in profiles:
            feature_match = re.search(r"\*\*特征描述\*\*\s*(.+)", segment)
            if feature_match:
                profile_prefixes.append(normalize_prefix(feature_match.group(1)))
        profile_prefix, profile_count = top_repeated_prefixes(profile_prefixes, threshold=5)

        dimension_blocks = parse_dimension_blocks(text)
        lead_prefixes = []
        for block in dimension_blocks:
            for key in ("high", "low"):
                intro = extract_intro_text(block[key])
                first_sentence = intro.split("。", 1)[0]
                lead_prefixes.append(normalize_prefix(first_sentence))
        lead_prefix, lead_count = top_repeated_prefixes(lead_prefixes, threshold=2)
        details.extend(
            [
                f"- 画像最高重复：{profile_prefix or 'N/A'} × {profile_count}（阈值 ≤5）",
                f"- 维度版最高重复：{lead_prefix or 'N/A'} × {lead_count}（阈值 ≤2）",
            ]
        )
        if profile_count > 5 or lead_count > 2:
            failures.append("C2 cross-section opening repetition exceeds threshold")

        # C4
        heading_counts = {
            "特征描述": text.count("**特征描述**"),
            "原因解析": text.count("**原因解析**"),
            "影响分析": text.count("**影响分析**"),
            "建议方向": text.count("**建议方向**"),
        }
        expected_counts = {
            "特征描述": expected_dimension_versions + expected_profiles,
            "原因解析": expected_dimension_versions + expected_profiles,
            "影响分析": expected_dimension_versions,
            "建议方向": expected_dimension_versions,
        }
        details.extend(
            [
                f"- 实际：{heading_counts}",
                f"- 期望：{expected_counts}",
            ]
        )
        if heading_counts != expected_counts:
            failures.append("C4 dimension/profile heading structure mismatch")

        # C5
        suggestion_leads = []
        bad_suggestion_leads = []
        for block in dimension_blocks:
            for key in ("high", "low"):
                lead = extract_suggestion_lead(block[key])
                if not lead:
                    bad_suggestion_leads.append(f"{block['name']} {key}: missing suggestion lead")
                    continue
                suggestion_leads.append(lead)
                period_count = lead.count("。")
                char_count = len(re.sub(r"\s+", "", lead))
                if period_count != 1 or char_count > 60 or lead.startswith("这些倾向"):
                    bad_suggestion_leads.append(
                        f"{block['name']} {key}: chars={char_count}, periods={period_count}, text={lead}"
                    )
        details.extend(
            [
                f"- 总领句：{len(suggestion_leads)} / {expected_dimension_versions}",
                f"- 不合格：{len(bad_suggestion_leads)}",
            ]
        )
        if len(suggestion_leads) != expected_dimension_versions or bad_suggestion_leads:
            failures.append("C5 suggestion lead quality failed")
            warnings.extend(bad_suggestion_leads[:10])

        # C6
        details.append(f"- 画像数：{len(profiles)} / {expected_profiles}")
        profile_hits = []
        for _, _, segment in profiles:
            profile_hits.extend(line_hits(segment, PROFILE_FORBIDDEN))
        details.append(f"- 画像禁用词命中：{len(profile_hits)}")
        if len(profiles) != expected_profiles or profile_hits:
            failures.append("C6 profile completeness failed")

        # C8
        quote_library_path = resolve_quote_library_path(request.workflow_context)
        quote_library = quote_library_lines(quote_library_path)
        quotes = extract_quotes(text)
        unique_quotes = list(dict.fromkeys(quotes))
        missing_quotes = [quote for quote in unique_quotes if quote_library and quote not in quote_library]
        details.extend(
            [
                f"- 金句数量：{len(quotes)} / {expected_dimension_versions}",
                f"- 去重数量：{len(unique_quotes)} / {len(quotes)}",
                f"- 来源缺失：{len(missing_quotes)}",
            ]
        )
        if len(quotes) != expected_dimension_versions or len(unique_quotes) != len(quotes) or missing_quotes:
            failures.append("C8 quote dedupe/source validation failed")
            warnings.extend([f"missing quote source: {quote}" for quote in missing_quotes[:10]])

        status = "PASS" if not failures else "FAIL"
        report = [
            f"【Role 6 · 章级调性扫描 · {book} · {chapter}】",
            "",
            f"> 报告路径：{output_path}",
            f"> 章节维度数 N = {dimensions}",
            f"> 期望段数 = {6 + (10 * dimensions) + (expected_profiles * 2)}",
            "",
            "> 覆盖说明：本地 checker 仅覆盖可机械化项目（C1/C2/C4/C5/C6/C8）。",
            "",
            "## C1 全章禁用词兜底",
            *details[:5],
            "",
            "## C2 跨段句型重复",
            *details[5:7],
            "",
            "## C4 维度结构完整性",
            *details[7:9],
            "",
            "## C5 总领句质量",
            *details[9:11],
            "",
            "## C6 画像完整性",
            *details[11:13],
            "",
            "## C8 金句去重 + 来源核验",
            *details[13:16],
            "",
            "## Failures",
            *([f"- {item}" for item in failures] or ["- None"]),
            "",
            "## Warnings",
            *([f"- {item}" for item in warnings] or ["- None"]),
            "",
            "## 综合结论",
            ("✅ Role 6 机械子集通过。" if not failures else "❌ Role 6 机械子集未通过。"),
        ]
        return CheckResult(
            ok=not failures,
            summary=status,
            report_markdown="\n".join(report),
            findings=failures,
            rework_payload={},
        )
