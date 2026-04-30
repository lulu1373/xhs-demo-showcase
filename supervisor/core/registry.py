from __future__ import annotations

from dataclasses import dataclass

from supervisor.checkers.assessment_role6 import AssessmentRole6Checker
from supervisor.checkers.assessment_role7 import AssessmentRole7Checker
from supervisor.checkers.assessment_role5 import AssessmentRole5Checker
from supervisor.runners.gemini_cli import GeminiCliRunner


@dataclass
class Registry:
    runners: dict[str, object]
    checkers: dict[str, object]


def build_registry() -> Registry:
    return Registry(
        runners={
            "gemini_cli": GeminiCliRunner(),
        },
        checkers={
            "assessment_role5": AssessmentRole5Checker(),
            "assessment_role6": AssessmentRole6Checker(),
            "assessment_role7": AssessmentRole7Checker(),
        },
    )
