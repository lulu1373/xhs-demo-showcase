from __future__ import annotations

import datetime as dt
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from supervisor.core.models import RunnerRequest, RunnerResult


class CodexCliRunner:
    name = "codex_cli"

    def build_command(self, request: RunnerRequest, output_path: Path) -> list[str]:
        codex = shutil.which("codex")
        if not codex:
            raise SystemExit("codex CLI not found on PATH")
        sandbox_mode = "workspace-write" if request.allow_edits else "read-only"
        return [
            codex,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            sandbox_mode,
            "--ask-for-approval",
            "never",
            "--color",
            "never",
            "-C",
            str(request.cwd),
            "-o",
            str(output_path),
            request.prompt,
        ]

    def run(self, request: RunnerRequest) -> RunnerResult:
        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "last-message.txt"
            command = self.build_command(request, output_path)
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
            last_message = ""
            if output_path.exists():
                last_message = output_path.read_text(encoding="utf-8")
            parsed_output = {"last_message": last_message} if last_message else None
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
