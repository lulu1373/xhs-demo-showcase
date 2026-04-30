from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional


COMMON_BASE_FORBIDDEN = [
    "而是",
    "而不是",
    "但是",
    "然而",
    "不过",
    "不仅",
    "同时",
    "另外",
    "此外",
    "反而",
    "可是",
    "虽然",
    "真的",
    "确实",
    "其实",
    "可以说",
    "某种程度上",
    "卡",
    "松",
    "崩",
    "炸",
    "松了",
    "拉扯",
    "稳住",
    "接住",
    "长出来",
    "做熟",
    "方法感",
    "被激活",
    "先抓",
    "顺起来",
    "接上",
    "——",
    "↓",
    "不是不",
    "不是没",
    "并不是不",
    "你没有",
    "你不太会",
    "你不懂",
]

EXAGGERATION_FORBIDDEN = [
    "极其",
    "极度",
    "极具",
    "极强",
    "极端",
    "极为",
    "极高",
    "极低",
    "深度",
    "深层",
    "深刻",
    "深深",
    "巨大",
    "卓越",
    "顶级",
    "硬核",
    "彻底",
    "绝对",
    "一万倍",
    "无比",
    "疯狂",
    "崩溃",
    "窒息",
    "摧毁",
    "爆发",
    "严重",
    "强烈",
    "最高级",
    "最核心",
    "最重要",
    "最强",
    "最难",
    "最深",
]

CLICHE_FORBIDDEN = [
    "你展现出",
    "你展示了",
    "你呈现出",
    "你身上闪耀",
    "你身上散发",
]

JUDGMENT_FORBIDDEN = [
    "令人折服",
    "令人惊佩",
    "令人惊叹",
    "罕见的",
    "稀有的",
    "难得的",
    "异于常人",
    "出类拔萃",
    "与众不同",
    "天赋异禀",
    "堪称",
    "堪比",
    "缺乏",
    "病态",
    "摧残",
    "病灶",
    "病根",
    "残缺",
    "扭曲",
    "畸形",
]

NLP_DOMAIN_FORBIDDEN = [
    "能量",
    "频率",
    "振动",
    "显化",
    "吸引力",
    "宇宙安排",
    "宇宙馈赠",
    "丰盛",
    "流动起来",
    "连接到",
    "被加持",
    "灵魂功课",
    "内在小孩",
    "高维",
    "低维",
    "小我",
    "大我",
    "原型",
    "原生家庭",
    "童年阴影",
    "被压抑的真我",
    "潜意识里的伤口",
    "能量场",
    "人格能量",
    "限制性信念",
    "可能性思维",
    "跳出框架",
    "重塑神经回路",
    "解锁",
    "激活",
    "卡点",
    "内观",
    "觉知",
    "觉察",
    "觉醒",
    "疗愈",
    "整合",
]

PROFILE_FORBIDDEN = [
    "↓",
    "第一步",
    "第二步",
    "第三步",
    "维度",
    "高分",
    "低分",
    "圆满",
    "合道",
    "圆通",
    "高级境界",
    "近乎道家",
    "一阶",
    "二阶",
    "开悟",
    "觉醒",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def line_hits(text: str, terms: Iterable[str]) -> list[tuple[int, str, str]]:
    hits: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for term in terms:
            if term and term in line:
                hits.append((lineno, term, line.strip()))
    return hits


def is_quote_attribution_line(line: str) -> bool:
    return bool(re.match(r'^>\s*["“].+["”]\s*——\s*[^"\n]+$', line.strip()))


def profile_segments(text: str) -> list[tuple[str, int, str]]:
    matches = list(re.finditer(r"^###\s+画像\s+([LH]+).*$", text, flags=re.M))
    segments: list[tuple[str, int, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        line = text[: match.start()].count("\n") + 1
        segments.append((match.group(1), line, text[start:end]))
    return segments


def infer_dimensions(chapter_path: Path) -> int:
    role2 = chapter_path / "role-2-output.md"
    if role2.exists():
        count = len(re.findall(r"^###\s+维度\s+\d+", read_text(role2), flags=re.M))
        if count:
            return count
    role5 = chapter_path / "role-5-output.md"
    if role5.exists():
        match = re.search(r"维度数\s*N\s*=\s*(\d+)", read_text(role5))
        if match:
            return int(match.group(1))
    raise SystemExit(f"Cannot infer dimension count from {chapter_path}")


def format_hits(label: str, hits: list[tuple[int, str, str]]) -> list[str]:
    lines = [f"", f"### {label} hits"]
    for lineno, term, line in hits:
        lines.append(f"- line {lineno}: `{term}` -> {line[:160]}")
    return lines


def parse_role2_dimension_names(text: str) -> list[str]:
    return re.findall(r"^###\s+维度\s+\d+：(.+)$", text, flags=re.M)


def parse_role3_dimension_names(text: str) -> list[str]:
    return re.findall(r"^##\s+维度\s+\d+：(.+)$", text, flags=re.M)


def parse_role3_item_counts(text: str) -> list[dict[str, object]]:
    sections = re.split(r"^##\s+维度\s+\d+：", text, flags=re.M)
    names = parse_role3_dimension_names(text)
    results: list[dict[str, object]] = []
    for name, section in zip(names, sections[1:]):
        rows = re.findall(r"^\|\s*([\d.]+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|$", section, flags=re.M)
        total = len(rows)
        positive = sum(1 for _, _, polarity in rows if "正" in polarity and "反" not in polarity)
        reverse = sum(1 for _, _, polarity in rows if "反" in polarity)
        results.append(
            {
                "name": name.strip(),
                "total": total,
                "positive": positive,
                "reverse": reverse,
            }
        )
    return results


def parse_role5_dimension_names(text: str) -> list[str]:
    return re.findall(r"^###\s+维度\s+\d+：(.+)$", text, flags=re.M)


def parse_role2_ranges(text: str) -> list[str]:
    return re.findall(r"\|\s*第[一二三四五六]档.*?\|\s*([0-9]+–[0-9]+)\s*\|", text)


def parse_role5_ranges(text: str) -> list[str]:
    return re.findall(r"^###\s+第[一二三四五六]档\s+([0-9]+–[0-9]+)", text, flags=re.M)


def normalize_prefix(text: str, limit: int = 4) -> str:
    collapsed = re.sub(r"\s+", "", text)
    collapsed = re.sub(r"[，。、“”\"'：:！？!?,．\-\(\)（）]", "", collapsed)
    return collapsed[:limit]


def extract_quotes(text: str) -> list[str]:
    quotes: list[str] = []
    for line in text.splitlines():
        match = re.match(r'^>\s*["“](.+?)["”]\s*——\s*.+$', line.strip())
        if match:
            quotes.append(match.group(1).strip())
    return quotes


def quote_library_lines(path: Optional[Path]) -> set[str]:
    if path is None or not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#") and not line.startswith("以下是")
    }


def resolve_quote_library_path(context: dict[str, object]) -> Optional[Path]:
    value = context.get("quote_library_path")
    if not value:
        return None
    path = Path(str(value))
    return path if path.exists() else None


def top_repeated_prefixes(prefixes: list[str], threshold: int) -> tuple[str, int]:
    if not prefixes:
        return ("", 0)
    counts = Counter([item for item in prefixes if item])
    if not counts:
        return ("", 0)
    prefix, count = counts.most_common(1)[0]
    return prefix, count


def suggested_quote_library_for_book(book: str) -> Optional[Path]:
    root = Path(__file__).resolve().parents[2]
    mapping = {
        "重塑心灵-NLP": root / "docs" / "assessment-workflow" / "李中莹重塑心灵金句.md",
    }
    path = mapping.get(book)
    if path and path.exists():
        return path
    return None

