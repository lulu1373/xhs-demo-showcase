# SOP Supervisor V1 Design

## Summary

Build a generalized SOP supervisor that can orchestrate linear task workflows, call different execution backends, run deterministic local checks, and generate rework instructions when outputs fail validation.

V1 is intentionally constrained:

- linear SOP only
- single-worker execution per step
- retry/rework loop supported
- no branching graph execution
- no parallel steps
- no UI or service layer

Implementation constraints:

- must run on Python 3.9
- should preserve the existing “script-first” usage style
- should avoid introducing heavy runtime dependencies

The existing `scripts/assessment_supervisor.py` will be treated as the seed implementation for one workflow (`assessment`) and one checker family (`assessment_role5`), not as the long-term architecture.

## Why

The current supervisor already proves three useful behaviors:

1. it can build an execution prompt from local SOP materials
2. it can run an external worker (`gemini` CLI)
3. it can apply deterministic local acceptance checks and produce a bounded rework instruction

What is missing is separation of concerns. The current script hard-binds:

- workflow definition
- prompt assembly
- Gemini execution
- Role 5 assessment-specific checking
- output directory conventions

That makes it hard to:

- reuse the supervisor for non-assessment SOPs
- add new runners without forking the script
- add new checkers without growing a monolith
- publish the tool as a generalized “supervisor engine”

## Goals

- Generalize the supervisor into a reusable local orchestration tool.
- Keep SOP flow configurable without inventing a complex DSL.
- Support multiple runners behind one stable interface.
- Preserve deterministic checking as first-class functionality.
- Preserve rework generation and bounded retry loops.
- Keep all artifacts on disk for auditability.

## Non-Goals

- DAG execution
- multi-agent fan-out/fan-in
- distributed execution
- database-backed run storage
- rich UI
- remote API service
- workflow authoring in a visual builder
- declarative checker logic in YAML

## Primary Use Cases

1. Run a book-assessment workflow step with Gemini, then apply local quality gates.
2. Re-run a failed step with a generated rework prompt.
3. Swap the execution backend later without changing workflow semantics.
4. Add a new SOP that follows the same “prompt -> run -> check -> rework” loop.

## Design Principles

- Configuration describes flow, not business logic.
- Runners execute work; they do not understand workflow semantics.
- Checkers validate outputs; they do not invoke models.
- Workflow-specific context loading lives in workflow adapters, not in the engine core.
- Every run writes an inspectable artifact bundle to disk.
- Rework should be bounded and explicit, never “rewrite everything”.
- V1 should prefer stdlib-friendly implementation choices where possible.

## Proposed Repository Structure

```text
scripts/
  sop_supervisor.py

supervisor/
  __init__.py
  cli.py
  core/
    engine.py
    models.py
    artifacts.py
    registry.py
    templating.py
  runners/
    base.py
    gemini_cli.py
  checkers/
    base.py
    assessment_role5.py
  workflows/
    assessment/
      workflow.yaml
      prompts/
        role5_write.md
        role5_rework.md
      context.py
      rework.py
```

Notes:

- `scripts/sop_supervisor.py` is the stable CLI entrypoint.
- `scripts/assessment_supervisor.py` should remain temporarily as a compatibility shim during migration.
- `supervisor/core` contains reusable engine logic.
- `supervisor/runners` contains backend adapters.
- `supervisor/checkers` contains deterministic validation logic.
- `supervisor/workflows` contains workflow-specific configuration and adapters.

## Core Concepts

### Workflow

A workflow is a named SOP package. It defines:

- available steps
- prompt template per step
- default runner per step
- checker binding per step
- retry policy per step
- whether edits are permitted

### Step

A step is one linear unit of supervised work. In V1, a workflow run executes exactly one selected step at a time.

Each step may:

- load workflow-specific context
- render a prompt
- call one runner
- run one checker
- optionally generate a rework prompt and retry

### Runner

A runner is the execution backend. It receives a fully rendered prompt plus runtime options and returns structured execution results.

V1 must include:

- `gemini_cli`

V1 should define interfaces for later additions:

- `codex_cli`
- `claude_cli`

Those later runners do not need concrete implementations in V1.

### Checker

A checker is a deterministic local validator over run artifacts and workflow outputs. It returns:

- pass/fail status
- human-readable report
- structured findings
- optional rework payload seed

### Run Bundle

A run bundle is the persisted artifact directory for one step attempt.

Minimum contents:

- `prompt.md`
- `command.json`
- `stdout.txt`
- `stderr.txt`
- `check-report.md`
- `meta.json`

Optional contents:

- `runner-output.json` when the runner exposes a parsed structured payload
- workflow-specific extra files

If a retry occurs, each attempt gets its own attempt directory under the parent run directory.

## Configuration Model

Configuration should be declarative but shallow. It should not encode arbitrary logic.

V1 file-format rule:

- JSON config is always supported via stdlib.
- YAML config is supported when `PyYAML` is available.
- Workflow authors should not depend on advanced YAML-only features.

Example `workflow.yaml`:

```yaml
id: assessment
name: Assessment Workflow

defaults:
  run_root: docs/assessment-workflow/runs
  retry:
    max_attempts: 2

steps:
  role5_write:
    prompt_template: prompts/role5_write.md
    runner: gemini_cli
    checker: assessment_role5
    allow_edits: true
    retry:
      max_attempts: 2
      mode: rework

  role6_check:
    prompt_template: prompts/role6_check.md
    runner: gemini_cli
    checker: none
    allow_edits: false
```

Rules:

- Workflow config may reference a runner by registered name.
- Workflow config may reference a checker by registered name.
- Workflow config may override retry settings per step.
- Complex context derivation must stay in Python adapters.
- V1 config must stay portable to JSON shape if YAML support is later removed.

## Python Interfaces

The engine should use standard-library-first primitives:

- `dataclasses`
- `pathlib`
- `subprocess`
- `json`
- optional `yaml` import only at config-load boundary

Do not introduce Jinja, Pydantic, or a custom DSL parser in V1.

### Runner Interface

```python
class Runner(Protocol):
    name: str

    def run(self, request: RunnerRequest) -> RunnerResult:
        ...
```

`RunnerRequest` fields:

- `prompt`
- `cwd`
- `timeout_seconds`
- `allow_edits`
- `env`
- `metadata`

`RunnerResult` fields:

- `command`
- `exit_code`
- `stdout_text`
- `stderr_text`
- `parsed_output`
- `started_at`
- `finished_at`

### Checker Interface

```python
class Checker(Protocol):
    name: str

    def check(self, request: CheckRequest) -> CheckResult:
        ...
```

`CheckRequest` fields:

- `workflow_id`
- `step_id`
- `attempt_dir`
- `workflow_context`
- `runner_result`
- `user_inputs`

`CheckResult` fields:

- `ok`
- `summary`
- `report_markdown`
- `findings`
- `rework_payload`

### Workflow Context Loader

Each workflow may provide a Python context loader:

```python
def build_context(inputs: dict[str, str]) -> WorkflowContext:
    ...
```

This is where workflow-specific path resolution belongs. For assessment, that includes:

- book/chapter directories
- domain-pack path
- relevant role skill path
- agent file path
- target output files

This keeps the engine generic and avoids hard-coding assessment concepts into core logic.

### Prompt Rendering

V1 prompt rendering should use a simple stdlib mechanism such as `string.Template` or a constrained `str.format_map` wrapper.

Requirements:

- missing keys should raise explicit errors
- rendering should remain text-first
- no logic-in-template features
- no third-party templating dependency

## Execution Flow

V1 run flow:

1. Parse CLI args.
2. Load workflow config.
3. Resolve selected step.
4. Load workflow-specific context.
5. Render prompt template with inputs and context.
6. Create run bundle directory.
7. Invoke runner.
8. Persist prompt, command, stdout, stderr, and metadata.
9. Invoke checker if configured.
10. Persist checker report.
11. If check passes, mark run complete.
12. If check fails and retry policy allows:
    - generate rework prompt from checker output
    - run another attempt
13. Stop when pass or retry limit reached.

## Rework Model

V1 rework is checker-driven.

A checker may return a `rework_payload` containing:

- failure summary
- bounded edit instructions
- forbidden rewrite scope
- required verification commands

The workflow’s rework template turns this payload into the next prompt.

This preserves a key property of the current assessment supervisor: failed work should be revised narrowly, not regenerated blindly.

## Artifact Layout

Proposed run layout:

```text
<run_root>/<workflow_id>/<job_id>/<timestamp>-<step_id>/
  meta.json
  attempt-01/
    prompt.md
    command.json
    stdout.json
    stderr.txt
    check-report.md
  attempt-02/
    prompt.md
    command.json
    stdout.json
    stderr.txt
    check-report.md
```

`meta.json` should contain:

- workflow id
- step id
- runner
- checker
- input args
- start/end timestamps
- final status
- final attempt count
- compatibility source when invoked via a legacy wrapper

## CLI Design

V1 commands:

```bash
python3 scripts/sop_supervisor.py run \
  --workflow assessment \
  --step role5_write \
  --runner gemini_cli \
  --input book=重塑心灵-NLP \
  --input chapter=chapter-02 \
  --input batch="画像 LLLLL / LLLLH 返工"

python3 scripts/sop_supervisor.py check \
  --attempt-dir <path>

python3 scripts/sop_supervisor.py smoke \
  --runner gemini_cli
```

Rules:

- `run` executes one step under one workflow.
- `check` reruns deterministic validation over an existing attempt directory and should derive workflow/step metadata from `meta.json` when possible.
- `smoke` verifies runner availability without workflow logic.

## Assessment Workflow Migration

The current `assessment_supervisor.py` should be split as follows:

- `build_prompt(...)` -> assessment workflow prompt template + context loader
- `run_gemini(...)` -> `GeminiCliRunner`
- `check_role5(...)` -> `AssessmentRole5Checker`
- `build_rework_prompt(...)` -> assessment workflow rework template

Assessment-specific constants remain valid, but must move out of engine core.

Compatibility requirement:

- keep `scripts/assessment_supervisor.py` as a thin wrapper over the new engine until downstream shell scripts and skills are migrated
- preserve current CLI affordances for the assessment workflow during the transition

## Error Handling

Expected failures:

- runner binary missing
- runner timeout
- workflow config missing
- template render failure
- context resolution failure
- checker failure due to missing target files
- malformed runner output

Required behavior:

- fail loudly with explicit error text
- always write available artifacts before exiting
- preserve stderr even when parsing fails
- never mark a run as success without checker pass when checker is configured

## Testing Strategy

### Unit Tests

- workflow config loading
- template rendering
- registry resolution
- checker result serialization
- artifact path generation
- retry policy handling

### Integration Tests

- `gemini_cli` runner smoke with stubbed subprocess
- assessment workflow prompt rendering
- role5 checker on known-good sample
- role5 checker on known-bad sample
- failed check triggering rework attempt generation

### Test Style Constraint

Follow the existing repository pattern where practical:

- `unittest` is acceptable and already common in local script tests
- tests may dynamically import script entrypoints via `importlib.util`
- avoid introducing a more elaborate test harness unless needed

### Manual Validation

- run the migrated assessment workflow against the existing chapter-02 sample
- compare generated local-check output with current script output
- verify run bundle completeness

## Risks

### Risk: over-generalizing configuration

If workflow YAML grows too expressive, it becomes a fragile DSL.

Mitigation:

- keep config shallow
- move logic to Python adapters

### Risk: runner abstractions leaking backend quirks

Different CLIs may return different output shapes.

Mitigation:

- normalize all runner outputs into one `RunnerResult`
- store raw stdout/stderr in artifacts regardless

### Risk: config format creates an undeclared dependency

If the engine requires YAML unconditionally, publishing and reuse become more fragile.

Mitigation:

- support JSON config by default
- treat YAML as optional convenience when `PyYAML` is present

### Risk: checker contracts becoming workflow-specific

Some workflows may need rich context.

Mitigation:

- permit workflow-specific `WorkflowContext`
- keep checker interface stable even if payload content differs

## Implementation Plan Boundary

This spec only covers architecture and migration shape.

The implementation plan should break work into these phases:

1. scaffold supervisor package and CLI
2. extract Gemini runner
3. extract assessment workflow context + templates
4. extract role5 checker
5. add retry/rework loop
6. add tests
7. deprecate old `assessment_supervisor.py`

## Recommendation

Proceed with a mixed architecture:

- workflow flow in YAML
- business logic in Python adapters
- runners as plugins
- checkers as plugins

This keeps the platform general enough to reuse while avoiding a brittle configuration DSL.
