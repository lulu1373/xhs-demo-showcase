from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class RetryPolicy:
    max_attempts: int = 1
    mode: str = "none"


@dataclass
class WorkflowDefaults:
    run_root: str
    retry: RetryPolicy = field(default_factory=RetryPolicy)


@dataclass
class StepConfig:
    step_id: str
    prompt_template: str
    runner: str
    checker: str
    allow_edits: bool
    retry: RetryPolicy


@dataclass
class WorkflowConfig:
    workflow_id: str
    workflow_dir: Path
    defaults: WorkflowDefaults
    steps: dict[str, StepConfig]


@dataclass
class RunnerRequest:
    prompt: str
    cwd: Path
    timeout_seconds: int
    allow_edits: bool
    env: dict[str, str]
    metadata: dict[str, Any]


@dataclass
class RunnerResult:
    command: list[str]
    exit_code: int
    stdout_text: str
    stderr_text: str
    parsed_output: Optional[Any]
    started_at: str
    finished_at: str


@dataclass
class CheckRequest:
    workflow_id: str
    step_id: str
    attempt_dir: Path
    workflow_context: dict[str, Any]
    runner_result: Optional[RunnerResult]
    user_inputs: dict[str, Any]


@dataclass
class CheckResult:
    ok: bool
    summary: str
    report_markdown: str
    findings: list[str]
    rework_payload: dict[str, Any]


@dataclass
class RunOutcome:
    status: str
    workflow_id: str
    step_id: str
    parent_run_dir: Path
    attempt_dir: Path
    prompt_path: Path
    meta_path: Path
    runner_result: Optional[RunnerResult]
    check_result: Optional[CheckResult]

