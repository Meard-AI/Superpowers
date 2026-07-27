# Heat Mode — Offline Runbook

Condensed operational steps. For detection mechanics see
[`heat_mode_guide.md`](./heat_mode_guide.md).

## Standard loop
1. **Diagnose** — pass the error text *and* your own observed failure count:
   ```bash
   python3 ./scripts/anti_stall.py --error-log "<error_trace>" --consecutive-failures 2 --json
   ```
2. **Branch** on `stall_detected`:
   - `true` → work through `suggested_actions` in order.
   - `false` → keep going normally, or add `--recommend` to get advice anyway.
3. **Reset** once execution recovers:
   ```bash
   python3 ./scripts/anti_stall.py --reset --json
   ```

## Accumulating failures across calls
Instead of tracking the count yourself:
```bash
python3 ./scripts/anti_stall.py --record-failure --json
```
Each call increments the persistent counter. `--reset` clears it.

## Flag semantics (do not confuse these)
| Flag | Meaning |
|---|---|
| `--consecutive-failures N` | Failures **you have already observed** |
| `--threshold N` | Count at which a stall is **declared** (default 2) |

The verdict uses `max(caller_reported, log_streak, persisted)` — visible in the
`signals` object of every result.

## Failure classes
| `failure_class` | Recovery theme |
|---|---|
| `json_format` | Relax schema strictness, parse loosely |
| `permission_timeout` | Check cwd, drop interactive commands |
| `deadlock` | Kill hung tasks, offload state |
| `command_failure` | Decompose into atomic steps |
| `generic_error` | Broad constraint relaxation |

## Exit codes
| Code | Meaning |
|---|---|
| 0 | Analysis completed (stall detected or not) |
| 1 | Bad input — missing log path, or state could not be written |

## Failure modes
- **"Log path does not exist"** — `--log` looked like a path but was not found. Pass raw
  text without path separators to analyze inline.
- **`stall_detected: false` when you expected true** — check `signals`. If
  `caller_reported` is 0 you forgot `--consecutive-failures`.
- **Counter never resets** — state lives in `$XDG_STATE_HOME/agent-superpowers/`. Check
  `state_file` in the output.
