from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def timestamp_slug() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def resolve_run_root(root_dir: Path, run_root: str) -> Path:
    run_root_path = Path(run_root)
    if run_root_path.is_absolute():
        return run_root_path
    return root_dir / run_root_path


def make_parent_run_dir(
    root_dir: Path,
    run_root: str,
    workflow_id: str,
    step_id: str,
    job_id: str,
) -> Path:
    base = resolve_run_root(root_dir, run_root) / workflow_id / job_id
    parent = base / f"{timestamp_slug()}-{step_id}"
    parent.mkdir(parents=True, exist_ok=True)
    return parent

