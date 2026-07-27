# Heat Mode — Anti-Stall Reference Guide

## 1. Executive Summary
Heat Mode prevents an agent from burning a context window on a loop it cannot escape.
When execution stalls — repeated tool errors, JSON formatting deadlocks, permission
timeouts — it classifies the failure and names the specific constraints to relax.

The insight it encodes: an agent stuck in a retry loop is usually failing *because of*
a constraint it is trying to satisfy (strict output schema, an interactive command, a
tool it keeps re-calling identically). Recovery means dropping the constraint, not
retrying harder.

---

## 2. Stall Detection Mechanics

### 2.1 Three independent signals
The failure count is `max()` of:

| Signal | Source | When it matters |
|---|---|---|
| `caller_reported` | `--consecutive-failures N` | The agent knows its own retry count — the most reliable signal |
| `log_streak` | Trailing consecutive error lines in the log | No count available, only output |
| `persisted` | Counter incremented by `--record-failure` | Failures span multiple tool calls |

All three appear in the `signals` object of every result, so a surprising verdict is
always explainable.

### 2.2 Why "trailing" consecutive
The log scan counts errors backwards from the **end** and stops at the first
non-error line. A run of errors followed by a success is not a stall — the agent
recovered. `total_error_lines` is reported separately and never silently substituted
for the streak.

### 2.3 Threshold configuration
| Profile | Threshold | Use for |
|---|---|---|
| Aggressive | 2 (**default**) | High-risk or time-sensitive tasks |
| Standard | 3 | Ordinary work |
| Relaxed | 5 | Complex exploratory or multi-stage tasks |

The default is 2 because the skill's contract is "trigger after 2 consecutive failures."

---

## 3. Failure Classification

Each error line in the streak is classified by the first matching pattern:

| Class | Matches | Recovery strategy |
|---|---|---|
| `json_format` | json, parse, schema, decode, syntax | Relax schema strictness; regex-extract instead of `json.loads` |
| `permission_timeout` | permission, timeout, prompt, denied | Verify cwd; drop interactive commands |
| `deadlock` | deadlock, hang, block, stuck | Kill background tasks; flush state to scratch |
| `command_failure` | command, exit code, process, not found | Decompose into atomic sub-commands |
| `generic_error` | anything else matching the error pattern | Broad constraint relaxation |

The acted-on class is the **most frequent in the streak, with the most recent
breaking ties**. v1 checked `json_format` first unconditionally, so one stale JSON
error dominated every later recommendation.

---

## 4. CLI Reference

| Flag | Purpose |
|---|---|
| `--log TEXT_OR_PATH` (`--error-log`) | Log file or raw text; also reads stdin |
| `--consecutive-failures N` | Failures the caller has observed |
| `--threshold N` | Stall declaration threshold (default 2) |
| `--record-failure` | Increment the persistent counter, then analyze |
| `--reset` | Zero the persistent counter |
| `--recommend` | Emit recommendations even below threshold |
| `--state-file PATH` | Override state location |
| `--json` | Machine-readable output |
| `--dry-run` | Analyze without writing state |

### 4.1 Log input resolution
| Input | Treated as |
|---|---|
| Existing file path | File contents |
| Contains `/` or ends `.log`/`.txt`/`.json`/`.out` but missing | **Error** (exit 1) |
| Anything else | Raw log text |
| stdin (when `--log` omitted) | Raw log text |

A missing path is an error rather than being reinterpreted as log body — otherwise a
typo'd path silently becomes "log content" and produces a phantom verdict.

---

## 5. Output Schema

```json
{
  "status": "SUCCESS",
  "stall_detected": true,
  "consecutive_failures": 3,
  "threshold": 2,
  "signals": { "log_streak": 3, "caller_reported": 0, "persisted": 0 },
  "total_error_lines": 3,
  "analyzed_lines": 5,
  "failure_class": "json_format",
  "recovery_strategy": "Relax JSON strictness and drop non-essential format constraints.",
  "suggested_actions": ["..."],
  "state_file": "/home/user/.local/state/agent-superpowers/heat-mode.json",
  "dry_run": false
}
```

---

## 6. State Location
Persistent state lives at `$AGENT_SUPERPOWERS_STATE`, else
`$XDG_STATE_HOME/agent-superpowers/heat-mode.json`, else
`~/.local/state/agent-superpowers/heat-mode.json`.

Never inside the skill folder: the folder is copied between machines and workspaces as
a read-only package, and runtime counters shared across every workspace using that copy
would be wrong.

---

## 7. Escalation Runbook

| Level | Trigger | Action |
|---|---|---|
| 1 | Repeated JSON/schema parse errors | Loose regex parsing, drop optional format checks, write raw output to scratch |
| 2 | Permission timeouts or path errors | Verify cwd inside workspace root, switch to non-interactive atomic scripts |
| 3 | Deadlocked tasks or hangs | Terminate background tasks, reset execution memory, offload progress |
| 4 | Persistent unrecoverable failure | Partial handoff with a structured state dump to the parent orchestrator |

---

## 8. Integration Pattern
Call `anti_stall.py` whenever a tool call fails. If `stall_detected` is `true`, execute
the first item in `suggested_actions` before retrying anything. Call `--reset` on the
first success so the next stall is measured from a clean baseline.
