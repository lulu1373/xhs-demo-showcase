# OpenClaw ECC Sidecar Design

**Goal:** Add an ECC-style continuous learning sidecar to the existing local OpenClaw + Feishu bot on this Mac so the bot can automatically collect conversation observations, extract reusable knowledge, isolate personal style, and continuously evolve new skills.

**Recommended Approach:** Keep the existing OpenClaw gateway untouched and add a separate local ECC sidecar process that observes Feishu bot conversations, redacts sensitive content before persistence, generates instincts with a model-assisted classifier, and automatically evolves and promotes knowledge skills globally while keeping style skills user-scoped.

## Scope

This design covers:

- Running the first ECC node on the user's existing local OpenClaw + Feishu deployment
- Collecting all employee-to-bot Feishu private-chat and group-chat conversations handled by this bot
- Redacting sensitive content before observations are persisted or sent to external model APIs
- Storing observations, instincts, evolved skills, state, logs, and rollback metadata on local disk
- Automatically extracting instinct candidates from repeated conversation patterns
- Automatically evolving and promoting shared knowledge skills to the global skill layer
- Automatically evolving and promoting personal style preferences to per-user skill layers
- Activating newly promoted skills without manual review in the first version
- Preserving a quarantine trail and rollback path for bad promotions

This design does not cover:

- Collecting terminal/editor behavior from employee laptops
- Multi-node sync between several personal bot installations
- A centralized database or hosted control plane
- Manual approval workflows before promotion
- Rewriting or forking OpenClaw core runtime internals

## Product Intent

The first version is a single-node validation system with a full automatic learning loop:

1. Conversations with the bot become redacted observations
2. Repeated patterns become instinct candidates
3. Stable candidates evolve into skills
4. Shared knowledge is promoted globally and affects all users immediately
5. Personal style is promoted only into the matching user profile

The design optimizes for fast local deployment, clear traceability, and safe separation between team knowledge and personal style.

## Architecture

### Components

- **OpenClaw Gateway**
  - Continues to receive Feishu messages, run the assistant, and send replies
  - Remains the only message-serving runtime in the first version

- **ECC Sidecar**
  - Runs as a separate local process next to OpenClaw
  - Reads conversation events from the existing bot path
  - Performs redaction, observation persistence, instinct extraction, evolve, promote, quarantine, and rollback bookkeeping

- **Observation Store**
  - Local JSONL and structured file storage under a dedicated ECC root directory
  - Keeps raw ingest artifacts, redacted observations, derived metadata, and processing checkpoints

- **Skill Layers**
  - `global/` for shared knowledge
  - `users/<feishu_user_id>/` for personal style and preference skills

- **Scheduler**
  - Periodically runs extraction, classification, evolve, promotion, cleanup, and health checks

### Integration Contract With OpenClaw

The first version uses two explicit integration points and does not require patching OpenClaw core source:

- **Observation ingest**
  - ECC sidecar tails the local OpenClaw session store under `~/.openclaw/agents/*/sessions/*.jsonl`
  - The sidecar extracts completed user/assistant turns from these session files and turns them into ECC observations
  - This keeps message serving in OpenClaw while giving ECC a durable, replayable local source of truth

- **Skill activation**
  - ECC installs a custom hook pack on the OpenClaw `agent:bootstrap` event
  - The hook reads the current sender/user identity from bootstrap context when available
  - The hook injects up to two generated context files for the current turn:
    - the current global active bundle
    - the current user-specific active bundle, if a user identity is available and a bundle exists
  - The hook loads generated files from the OpenClaw workspace so activation stays inside supported workspace/bootstrap mechanics

Activation fallback behavior:

- If the bootstrap context does not expose a usable user identity for the current turn, only the global active bundle is injected
- Missing user identity must never block the turn or cause the wrong user's style bundle to load

This contract keeps OpenClaw as the only message-serving runtime while giving the ECC sidecar one read path for learning and one supported bootstrap path for turn-time activation.

### Message Flow

1. A user sends the bot a Feishu private or group message
2. OpenClaw processes the turn and sends the reply normally
3. ECC sidecar receives a copy of the turn record
4. The sidecar extracts the minimum required fields
5. Sensitive content is redacted before persistence
6. The redacted observation is appended to the observation store
7. The scheduler batches observations and sends redacted snippets to an external model for pattern extraction
8. The sidecar scores and classifies extracted instincts as `knowledge` or `style`
9. Qualified instincts evolve into skills
10. Global knowledge skills are promoted to the shared layer and activated for all users
11. Personal style skills are promoted only to the matching user layer
12. Every evolve/promote action is recorded with evidence and rollback metadata

## Data Model

### Observation

Each observation should capture only the minimum necessary learning context:

- Timestamp
- Conversation ID
- Feishu chat type: `p2p` or `group`
- User ID
- Bot account ID
- Redacted user message
- Redacted assistant reply
- Derived metadata such as turn length, follow-up count, correction indicators, and topic hash

For the first version, these fields are extracted from the inbound user message transcript generated by OpenClaw's channel adapter. In Feishu sessions this transcript currently includes a `Conversation info` JSON block with fields such as:

- `sender_id`
- `conversation_label`
- `is_group_chat`
- `message_id`

Identity contract:

- `user_id` is sourced from `sender_id`
- `chat_type` is `group` when `is_group_chat=true`, otherwise `p2p`
- `conversation_id` is sourced from `conversation_label` when present, otherwise the OpenClaw session file ID

Fallback behavior:

- If `sender_id` cannot be extracted, the sidecar still stores the observation but marks it `scope_capability=user_unknown`
- Observations with `user_unknown` are eligible for global knowledge extraction only
- User-style learning and user-specific promotion are disabled for those observations
- `user_unknown` observations may increase global evidence count, but must not increase the `distinct user count >= 3` promotion threshold

For the first version, `bot_account_id` is sourced from the configured OpenClaw Feishu account name, which is expected to be `default` on this Mac unless the channel config changes later.

Raw unredacted payloads should never be sent to the model analysis stage. `observations/raw/` is an optional short-retention local debugging path and should be disabled by default in the first production-like setup on this Mac.

Example redacted observation record:

```json
{
  "timestamp": "2026-03-24T07:30:12.376Z",
  "conversation_id": "oc_1ee49f6ce4543439816fefcc05764e47",
  "chat_type": "group",
  "user_id": "ou_e2c9bb2323a8338ce50432052a108b55",
  "message_id": "om_x100b531796f51880b291562b27ed148",
  "user_text": "[PERSON]: 你能看到我们群里的聊天记录吗？",
  "assistant_text": "我只能看到当前会话里发给我的内容，不能主动翻整个群历史。",
  "scope_capability": "full",
  "derived": {
    "follow_up_count": 0,
    "correction_signal": false,
    "topic_hash": "chat-history-visibility"
  }
}
```

### Instinct

An instinct is an atomic learned behavior with:

- Stable ID
- Type: `knowledge` or `style`
- Trigger summary
- Action summary
- Confidence score
- Evidence count
- Distinct user count
- Source conversation references
- Scope: `global` or `user`

### Skill

A skill is an evolved artifact built from related instincts with:

- Skill ID and title
- Scope and owner
- Source instinct IDs
- Promotion timestamp
- Current status: `evolved`, `active`, or `rolled_back`
- Bundle membership metadata

Persisted skill artifacts are individual evolved units. Activation does not load individual skill files directly; instead, the sidecar compiles all active skills for a scope into one scope bundle file.

### Active Bundle

An active bundle is the atomic activation and rollback unit.

There is exactly one active bundle per scope:

- `active/global/MEMORY.md`
- `active/users/<feishu_user_id>/MEMORY.md`

Each bundle is rebuilt from the current set of active evolved skills for that scope and then atomically swapped into place.

This means:

- evolve stores per-skill artifacts
- activate compiles per-scope bundles
- rollback restores the previous bundle snapshot for the affected scope

Example active bundle artifact:

```markdown
# ECC Active Bundle - Global

## Shared Knowledge
- When users ask whether the bot can see full Feishu group history, explain that it only sees content delivered into the current conversation context.
- When users share Feishu wiki links, first distinguish wiki vs docx links before describing available actions.

## Reusable Workflow Hints
- Prefer direct next-step instructions when a permission or tool refresh problem is blocking execution.
```

## Shared Knowledge Vs Personal Style

### Global Knowledge

Promote globally when the learned behavior reflects reusable team knowledge, such as:

- Repeated concept explanations
- Common onboarding confusions
- Frequently recurring troubleshooting advice
- Reliable workflow shortcuts
- Team-wide terminology mappings

Global knowledge must be validated across multiple users or sessions before promotion.

### User Style

Keep user-scoped when the learned behavior reflects personal preference, such as:

- Response brevity vs detail preference
- Preferred format such as bullets, prose, or tables
- Tone and phrasing habits
- Whether the user prefers the answer first or explanation first

When classification is ambiguous, default to user scope rather than global scope.

## Automatic Learning Rules

### Stage 1: Observation

Every bot turn is stored as a redacted observation. No direct skill generation happens at this stage.

### Stage 2: Instinct Candidate Generation

Create instinct candidates only after repeated signals appear.

Initial thresholds:

- Same pattern observed at least `3` times before a candidate is created
- Signals may come from repeated explanations, repeated corrections, or repeated stable user preferences

### Stage 3: Evolve

Evolve instinct candidates into skills only if they pass both repetition and effectiveness checks.

Initial evolve threshold:

- Confidence score `>= 0.72`

Effectiveness signals in the first version:

- Fewer immediate clarifying follow-ups after a similar response
- No direct user correction after the response
- Reuse of the same explanation pattern across multiple similar turns
- Consistent topic clustering over time

These signals are product requirements, not fixed scoring formulas. The exact scoring implementation may evolve as long as it preserves the thresholds and scope rules defined in this spec.

### Stage 4: Promote

Promote by scope:

- **User scope**
  - Same user preference pattern appears at least `4` times
  - Promote into `users/<feishu_user_id>/`

- **Global scope**
  - Classified as knowledge
  - Distinct user count `>= 3`
  - Total evidence count `>= 6`
  - Confidence score `>= 0.82`
  - Promote into `global/`

Promoted global skills are activated immediately for all users in this first version.

## Skill Lifecycle

Each generated skill follows this lifecycle:

`candidate -> evolved -> quarantined_snapshot -> active -> rolled_back`

Definitions:

- **candidate**
  - Derived instinct clusters that have not yet become a skill bundle

- **evolved**
  - A skill bundle has been generated from candidate instincts

- **quarantined_snapshot**
  - The generated bundle is written to `evolved/quarantine/` with evidence, version info, and rollback metadata
  - This is an audit and rollback checkpoint, not a manual-review gate
  - In the automatic first version, this state may exist only briefly inside the same scheduler run before activation

- **active**
  - The bundle has been copied into the active `global/` or `users/<feishu_user_id>/` layer and is eligible for bootstrap injection

- **rolled_back**
  - The bundle has been removed from active use and recorded in rollback history

## Redaction And Privacy

Redaction must happen before observation persistence and before model analysis.

The first version should replace these patterns with typed placeholders:

- Personal names -> `[PERSON]`
- Email addresses -> `[EMAIL]`
- Phone numbers -> `[PHONE]`
- Government ID-like patterns -> `[ID]`
- API keys, tokens, secrets -> `[TOKEN]`
- Feishu document or file identifiers -> `[DOC_ID]`
- Department, group, or org identity markers -> `[ORG]`
- Secret-looking strings inside code blocks -> `[TOKEN]`

Redaction should preserve enough semantic structure for downstream learning while removing the original values.

## Storage Layout

The ECC sidecar root should live under:

`~/.openclaw-ecc/`

Initial layout:

- `observations/raw/`
- `observations/redacted/`
- `instincts/candidates/`
- `instincts/global/`
- `instincts/users/<feishu_user_id>/`
- `evolved/quarantine/`
- `evolved/global/skills/`
- `evolved/users/<feishu_user_id>/skills/`
- `active/global/MEMORY.md`
- `active/users/<feishu_user_id>/MEMORY.md`
- `state/`
- `logs/`
- `archive/`
- `rollback/`

This structure must make every promotion traceable back to its evidence.

Lightweight retention policy for the first version:

- `observations/raw/`: disabled by default; if enabled for debugging, keep at most 24 hours
- `logs/`: keep 14 days
- `archive/`: keep 30 days before manual or scheduled cleanup

## Activation Strategy

The first version should load skills in this order:

1. `active/global/MEMORY.md`
2. `active/users/<feishu_user_id>/MEMORY.md` for the current Feishu user, if available

The injected unit is the compiled scope bundle, not individual evolved skill files.

The bootstrap hook should resolve the current Feishu user from turn metadata. If no valid user ID is available, it should inject only the global bundle.

If activation fails, OpenClaw must still answer normally without the ECC layer rather than blocking the user-visible bot.

## Failure Handling

The sidecar must be non-blocking for message serving.

If the sidecar fails:

- OpenClaw continues serving messages
- Observation backlog remains on disk
- Scheduled jobs retry later
- Failed promote/evolve actions are logged with reason and retry metadata

If a promoted skill causes regressions:

- Mark the skill as rolled back
- Remove it from the active layer
- Preserve evidence for later diagnosis

## Rollback And Quarantine

Even in a fully automatic deployment, every evolved skill should first be written as a quarantined snapshot with trace metadata and version info before it is activated.

Required safeguards:

- **Quarantine trail**
  - Every new evolved skill is recorded in `evolved/quarantine/` with evidence, confidence, scope, source user/session counts, and the exact active target it will replace

- **Rollback record**
  - Every promotion writes a reversible change record so the latest global or user skill package can be reverted

These safeguards support automatic systems without requiring manual approval gates. Quarantine is therefore a real persisted checkpoint, but not a human approval state.

## Operational Boundaries

First-version deployment assumptions:

- Runs only on this Mac
- Reuses the existing local OpenClaw + Feishu installation
- Uses local LaunchAgent processes for both OpenClaw and the ECC sidecar
- Uses external model APIs only on redacted content
- Does not sync with coworker nodes yet
- Does not ingest local terminal/editor behavior yet

## Testing Strategy

### Functional

- Verify a Feishu conversation is captured as a redacted observation
- Verify redaction removes sensitive patterns before persistence
- Verify repeated similar observations generate instinct candidates
- Verify style-only patterns stay under the correct user profile
- Verify knowledge patterns meeting the threshold are promoted globally
- Verify newly promoted skills affect subsequent conversations

### Safety

- Verify raw secrets are never passed to external model analysis
- Verify ambiguous classifications default to user scope
- Verify sidecar failure does not break the bot reply path
- Verify rollback disables a bad skill cleanly

### Operational

- Verify LaunchAgent restarts the sidecar after exit
- Verify state checkpoints prevent duplicate reprocessing
- Verify log and archive rotation keep disk usage bounded

## Success Criteria

- The existing OpenClaw + Feishu bot remains operational on this Mac
- All handled Feishu private and group bot conversations become redacted observations
- The sidecar automatically extracts instinct candidates from repeated patterns
- Style learning is isolated per Feishu user
- Shared knowledge is promoted globally and becomes active for all users immediately
- Every evolve/promote action is traceable and reversible
- The system continues serving users even if ECC learning jobs fail temporarily
