# ECC for AIWork on Codex

This project uses the global ECC installation in `/Users/lulu/.codex` and adds a project-local Codex overlay here.

## Model Recommendations

| Task Type | Recommended Model |
|-----------|-------------------|
| Routine coding, tests, formatting | GPT 5.4 |
| Complex features, architecture | GPT 5.4 |
| Debugging and refactoring | GPT 5.4 |
| Security review | GPT 5.4 |

## How This Repo Uses ECC

- Shared agents and skills live under `/Users/lulu/.codex`.
- This repo keeps only the project-specific Codex overlay in `.codex/`.
- Codex does not support Claude Code hook parity yet, so continuous-learning and hook-heavy workflows remain partial in this harness.

## Multi-Agent Support

Project-local agent roles are defined under `.codex/agents/`:

- `explorer` for read-only investigation
- `reviewer` for correctness and security review
- `docs_researcher` for documentation verification

## Practical Guidance

- Prefer `AGENTS.md` plus `.codex/AGENTS.md` as the instruction source for this repo.
- Keep project-specific instructions here; keep reusable ECC capabilities in the global install.
- When a task depends on external APIs or current docs, verify against primary documentation before landing changes.
