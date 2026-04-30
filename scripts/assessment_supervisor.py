#!/usr/bin/env python3
"""Compatibility shim for the assessment workflow on top of the new SOP supervisor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor.checkers.assessment_role5 import AssessmentRole5Checker
from supervisor.core.engine import SupervisorEngine, load_workflow_from_directory
from supervisor.core.registry import build_registry
from supervisor.core.artifacts import write_text
from supervisor.core.models import CheckRequest
from supervisor.workflows.assessment.context import build_context

ASSESSMENT_WORKFLOW_DIR = ROOT / "supervisor" / "workflows" / "assessment"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemini assessment supervisor")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--book", required=True)
        p.add_argument("--chapter", required=True)
        p.add_argument("--role", default="5")
        p.add_argument("--dimensions", type=int)

    check = sub.add_parser("check", help="Run local deterministic checks")
    add_common(check)
    check.add_argument("--output")

    run = sub.add_parser("run", help="Execute Gemini CLI and save artifacts")
    add_common(run)
    run.add_argument("--batch", help="Batch/range instruction for the worker")
    run.add_argument("--allow-edits", action="store_true")
    run.add_argument("--first-batch", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--timeout", type=int, default=900)

    smoke = sub.add_parser("smoke", help="Run a minimal Gemini CLI smoke test")
    smoke.add_argument("--timeout", type=int, default=120)

    return parser.parse_args(argv)


def _workflow():
    return load_workflow_from_directory(ASSESSMENT_WORKFLOW_DIR)


def _step_for_role(role: str) -> str:
    return {
        "5": "role5",
        "6": "role6",
        "7": "role7",
    }.get(role, "role_generic")


def run_command(args: argparse.Namespace) -> int:
    workflow = _workflow()
    registry = build_registry()
    engine = SupervisorEngine(registry)
    inputs = {
        "book": args.book,
        "chapter": args.chapter,
        "role": args.role,
        "batch": args.batch or "",
        "first_batch": "true" if args.first_batch else "false",
        "allow_edits": "true" if args.allow_edits else "false",
    }
    if args.dimensions is not None:
        inputs["dimensions"] = str(args.dimensions)
    outcome = engine.run(
        workflow=workflow,
        step_id=_step_for_role(args.role),
        inputs=inputs,
        runner_name=None,
        timeout_seconds=args.timeout,
        dry_run=args.dry_run,
        compatibility_source="assessment_supervisor.py",
    )
    if args.dry_run:
        print(f"Dry run prompt saved: {outcome.prompt_path}")
        return 0
    if outcome.check_result is not None:
        print(outcome.check_result.report_markdown)
        print(f"Run artifacts: {outcome.parent_run_dir}")
        return 0 if outcome.check_result.ok else 2
    if outcome.runner_result is not None:
        print(outcome.runner_result.stdout_text)
    print(f"Run artifacts: {outcome.parent_run_dir}")
    return 0 if outcome.status in {"completed", "passed"} else 2


def check_command(args: argparse.Namespace) -> int:
    context = build_context(
        _step_for_role(args.role),
        {
            "book": args.book,
            "chapter": args.chapter,
            "role": args.role,
            "first_batch": "true",
            "allow_edits": "false",
        },
        ASSESSMENT_WORKFLOW_DIR,
    )
    request = CheckRequest(
        workflow_id="assessment",
        step_id=_step_for_role(args.role),
        attempt_dir=Path(context["chapter_dir"]),
        workflow_context=context,
        runner_result=None,
        user_inputs={
            "book": args.book,
            "chapter": args.chapter,
            **({"dimensions": args.dimensions} if args.dimensions is not None else {}),
        },
    )
    registry = build_registry()
    checker_name = {
        "5": "assessment_role5",
        "6": "assessment_role6",
        "7": "assessment_role7",
    }.get(args.role)
    if checker_name is None:
        raise SystemExit(f"No local checker configured for Role {args.role}")
    result = registry.checkers[checker_name].check(request)
    if args.output:
        write_text(Path(args.output), result.report_markdown)
    print(result.report_markdown)
    return 0 if result.ok else 2


def smoke_command(args: argparse.Namespace) -> int:
    runner = build_registry().runners["gemini_cli"]
    result = runner.smoke(ROOT, timeout_seconds=args.timeout)
    response = ""
    parsed = result.parsed_output
    if isinstance(parsed, dict):
        response = str(parsed.get("response", ""))
    if not response:
        response = result.stdout_text.strip()[:200]
    print(f"Gemini smoke response: {response}")
    return result.exit_code


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.command == "run":
        return run_command(args)
    if args.command == "check":
        return check_command(args)
    if args.command == "smoke":
        return smoke_command(args)
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
