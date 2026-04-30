from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


ROOT = Path("/Users/lulu/AIWork")
SCRIPT_PATH = ROOT / "scripts" / "sop_supervisor.py"
LEGACY_SCRIPT_PATH = ROOT / "scripts" / "assessment_supervisor.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SopSupervisorTests(unittest.TestCase):
    def test_render_template_rejects_missing_key(self) -> None:
        module = load_module(SCRIPT_PATH, "sop_supervisor_script_missing_key")

        with self.assertRaises(KeyError):
            module.render_prompt_text("hello ${name} ${missing}", {"name": "world"})

    def test_load_workflow_config_supports_json(self) -> None:
        module = load_module(SCRIPT_PATH, "sop_supervisor_script_json")

        with TemporaryDirectory() as tmp_dir:
            workflow_path = Path(tmp_dir) / "workflow.json"
            workflow_path.write_text(
                json.dumps(
                    {
                        "id": "demo",
                        "defaults": {"run_root": "runs/demo"},
                        "steps": {
                            "draft": {
                                "prompt_template": "prompts/draft.md",
                                "runner": "gemini_cli",
                                "checker": "none",
                                "allow_edits": False,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            config = module.load_workflow_config(workflow_path)

        self.assertEqual(config.workflow_id, "demo")
        self.assertEqual(config.steps["draft"].runner, "gemini_cli")
        self.assertEqual(config.defaults.run_root, "runs/demo")

    def test_gemini_runner_builds_expected_command(self) -> None:
        module = load_module(SCRIPT_PATH, "sop_supervisor_script_runner")
        runner = module.GeminiCliRunner()
        request = module.RunnerRequest(
            prompt="Reply with OK only.",
            cwd=ROOT,
            timeout_seconds=120,
            allow_edits=False,
            env={},
            metadata={},
        )

        with mock.patch("supervisor.runners.gemini_cli.shutil.which", return_value="/opt/bin/gemini"):
            with mock.patch("supervisor.runners.gemini_cli.subprocess.run") as run_mock:
                run_mock.return_value = mock.Mock(
                    returncode=0,
                    stdout='{"response":"OK"}',
                    stderr="",
                )
                result = runner.run(request)

        self.assertEqual(result.command[0], "/opt/bin/gemini")
        self.assertIn("--approval-mode", result.command)
        self.assertIn("plan", result.command)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.parsed_output["response"], "OK")

    def test_engine_dry_run_writes_prompt_bundle(self) -> None:
        module = load_module(SCRIPT_PATH, "sop_supervisor_script_dry_run")

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_dir = root / "workflow"
            prompts_dir = workflow_dir / "prompts"
            prompts_dir.mkdir(parents=True)
            (prompts_dir / "draft.md").write_text("Hello ${subject}", encoding="utf-8")
            (workflow_dir / "workflow.json").write_text(
                json.dumps(
                    {
                        "id": "demo",
                        "defaults": {"run_root": str(root / "runs")},
                        "steps": {
                            "draft": {
                                "prompt_template": "prompts/draft.md",
                                "runner": "gemini_cli",
                                "checker": "none",
                                "allow_edits": False,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            workflow = module.load_workflow_from_directory(workflow_dir)
            registry = module.build_registry()
            engine = module.SupervisorEngine(registry)
            outcome = engine.run(
                workflow=workflow,
                step_id="draft",
                inputs={"subject": "world"},
                runner_name=None,
                timeout_seconds=60,
                dry_run=True,
            )

            prompt_path = outcome.parent_run_dir / "attempt-01" / "prompt.md"
            meta_path = outcome.parent_run_dir / "meta.json"

            self.assertTrue(prompt_path.exists())
            self.assertTrue(meta_path.exists())
            self.assertEqual(prompt_path.read_text(encoding="utf-8"), "Hello world")
            self.assertEqual(outcome.status, "dry_run")

    def test_role5_checker_reports_placeholder_mismatch(self) -> None:
        module = load_module(SCRIPT_PATH, "sop_supervisor_script_checker")
        checker = module.AssessmentRole5Checker()

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            chapter_dir = root / "book" / "chapter-01"
            chapter_dir.mkdir(parents=True)
            (chapter_dir / "role-2-output.md").write_text("### 维度 1\n", encoding="utf-8")
            (chapter_dir / "role-5-output.md").write_text(
                "# Report\n<!-- PH-INDEX-01 -->\n<!-- PH-INDEX-02 -->\n",
                encoding="utf-8",
            )
            (chapter_dir / "role-5-progress.md").write_text(
                "- [ ] PH-INDEX-01\n",
                encoding="utf-8",
            )
            attempt_dir = root / "run" / "attempt-01"
            attempt_dir.mkdir(parents=True)
            request = module.CheckRequest(
                workflow_id="assessment",
                step_id="role5",
                attempt_dir=attempt_dir,
                workflow_context={
                    "book": "book",
                    "chapter": "chapter-01",
                    "chapter_dir": str(chapter_dir),
                },
                runner_result=None,
                user_inputs={"book": "book", "chapter": "chapter-01"},
            )

            result = checker.check(request)

        self.assertFalse(result.ok)
        self.assertIn("placeholders", result.report_markdown)
        self.assertIn("rework", result.rework_payload)

    def test_role6_checker_validates_structure_and_quote_source(self) -> None:
        from supervisor.checkers.assessment_role6 import AssessmentRole6Checker
        from supervisor.core.models import CheckRequest

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            chapter_dir = root / "book" / "chapter-01"
            chapter_dir.mkdir(parents=True)
            (chapter_dir / "role-2-output.md").write_text(
                "### 维度 1：应该如此\n",
                encoding="utf-8",
            )
            (chapter_dir / "role-5-output.md").write_text(
                "\n".join(
                    [
                        "# Report",
                        "## 二、维度详写",
                        "### 维度 1：应该如此",
                        "#### 高分版",
                        "你能看见变化，并且回到下一步。",
                        "",
                        "**特征描述**",
                        "你能先看眼前还能做什么。",
                        "",
                        "**原因解析**",
                        "你把行动放在预设之前。",
                        "",
                        "**影响分析**",
                        "短期看更稳。长期看更灵活。",
                        "",
                        "**建议方向**",
                        '> "信念是为你服务的，有效就用，无效就改变它。" —— 李中莹',
                        "把注意力放回当下能做的事。",
                        "",
                        "#### 低分版",
                        "你会停在原先预想里，再慢慢转向现实。",
                        "",
                        "**特征描述**",
                        "你会先反复想事情为什么不是原来那样。",
                        "",
                        "**原因解析**",
                        "你很在乎事情是否按预期发生。",
                        "",
                        "**影响分析**",
                        "短期看更累。长期看更容易停住。",
                        "",
                        "**建议方向**",
                        '> "因为我们并不完美，所以我们没有资格要求世界完美。" —— 李中莹',
                        "先把焦点移回此刻还能做的一步。",
                        "",
                        "## 三、画像详写（共 2 个）",
                        "### 画像 L",
                        "**特征描述**",
                        "你能先看手边能做的事，再决定下一步。",
                        "",
                        "**原因解析**",
                        "你的注意力比较容易回到现实场景里。",
                        "",
                        "### 画像 H",
                        "**特征描述**",
                        "你会在停顿后回到事情本身。",
                        "",
                        "**原因解析**",
                        "你较少把旧预期当成唯一标准。",
                    ]
                ),
                encoding="utf-8",
            )
            quote_library = root / "quotes.md"
            quote_library.write_text(
                "\n".join(
                    [
                        "信念是为你服务的，有效就用，无效就改变它。",
                        "因为我们并不完美，所以我们没有资格要求世界完美。",
                    ]
                ),
                encoding="utf-8",
            )

            request = CheckRequest(
                workflow_id="assessment",
                step_id="role6",
                attempt_dir=root / "run" / "attempt-01",
                workflow_context={
                    "book": "book",
                    "chapter": "chapter-01",
                    "chapter_dir": str(chapter_dir),
                    "quote_library_path": str(quote_library),
                },
                runner_result=None,
                user_inputs={"dimensions": 1},
            )
            result = AssessmentRole6Checker().check(request)

        self.assertTrue(result.ok)
        self.assertIn("C8 金句去重 + 来源核验", result.report_markdown)

    def test_role7_checker_detects_dimension_chain_mismatch(self) -> None:
        from supervisor.checkers.assessment_role7 import AssessmentRole7Checker
        from supervisor.core.models import CheckRequest

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            chapter_dir = root / "book" / "chapter-01"
            chapter_dir.mkdir(parents=True)
            (chapter_dir / "role-1-output.md").write_text("- 痛点 1：示例\n", encoding="utf-8")
            (chapter_dir / "role-2-output.md").write_text(
                "\n".join(
                    [
                        "### 维度 1：应该如此",
                        "",
                        "| 档位 | 展示分段 | 原始总分范围 | 语气方向 |",
                        "|------|---------|-------------|---------|",
                        "| 第一档（最高） | 80–100 | 21–25 | 往往/通常 |",
                        "| 第二档 | 60–79 | 16–20 | 往往/通常 |",
                    ]
                ),
                encoding="utf-8",
            )
            (chapter_dir / "role-3-output.md").write_text(
                "\n".join(
                    [
                        "## 维度 1：别的名字",
                        "| 题号 | 题干 | 正/反向 |",
                        "|------|------|--------|",
                        "| 1.1 | A | 正 |",
                        "| 1.2 | B | 正 |",
                        "| 1.3 | C | 正 |",
                        "| 1.4 | D | 正 |",
                        "| 1.5 | E | **反** |",
                    ]
                ),
                encoding="utf-8",
            )
            (chapter_dir / "role-5-output.md").write_text(
                "\n".join(
                    [
                        "## 一、指数区间描述（2 段）",
                        "### 第一档 80–100",
                        "a",
                        "### 第二档 60–79",
                        "b",
                        "## 二、维度详写",
                        "### 维度 1：应该如此",
                        "## 三、画像详写（共 2 个）",
                        "### 画像 L",
                        "**特征描述**",
                        "x",
                        "**原因解析**",
                        "y",
                        "### 画像 H",
                        "**特征描述**",
                        "x",
                        "**原因解析**",
                        "y",
                    ]
                ),
                encoding="utf-8",
            )
            (chapter_dir / "role-5-progress.md").write_text("", encoding="utf-8")
            quote_library = root / "quotes.md"
            quote_library.write_text("", encoding="utf-8")

            request = CheckRequest(
                workflow_id="assessment",
                step_id="role7",
                attempt_dir=root / "run" / "attempt-01",
                workflow_context={
                    "book": "book",
                    "chapter": "chapter-01",
                    "chapter_dir": str(chapter_dir),
                    "quote_library_path": str(quote_library),
                },
                runner_result=None,
                user_inputs={"dimensions": 1},
            )
            result = AssessmentRole7Checker().check(request)

        self.assertFalse(result.ok)
        self.assertIn("V1", result.report_markdown)

    def test_legacy_wrapper_maps_run_to_new_engine(self) -> None:
        module = load_module(LEGACY_SCRIPT_PATH, "assessment_supervisor_legacy_wrapper")
        args = module.parse_args(
            [
                "run",
                "--book",
                "重塑心灵-NLP",
                "--chapter",
                "chapter-02",
                "--role",
                "5",
                "--batch",
                "test batch",
                "--dry-run",
            ]
        )

        self.assertEqual(args.command, "run")
        self.assertEqual(args.role, "5")
        self.assertEqual(args.batch, "test batch")


if __name__ == "__main__":
    unittest.main()
