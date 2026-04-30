from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = ROOT / "docs" / "assessment-workflow"
CLAUDE_AGENTS = ROOT / ".claude" / "agents"
GLOBAL_CODEX_SKILLS = Path("/Users/lulu/.codex/skills")
PROJECT_CODEX_SKILLS = ROOT / ".codex" / "skills"

ROLE_AGENT_FILES = {
    "1": "assess-role-1-extractor.md",
    "2": "assess-role-2-framework.md",
    "3": "assess-role-3-item-writer.md",
    "4": "assess-role-4-item-reviewer.md",
    "5": "assess-role-5-writer-with-qc.md",
    "5.5": "assess-role-5.5-paragraph-qc.md",
    "6": "assess-role-6-tone-guardian.md",
    "7": "assess-role-7-result-validator.md",
}


def chapter_dir(book: str, chapter: str) -> Path:
    return WORKFLOW_DIR / "books" / book / chapter


def domain_pack_path(book: str) -> Path:
    return WORKFLOW_DIR / "books" / book / "domain-pack.md"


def role_skill_path(role: str, first_batch: bool) -> Path:
    if role == "5" and not first_batch:
        relative = Path("assess-r5-next") / "SKILL.md"
    else:
        relative = Path(f"assess-r{role}") / "SKILL.md"
    project_path = PROJECT_CODEX_SKILLS / relative
    if project_path.exists():
        return project_path
    return GLOBAL_CODEX_SKILLS / relative


def build_context(step_id: str, inputs: dict[str, object], workflow_dir: Path) -> dict[str, object]:
    book = str(inputs["book"])
    chapter = str(inputs["chapter"])
    role = str(inputs.get("role", "5"))
    first_batch = str(inputs.get("first_batch", "")).lower() in {"1", "true", "yes"}
    cdir = chapter_dir(book, chapter)
    skill = role_skill_path(role, first_batch)
    agent = CLAUDE_AGENTS / ROLE_AGENT_FILES.get(role, "")
    common = WORKFLOW_DIR / "通用规范_V1.md"
    domain = domain_pack_path(book)
    paths = [skill, common, domain, cdir]
    if agent.name:
        paths.append(agent)
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise SystemExit("Missing required paths:\n" + "\n".join(missing))

    allow_edits = str(inputs.get("allow_edits", "")).lower() in {"1", "true", "yes"}
    mode_line = (
        "本轮允许自动编辑指定章节文件。"
        if allow_edits
        else "本轮只读检查，不允许修改任何文件。"
    )
    batch = str(
        inputs.get("batch")
        or "按用户指定范围执行；如果范围不清，只生成计划和需要确认的问题。"
    )
    return {
        "book": book,
        "chapter": chapter,
        "role": role,
        "skill_path": str(skill),
        "agent_path": str(agent),
        "common_path": str(common),
        "domain_path": str(domain),
        "chapter_dir": str(cdir),
        "mode_line": mode_line,
        "batch_instruction": batch,
        "quote_library_path": str((ROOT / "docs" / "assessment-workflow" / "李中莹重塑心灵金句.md")) if book == "重塑心灵-NLP" else "",
    }
