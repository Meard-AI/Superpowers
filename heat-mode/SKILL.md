---
name: heat-mode
description: Anti-stall self-healing and error recovery. Use after 2 or more consecutive tool failures, or when stuck in a retry loop, to classify the failure and get a concrete recovery plan.
allowed-tools:
  - Bash
  - Read
metadata:
  version: 2.0.0
  author: Agent Superpowers Team
  category: reliability
---

# Heat Mode Playbook

**Heat Mode** is an emergency anti-stall recovery mechanism. After repeated tool
failures or a command loop, it classifies the failure type and returns the specific
constraints to relax in order to break out.

## Triggers & Scope
- Trigger after 2 or more consecutive tool or command failures.
- Trigger when encountering execution deadlocks or infinite retry loops.

## Workflow Instructions

### 1. Diagnose the stall

Pass both the error text and your own observed failure count:

```bash
python3 ./scripts/anti_stall.py --error-log "<error_trace>" --consecutive-failures 2 --json
```

`--consecutive-failures` is what **you** have observed. `--threshold` (default `2`) is
the count at which a stall is declared. The verdict uses the highest of three signals:
your reported count, the trailing error streak in the log, and the persisted counter.

### 2. Execute the remediation plan

If `"stall_detected": true`, work through `suggested_actions` in order. `failure_class`
tells you which family of fix applies: `json_format`, `permission_timeout`, `deadlock`,
`command_failure`, or `generic_error`.

Add `--recommend` to get recommendations even when below threshold.

### 3. Track failures across calls (optional)

```bash
python3 ./scripts/anti_stall.py --record-failure --json
```

Increments a persistent counter, so successive failures accumulate without you having
to track the count yourself.

### 4. Reset once execution succeeds

```bash
python3 ./scripts/anti_stall.py --reset --json
```

## Log Input Rules
`--log` / `--error-log` accepts either a file path or raw log text. A value that looks
like a path but does not exist is an **error**, not silently treated as log content.
Log text can also be piped on stdin.

## Escalation
| Level | Trigger | Action |
|---|---|---|
| 1 | Repeated JSON/schema parse errors | Switch to loose regex parsing, drop optional format checks |
| 2 | Permission timeouts or path errors | Verify cwd is inside workspace root, use non-interactive commands |
| 3 | Deadlocks or process hangs | Kill hanging background tasks, offload state to scratch |
| 4 | Persistent unrecoverable failure | Partial handoff with a structured state dump to the parent orchestrator |

## State Location
The persistent counter is stored in `$XDG_STATE_HOME/agent-superpowers/heat-mode.json`
(or `~/.local/state/agent-superpowers/`), never inside this skill folder. Override with
`AGENT_SUPERPOWERS_STATE` or `--state-file`.
