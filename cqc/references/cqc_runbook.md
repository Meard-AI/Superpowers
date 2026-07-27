# CQC — Offline Runbook

Condensed operational steps. For scope limits and threat model see
[`cqc_guide.md`](./cqc_guide.md).

## Standard loop
1. **Validate the target path** before any modification:
   ```bash
   python3 ./scripts/boundary_validator.py --allowed-paths "<allowed_dirs>" --check-path "<target_path>" --json
   ```
2. **Statically analyze the command** you intend to run:
   ```bash
   python3 ./scripts/boundary_validator.py --check-command "<cmd>" --perimeter-dir "<dir>" --json
   ```
3. **Execute inside the perimeter**:
   ```bash
   python3 ./scripts/cqc_executor.py --perimeter-dir "<dir>" --command "<cmd>" --json
   ```
4. **Read `boundary_violations`** in the result. Empty means nothing changed inside
   `watch_scope`; it does **not** mean nothing changed anywhere.

## Flags that matter
| Flag | Effect |
|---|---|
| `--dry-run` | Static analysis only; never runs the command |
| `--warn-only` | Run despite a static violation (default is refuse) |
| `--watch-dir PATH` | Add a monitored root; repeatable. Default: perimeter's parent |
| `--timeout N` | Command timeout, seconds (default 300) |

## Exit codes
| Code | Meaning |
|---|---|
| 0 | Clean — ran, exited 0, no violations detected |
| 2 | `blocked` (refused before running) or `violated` (side-effects found) |
| other | The command's own exit code |

## Status values
| Status | Meaning |
|---|---|
| `passed` | Ran cleanly, no violations in scope |
| `blocked` | Refused: static analysis found a perimeter escape |
| `violated` | Ran, but files outside the perimeter changed |
| `failed` | Command failed, timed out, or the perimeter was invalid |

## Failure modes
- **`UNDECIDABLE` verdict** — the command contains `$VAR`, `$(...)`, backticks, `~`,
  `eval`, or `xargs`. Static analysis cannot be trusted. Rewrite with literal paths, or
  accept the risk deliberately.
- **`blocked` on a legitimate command** — the path genuinely leaves the perimeter.
  Widen `--perimeter-dir` rather than reaching for `--warn-only`.
- **Violations reported that you did not cause** — another process wrote inside
  `watch_scope` during the run. Snapshot diffing cannot attribute changes to a PID.
