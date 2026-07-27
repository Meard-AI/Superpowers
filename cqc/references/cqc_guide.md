# CQC — Sandbox & Boundary Guide

## 1. Overview
CQC narrows the blast radius of a command by declaring a **perimeter directory**,
refusing commands that visibly reach outside it, and diffing the surrounding
filesystem afterwards to report collateral changes.

## 2. What CQC Is and Is Not

**CQC is a mistake detector.** It catches an agent that is about to `rm` the wrong
path, or a build script that scribbles into a sibling module.

**CQC is not a security boundary.** It cannot stop a determined or compromised
command. Two structural limits, both surfaced in every result rather than hidden:

| Limit | Consequence | Field that reports it |
|---|---|---|
| Static analysis reads a shell string | Runtime expansion defeats it | `static_analysis.undecidable` |
| Snapshot diffing covers only declared roots | Writes elsewhere are invisible | `watch_scope`, `watch_scope_note` |

If you need enforcement rather than detection, use an OS mechanism:

| Platform | Mechanism |
|---|---|
| macOS | `sandbox-exec` (Seatbelt) |
| Linux | Landlock + seccomp, or bubblewrap |
| Any | Container, microVM (Firecracker), or gVisor |

These operate at the kernel/syscall layer, where a boundary can actually hold.
Note that Claude Code and Codex CLI already run bash inside such a sandbox — CQC
layers *intent checking* on top of that, it does not replace it.

---

## 3. Core Concepts

### 3.1 Perimeter directory (`--perimeter-dir`, alias `--target-dir`)
The directory the command runs in and is allowed to modify. Defaults to CWD.

### 3.2 Containment is component-wise
A path is inside the perimeter when it *is* the perimeter or lives beneath it,
compared component-by-component via `Path.relative_to`.

A prefix string comparison is wrong and was a real bug in v1:

```
perimeter  /x/app
candidate  /x/app-secrets/creds.txt
startswith → True   ← WRONG, sibling directory treated as inside
relative_to → ValueError → False   ← correct
```

### 3.3 Two validation layers
1. **Static analysis** — tokenizes the command with `shlex` (so *quoted* paths are
   seen, which a whitespace regex misses), resolves each path-like token against the
   perimeter, and flags any that escape. System prefixes (`/bin`, `/usr`, `/opt`,
   `/dev`, `/proc`, `/sys`) are ignored as normal.
2. **Filesystem snapshot** — records mtimes under `watch_scope` but outside the
   perimeter, before and after execution, and diffs them.

### 3.4 Undecidability
When the command contains a construct that expands at runtime, static analysis is
reported as `undecidable` instead of clean:

| Construct | Why it defeats analysis |
|---|---|
| `$VAR`, `${VAR}` | Value unknown until the shell expands it |
| `$(...)`, backticks | Output becomes the path |
| `~` | Expands to `$HOME`, outside any project perimeter |
| `eval`, `exec`, `xargs` | Command is constructed at runtime |
| `base64` | Payload is obscured |

`UNDECIDABLE` is an honest verdict. Reporting "no violations" for `cat ~/.ssh/config`
would be a lie.

---

## 4. Snapshot Diffing Caveats
- **mtime-based** — a content change preserving mtime is invisible.
- **Racy** — a concurrent process writing inside `watch_scope` produces a false positive.
- **Cost** — the watch roots are walked twice per run. `.git`, `node_modules`,
  `__pycache__`, `.venv`, and similar are pruned in place, but a large watch root is
  still expensive. Scope `--watch-dir` deliberately.

---

## 5. CLI Reference

### 5.1 `boundary_validator.py`
| Flag | Purpose |
|---|---|
| `--check-path PATH` | Is this path inside `--allowed-paths`? Exit 0/1 |
| `--allowed-paths A,B` | Comma-separated allowed roots (default CWD) |
| `--check-command CMD` | Static analysis of a command string |
| `--perimeter-dir DIR` | Perimeter for `--check-command` |
| `--json` | Machine-readable output |

### 5.2 `cqc_executor.py`
| Flag | Purpose |
|---|---|
| `--command CMD` (`--cmd`) | Command to run |
| `--perimeter-dir DIR` (`--target-dir`) | Perimeter, default CWD |
| `--watch-dir PATH` | Extra monitored root, repeatable |
| `--warn-only` | Run despite a static violation |
| `--dry-run` | Analyze only |
| `--timeout N` | Seconds, default 300 |
| `--json` | Machine-readable output |

---

## 6. Worked Example

```bash
python3 scripts/cqc_executor.py \
  --perimeter-dir "src/parser" \
  --command "python3 -m pytest tests/unit" \
  --watch-dir "src" \
  --json
```

Runs the tests with `src/parser` as the perimeter, monitoring all of `src` for
side-effects. Exit `2` means either the command was refused or something outside
`src/parser` changed.
