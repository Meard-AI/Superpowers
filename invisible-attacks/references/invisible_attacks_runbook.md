# Invisible Attacks — Offline Runbook

Condensed operational steps. For the enforcement boundary and threat model see
[`invisible_attacks_guide.md`](./invisible_attacks_guide.md).

## Path validation loop
1. **Validate before mutating**:
   ```bash
   python3 ./scripts/sandbox_enforcer.py --path "<target>" --allowed-root "<dir>" --action write --json
   ```
2. **Branch on exit code**: `0` → proceed. `1` → halt, do not force the write, request
   a scope update from the parent agent.

## Speculative queue loop
| Step | Command |
|---|---|
| Enqueue | `--queue-speculative "<cmd>" --allowed-root "<dir>" --json` |
| Execute all | `--run-queue --json` |
| Inspect | `--status --json` |
| Clear | `--clear-queue --json` |

Queued tasks are `QUEUED` until `--run-queue` launches them, then `RUNNING`, then
`FINISHED` once the PID exits. `--status` reconciles against real process liveness.

## Leak check
```bash
python3 ./scripts/sandbox_enforcer.py --check-leak --json
```
Exit `1` when spawned processes are still alive, `0` when clean. Only tasks launched
via `--run-queue` are tracked.

## Scoped execution
```bash
python3 ./scripts/sandbox_enforcer.py --run-cmd "<cmd>" --allowed-root "<dir>" --timeout 30 --json
```
Sets cwd and one env var. **This is not isolation** — see the guide.

## Exit codes
| Code | Meaning |
|---|---|
| 0 | Allowed / succeeded / no leaks |
| 1 | Path denied, command failed, or leaks detected |
| 124 | `--run-cmd` timed out |

## State
`$AGENT_SUPERPOWERS_STATE`, else `$XDG_STATE_HOME/agent-superpowers/`, else
`~/.local/state/agent-superpowers/`. Queue at `speculative_queue.json`, task output
under `speculative_logs/`. Never inside the skill folder.

## Failure modes
- **Task stuck `RUNNING`** — run `--status` to reconcile, or `--check-leak` to see the PID.
- **`--run-cmd` fails with "not a directory"** — `--allowed-root` does not exist.
- **Queue looks stale** — `--clear-queue`; task IDs come from a persistent counter and
  are never reused.
