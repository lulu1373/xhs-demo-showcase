from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess

from supervisor.core.models import RunnerRequest, RunnerResult


class GeminiCliRunner:
    name = "gemini_cli"

    def build_command(self, request: RunnerRequest) -> list[str]:
        gemini = shutil.which("gemini")
        if not gemini:
            raise SystemExit("gemini CLI not found on PATH")
        approval_mode = "auto_edit" if request.allow_edits else "plan"
        return [
            gemini,
            "-p",
            request.prompt,
            "--approval-mode",
            approval_mode,
            "--output-format",
            "json",
            "--skip-trust",
        ]

    def run(self, request: RunnerRequest) -> RunnerResult:
        command = self.build_command(request)
        started_at = dt.datetime.now().isoformat()
        completed = subprocess.run(
            command,
            cwd=str(request.cwd),
            text=True,
            capture_output=True,
            timeout=request.timeout_seconds,
            check=False,
            env=request.env or None,
        )
        finished_at = dt.datetime.now().isoformat()
        parsed_output = None
        try:
            parsed_output = json.loads(completed.stdout) if completed.stdout.strip() else None
        except json.JSONDecodeError:
            parsed_output = None
        return RunnerResult(
            command=command,
            exit_code=completed.returncode,
            stdout_text=completed.stdout,
            stderr_text=completed.stderr,
            parsed_output=parsed_output,
            started_at=started_at,
            finished_at=finished_at,
        )

    def smoke(self, cwd, timeout_seconds: int = 120) -> RunnerResult:
        request = RunnerRequest(
            prompt="Reply with OK only.",
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            allow_edits=False,
            env={},
            metadata={},
        )
        return self.run(request)

