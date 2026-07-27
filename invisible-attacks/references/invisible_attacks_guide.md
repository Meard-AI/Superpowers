# Invisible Attacks — Boundary & Speculation Guide

## 1. Overview
Two capabilities in one skill:

1. **Path boundary validation** — answer "is this write in bounds?" before performing it.
2. **Speculative background execution** — run step N+1 work early, with real process
   tracking so nothing is left orphaned.

---

## 2. Enforcement Boundary — read this first

### 2.1 Path validation is advisory
The validator tells the **caller** whether a mutation is in bounds. It does not
intercept filesystem calls and cannot prevent a write it was never asked about. It is
useful exactly to the degree the agent consults it before acting.

### 2.2 `--run-cmd` is not isolation
It sets the child's working directory and one environment variable
(`SANDBOX_SCOPED=1`). The child:

- inherits the **entire** parent environment, including every secret in it
- runs as the **same user** with the same privileges
- can reach the **whole filesystem**

The flag is named `--run-cmd` for this reason; `--isolate-cmd` remains as an alias but
the output includes an explicit `"isolation": "none — cwd and one env var only"` field.

### 2.3 What to use instead
| Platform | Mechanism |
|---|---|
| macOS | `sandbox-exec` (Seatbelt) |
| Linux | Landlock (filesystem paths) + seccomp (syscalls), or bubblewrap |
| Any | Container, gVisor, or a Firecracker microVM |

Landlock needs Linux 5.13+ for filesystem rules. Claude Code and Codex CLI already
apply these to their bash tools; this skill layers intent-checking above that, it does
not substitute for it.

---

## 3. Containment Logic

A path is inside the allowed root when `Path.relative_to` succeeds after both are
resolved. Resolution follows symlinks, so a symlink inside the root pointing outside it
resolves outside and is correctly denied.

Prefix string comparison would be wrong: `/x/app-secrets` starts with `/x/app` but is a
different directory.

### 3.1 `--action`
`read`, `write`, or `delete`. Currently recorded in the result for audit purposes;
containment is evaluated identically for all three.

---

## 4. Speculative Queue

### 4.1 Lifecycle
```
QUEUED ──(--run-queue)──> RUNNING ──(process exits)──> FINISHED
                             └──(spawn fails)────────> FAILED
```

A queue nothing executes is just a list. `--run-queue` launches each `QUEUED` task with
`subprocess.Popen`, records the real PID, and redirects combined output to
`speculative_logs/<task_id>.log`.

### 4.2 Task IDs
Allocated from a persistent `next_id` counter, not from queue length. Length-derived
IDs collide as soon as anything is removed.

### 4.3 Status reconciliation
`--status` and `--check-leak` probe each recorded PID with signal `0` — liveness
without delivering a signal — and demote `RUNNING` to `FINISHED` for dead PIDs.

### 4.4 Leak detection scope
`--check-leak` reports processes **this tool spawned** and that are still alive. It does
not enumerate system processes. The `scope_note` field says so on every call.

This is a deliberately narrow, honest check. The previous implementation returned a
hardcoded `{"status": "SECURE", "leaks_detected": false}` with no inspection whatsoever
— a check that can never fail is worse than no check, because it manufactures
confidence.

---

## 5. State Location

| Item | Path |
|---|---|
| Queue | `<state>/speculative_queue.json` |
| Task logs | `<state>/speculative_logs/<task_id>.log` |

`<state>` resolves to `$AGENT_SUPERPOWERS_STATE`, else
`$XDG_STATE_HOME/agent-superpowers`, else `~/.local/state/agent-superpowers`.

State is kept **outside the skill folder** deliberately: the folder is copied between
machines and workspaces as a read-only package. Writing runtime state into it pollutes
the distributed artifact and shares one queue across every workspace using that copy.
A legacy bare-list queue file is migrated automatically on load.

---

## 6. CLI Reference

| Flag | Purpose |
|---|---|
| `--path PATH` | Validate a path against `--allowed-root`; exit 0/1 |
| `--allowed-root DIR` (`--target-dir`) | Boundary root, default CWD |
| `--action read\|write\|delete` | Recorded action type |
| `--queue-speculative CMD` | Enqueue a background task |
| `--run-queue` | Launch all `QUEUED` tasks |
| `--status` | Show the queue, reconciled against liveness |
| `--clear-queue` | Empty the queue |
| `--check-leak` | Report still-running spawned tasks; exit 1 if any |
| `--run-cmd CMD` (`--isolate-cmd`) | Run with cwd scoped to the allowed root |
| `--timeout N` | Timeout for `--run-cmd`, default 30s |
| `--json` / `--dry-run` | Output format / no side-effects |

---

## 7. Worked Example

```bash
export ROOT="$PWD"

# 1. Gate a write
python3 scripts/sandbox_enforcer.py --path "$ROOT/src/out.txt" --allowed-root "$ROOT" --json

# 2. Warm the build while reasoning continues
python3 scripts/sandbox_enforcer.py --queue-speculative "npm run build" --allowed-root "$ROOT" --json
python3 scripts/sandbox_enforcer.py --run-queue --json

# 3. Before finishing, confirm nothing was left running
python3 scripts/sandbox_enforcer.py --check-leak --json
```

Step 3 belongs in any teardown path. Exit `1` means a background task outlived the
session and needs handling.
