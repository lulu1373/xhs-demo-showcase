from __future__ import annotations

from string import Template


def render_prompt_text(template_text: str, variables: dict[str, object]) -> str:
    normalized = {key: str(value) for key, value in variables.items()}
    return Template(template_text).substitute(normalized)

