from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Optional

from supervisor.core.artifacts import make_parent_run_dir, write_json, write_text
from supervisor.core.models import (
    CheckRequest,
    RunOutcome,
    RunnerRequest,
    RetryPolicy,
    StepConfig,
    WorkflowConfig,
    WorkflowDefaults,
)
from supervisor.core.templating import render_prompt_text


ROOT = Path(__file__).resolve().parents[2]


def _load_yaml_or_json(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency boundary
        raise SystemExit(f"YAML config requires PyYAML: {exc}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_workflow_config(path: Path) -> WorkflowConfig:
    raw = _load_yaml_or_json(path)
    defaults_raw = raw.get("defaults", {})
    default_retry_raw = defaults_raw.get("retry", {})
    defaults = WorkflowDefaults(
        run_root=str(defaults_raw["run_root"]),
        retry=RetryPolicy(
            max_attempts=int(default_retry_raw.get("max_attempts", 1)),
            mode=str(default_retry_raw.get("mode", "none")),
        ),
    )
    steps: dict[str, StepConfig] = {}
    for step_id, step_raw in raw.get("steps", {}).items():
        retry_raw = step_raw.get("retry", {})
        retry = RetryPolicy(
            max_attempts=int(retry_raw.get("max_attempts", defaults.retry.max_attempts)),
            mode=str(retry_raw.get("mode", defaults.retry.mode)),
        )
        steps[step_id] = StepConfig(
            step_id=step_id,
            prompt_template=str(step_raw["prompt_template"]),
            runner=str(step_raw["runner"]),
            checker=str(step_raw.get("checker", "none")),
            allow_edits=bool(step_raw.get("allow_edits", False)),
            retry=retry,
        )
    return WorkflowConfig(
        workflow_id=str(raw["id"]),
        workflow_dir=path.parent,
        defaults=defaults,
        steps=steps,
    )


def load_workflow_from_directory(workflow_dir: Path) -> WorkflowConfig:
    yaml_path = workflow_dir / "workflow.yaml"
    json_path = workflow_dir / "workflow.json"
    if yaml_path.exists():
        return load_workflow_config(yaml_path)
    if json_path.exists():
        return load_workflow_config(json_path)
    raise SystemExit(f"Missing workflow config in {workflow_dir}")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot load module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SupervisorEngine:
    def __init__(self, registry) -> None:
        self.registry = registry

    def _workflow_context_module(self, workflow: WorkflowConfig):
        path = workflow.workflow_dir / "context.py"
        if not path.exists():
            return None
        return _load_module(path, f"{workflow.workflow_id}_context")

    def _workflow_rework_module(self, workflow: WorkflowConfig):
        path = workflow.workflow_dir / "rework.py"
        if not path.exists():
            return None
        return _load_module(path, f"{workflow.workflow_id}_rework")

    def _render_step_prompt(
        self,
        workflow: WorkflowConfig,
        step: StepConfig,
        inputs: dict[str, object],
    ) -> tuple[str, dict[str, object]]:
        context_module = self._workflow_context_module(workflow)
        if context_module is None:
            context = dict(inputs)
        else:
            context = context_module.build_context(step.step_id, inputs, workflow.workflow_dir)
        prompt_template_path = workflow.workflow_dir / step.prompt_template
        template_text = prompt_template_path.read_text(encoding="utf-8")
        prompt = render_prompt_text(template_text, {**context, **inputs})
        return prompt, context

    def _run_check(
        self,
        workflow: WorkflowConfig,
        step: StepConfig,
        attempt_dir: Path,
        context: dict[str, object],
        inputs: dict[str, object],
        runner_result,
    ):
        if step.checker == "none":
            return None
        checker = self.registry.checkers[step.checker]
        request = CheckRequest(
            workflow_id=workflow.workflow_id,
            step_id=step.step_id,
            attempt_dir=attempt_dir,
            workflow_context=context,
            runner_result=runner_result,
            user_inputs=inputs,
        )
        return checker.check(request)

    def run(
        self,
        workflow: WorkflowConfig,
        step_id: str,
        inputs: dict[str, object],
        runner_name: Optional[str],
        timeout_seconds: int,
        dry_run: bool = False,
        compatibility_source: str = "",
    ) -> RunOutcome:
        if step_id not in workflow.steps:
            raise SystemExit(f"Unknown step: {step_id}")
        step = workflow.steps[step_id]
        prompt, context = self._render_step_prompt(workflow, step, inputs)
        job_id = str(inputs.get("job_id") or inputs.get("chapter") or inputs.get("book") or "job")
        parent_run_dir = make_parent_run_dir(
            ROOT,
            workflow.defaults.run_root,
            workflow.workflow_id,
            step.step_id,
            job_id,
        )
        meta_path = parent_run_dir / "meta.json"
        selected_runner = runner_name or step.runner
        final_status = "dry_run"
        final_runner_result = None
        final_check_result = None

        attempts = max(1, step.retry.max_attempts)
        current_prompt = prompt
        for index in range(1, attempts + 1):
            attempt_dir = parent_run_dir / f"attempt-{index:02d}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            prompt_path = attempt_dir / "prompt.md"
            write_text(prompt_path, current_prompt)

            meta = {
                "workflow_id": workflow.workflow_id,
                "step_id": step.step_id,
                "runner": selected_runner,
                "checker": step.checker,
                "inputs": inputs,
                "attempt": index,
                "compatibility_source": compatibility_source,
            }
            write_json(meta_path, meta)

            if dry_run:
                return RunOutcome(
                    status="dry_run",
                    workflow_id=workflow.workflow_id,
                    step_id=step.step_id,
                    parent_run_dir=parent_run_dir,
                    attempt_dir=attempt_dir,
                    prompt_path=prompt_path,
                    meta_path=meta_path,
                    runner_result=None,
                    check_result=None,
                )

            runner = self.registry.runners[selected_runner]
            request = RunnerRequest(
                prompt=current_prompt,
                cwd=ROOT,
                timeout_seconds=timeout_seconds,
                allow_edits=bool(inputs.get("allow_edits", step.allow_edits)),
                env={},
                metadata=meta,
            )
            runner_result = runner.run(request)
            final_runner_result = runner_result
            write_json(attempt_dir / "command.json", runner_result.command)
            write_text(attempt_dir / "stdout.txt", runner_result.stdout_text)
            write_text(attempt_dir / "stderr.txt", runner_result.stderr_text)
            if runner_result.parsed_output is not None:
                write_json(attempt_dir / "runner-output.json", runner_result.parsed_output)

            check_result = self._run_check(
                workflow=workflow,
                step=step,
                attempt_dir=attempt_dir,
                context=context,
                inputs=inputs,
                runner_result=runner_result,
            )
            final_check_result = check_result
            if check_result is not None:
                write_text(attempt_dir / "check-report.md", check_result.report_markdown)
                if check_result.ok:
                    final_status = "passed"
                    return RunOutcome(
                        status=final_status,
                        workflow_id=workflow.workflow_id,
                        step_id=step.step_id,
                        parent_run_dir=parent_run_dir,
                        attempt_dir=attempt_dir,
                        prompt_path=prompt_path,
                        meta_path=meta_path,
                        runner_result=runner_result,
                        check_result=check_result,
                    )
                rework_module = self._workflow_rework_module(workflow)
                if (
                    step.retry.mode == "rework"
                    and index < attempts
                    and rework_module is not None
                    and check_result.rework_payload
                ):
                    current_prompt = rework_module.build_rework_prompt(
                        step.step_id,
                        check_result.rework_payload,
                        inputs,
                        context,
                    )
                    continue
                final_status = "failed"
                return RunOutcome(
                    status=final_status,
                    workflow_id=workflow.workflow_id,
                    step_id=step.step_id,
                    parent_run_dir=parent_run_dir,
                    attempt_dir=attempt_dir,
                    prompt_path=prompt_path,
                    meta_path=meta_path,
                    runner_result=runner_result,
                    check_result=check_result,
                )

            final_status = "completed" if runner_result.exit_code == 0 else "failed"
            return RunOutcome(
                status=final_status,
                workflow_id=workflow.workflow_id,
                step_id=step.step_id,
                parent_run_dir=parent_run_dir,
                attempt_dir=attempt_dir,
                prompt_path=prompt_path,
                meta_path=meta_path,
                runner_result=runner_result,
                check_result=None,
            )

        return RunOutcome(
            status=final_status,
            workflow_id=workflow.workflow_id,
            step_id=step.step_id,
            parent_run_dir=parent_run_dir,
            attempt_dir=parent_run_dir / f"attempt-{attempts:02d}",
            prompt_path=parent_run_dir / f"attempt-{attempts:02d}" / "prompt.md",
            meta_path=meta_path,
            runner_result=final_runner_result,
            check_result=final_check_result,
        )

    def check_attempt(self, attempt_dir: Path):
        meta_path = attempt_dir.parent / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        workflow_dir = ROOT / "supervisor" / "workflows" / meta["workflow_id"]
        workflow = load_workflow_from_directory(workflow_dir)
        step = workflow.steps[meta["step_id"]]
        context_module = self._workflow_context_module(workflow)
        inputs = dict(meta.get("inputs", {}))
        if context_module is None:
            context = dict(inputs)
        else:
            context = context_module.build_context(step.step_id, inputs, workflow.workflow_dir)
        result = self._run_check(workflow, step, attempt_dir, context, inputs, None)
        if result is None:
            raise SystemExit("No checker configured for this attempt")
        write_text(attempt_dir / "check-report.md", result.report_markdown)
        return result
