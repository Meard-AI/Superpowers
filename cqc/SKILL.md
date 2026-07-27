---
name: cqc
description: Close-Quarters Combat perimeter checking for file modifications. Use before running commands that modify a sensitive sub-module, to statically check a command for perimeter escape and detect out-of-perimeter side-effects afterwards.
allowed-tools:
  - Bash
  - Read
  - Edit
metadata:
  version: 2.0.0
  author: Agent Superpowers Team
  category: safety
---

# Close-Quarters Combat (CQC) Playbook

**CQC** narrows the working perimeter when modifying sensitive codebases, catching
commands that reach outside a declared directory and reporting collateral changes.

## Triggers & Scope
- Trigger before performing code modifications in a target sub-path or high-risk repository.
- Trigger when you want to confirm a command touched nothing outside its perimeter.

## Workflow Instructions

### 1. Validate a target path

```bash
python3 ./scripts/boundary_validator.py --allowed-paths "src/,lib/" --check-path "<target_file_path>" --json
```

Exits `0` when allowed, `1` when blocked.

### 2. Statically analyze a command before running it

```bash
python3 ./scripts/boundary_validator.py --check-command "<command_string>" --perimeter-dir "<dir>" --json
```

Three outcomes: `ALLOWED`, `BLOCKED` (a referenced path escapes), or `UNDECIDABLE`
(the command contains runtime expansion, so static analysis cannot be trusted).

### 3. Execute inside the perimeter

```bash
python3 ./scripts/cqc_executor.py --perimeter-dir "<allowed_subpath>" --command "<command_string>" --json
```

Execution is **refused** when static analysis finds an escape. Pass `--warn-only` to
override, `--dry-run` to analyze without running, and `--watch-dir <path>` (repeatable)
to monitor additional roots for side-effects.

Exit codes: `0` clean · `2` blocked or boundary violated · otherwise the command's own exit code.

## Enforcement Boundary
CQC is a **mistake detector, not a security sandbox**. Two limits, both reported in
the output rather than hidden:

- Static analysis reads a shell command as a string. Variable expansion, command
  substitution, `eval`, or any interpreter defeats it — hence the `UNDECIDABLE` verdict.
- The filesystem diff only covers `watch_scope` (default: the perimeter's parent).
  Writes outside those roots are not monitored; `watch_scope_note` says so on every run.

To actually *prevent* an escape, use an OS sandbox: `sandbox-exec` (macOS),
Landlock + seccomp or bubblewrap (Linux), or a container.

## Error Handling
On `blocked` or `violated`:
1. Do not re-run with `--warn-only` to force it through.
2. Report the specific `boundary_violations` entries to the parent agent.
