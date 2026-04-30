from __future__ import annotations


def build_rework_prompt(
    step_id: str,
    rework_payload: dict[str, object],
    inputs: dict[str, object],
    context: dict[str, object],
) -> str:
    if not rework_payload:
        raise ValueError("Missing rework payload")
    return str(rework_payload["rework"])

