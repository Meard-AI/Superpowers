---
name: invisible-attacks
description: Path boundary validation and speculative background task execution. Use when validating that a file mutation stays inside an allowed root, or when queueing and running background pre-fetch tasks and checking for leaked processes.
allowed-tools:
  - Bash
  - Read
  - Write
metadata:
  version: 2.0.0
  author: Agent Superpowers Team
  category: security-and-speculation
---

# Invisible Attacks Skill Playbook

Validate path mutations against an allowed root, and run non-destructive speculative
background tasks (step N+1 pre-fetching, parallel builds) with real process tracking.

## Triggers & Scope
Activate invisible-attacks when:
1. About to write, modify, or delete a file and you need to confirm it is in bounds.
2. Executing multi-step pipelines where preparing step N+1 in the background reduces latency.
3. Checking whether previously spawned background tasks are still running.

## Path Boundary Validation

Validate a target path before any mutation:

```bash
python3 ./scripts/sandbox_enforcer.py --path "<target_file>" --allowed-root "<allowed_dir>" --action write --json
```

- **Exit `0` (`"allowed": true`)** — proceed with the mutation.
- **Exit `1` (`"allowed": false`)** — halt. Do not attempt to bypass or force the write.
  Request a scope update from the parent agent instead.

## Speculative Queue

Enqueue a background task:

```bash
python3 ./scripts/sandbox_enforcer.py --queue-speculative "npm run build" --allowed-root "<dir>" --json
```

Execute every queued task in the background:

```bash
python3 ./scripts/sandbox_enforcer.py --run-queue --json
```

Inspect queue state (statuses are reconciled against real process liveness):

```bash
python3 ./scripts/sandbox_enforcer.py --status --json
```

Clear the queue:

```bash
python3 ./scripts/sandbox_enforcer.py --clear-queue --json
```

## Process Leak Check

Report background tasks this tool spawned that are still alive:

```bash
python3 ./scripts/sandbox_enforcer.py --check-leak --json
```

Exits `1` when live processes remain (`"status": "LEAKS_DETECTED"`), `0` when clean.
Only processes spawned through `--run-queue` are tracked; anything started by other
means is not visible here.

## Scoped Command Execution

```bash
python3 ./scripts/sandbox_enforcer.py --run-cmd "<command>" --allowed-root "<dir>" --timeout 30 --json
```

## Enforcement Boundary
`--run-cmd` scopes the child's working directory and sets one environment variable.
**That is not isolation.** The child inherits the full environment, runs as the same
user, and can reach the entire filesystem. Path validation is likewise *advisory* — it
reports whether a mutation is in bounds; it cannot prevent one.

For a real boundary, use an OS sandbox: `sandbox-exec` (macOS), Landlock + seccomp or
bubblewrap (Linux), or a container.

## State Location
Queue state and task logs are written to `$XDG_STATE_HOME/agent-superpowers/` (or
`~/.local/state/agent-superpowers/`), never inside this skill folder. Override with
`AGENT_SUPERPOWERS_STATE`.
