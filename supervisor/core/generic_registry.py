from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Iterable

from supervisor.runners.codex_cli import CodexCliRunner
from supervisor.runners.gemini_cli import GeminiCliRunner


@dataclass
class GenericRegistry:
    runners: dict[str, object]
    checkers: dict[str, object]


def build_registry(workflow_ids: Iterable[str] = ()) -> GenericRegistry:
    registry = GenericRegistry(
        runners={
            "codex_cli": CodexCliRunner(),
            "gemini_cli": GeminiCliRunner(),
        },
        checkers={},
    )
    for workflow_id in workflow_ids:
        module_name = f"supervisor.workflows.{workflow_id}.generic_registry"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:
                continue
            raise
        module.register(registry)
    return registry
