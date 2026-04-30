#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor.core.engine import (
    SupervisorEngine,
    load_workflow_config,
    load_workflow_from_directory,
)
from supervisor.core.models import CheckRequest, RunnerRequest, RunnerResult
from supervisor.core.generic_registry import build_registry
from supervisor.core.templating import render_prompt_text
from supervisor.runners.gemini_cli import GeminiCliRunner

WORKFLOWS_DIR = ROOT / "supervisor" / "workflows"


def workflow_dir_for(workflow_id: str) -> Path:
    path = WORKFLOWS_DIR / workflow_id
    if not path.exists():
        raise SystemExit(f"Unknown workflow directory: {path}")
    return path


def parse_input_pairs(values: list[str]) -> dict[str, str]:
    payload: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise SystemExit(f"Invalid --input value: {item}")
        key, value = item.split("=", 1)
        payload[key] = value
    return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generalized SOP supervisor")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run one workflow step")
    run.add_argument("--workflow", required=True)
    run.add_argument("--step", required=True)
    run.add_argument("--runner")
    run.add_argument("--input", action="append", default=[])
    run.add_argument("--timeout", type=int, default=900)
    run.add_argument("--dry-run", action="store_true")

    check = sub.add_parser("check", help="Run checker on existing attempt dir")
    check.add_argument("--attempt-dir", required=True)

    smoke = sub.add_parser("smoke", help="Smoke test one runner")
    smoke.add_argument("--runner", default="gemini_cli")
    smoke.add_argument("--timeout", type=int, default=120)

    return parser.parse_args(argv)


def print_runner_output(result: RunnerResult) -> None:
    if result.stdout_text:
        print(result.stdout_text)
        return
    parsed = result.parsed_output
    if isinstance(parsed, dict):
        last_message = parsed.get("last_message")
        if last_message:
            print(last_message)


def run_command(args: argparse.Namespace) -> int:
    workflow = load_workflow_from_directory(workflow_dir_for(args.workflow))
    registry = build_registry([args.workflow])
    engine = SupervisorEngine(registry)
    outcome = engine.run(
        workflow=workflow,
        step_id=args.step,
        inputs=parse_input_pairs(args.input),
        runner_name=args.runner,
        timeout_seconds=args.timeout,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print(f"Dry run prompt saved: {outcome.prompt_path}")
        return 0
    if outcome.check_result is not None:
        print(outcome.check_result.report_markdown)
        return 0 if outcome.check_result.ok else 2
    if outcome.runner_result is not None:
        print_runner_output(outcome.runner_result)
    return 0 if outcome.status in {"completed", "passed"} else 2


def check_command(args: argparse.Namespace) -> int:
    attempt_dir = Path(args.attempt_dir)
    meta_path = attempt_dir.parent / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    registry = build_registry([str(meta["workflow_id"])])
    engine = SupervisorEngine(registry)
    result = engine.check_attempt(attempt_dir)
    print(result.report_markdown)
    return 0 if result.ok else 2


def smoke_command(args: argparse.Namespace) -> int:
    registry = build_registry()
    runner = registry.runners[args.runner]
    result = runner.smoke(ROOT, timeout_seconds=args.timeout)
    print_runner_output(result)
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
