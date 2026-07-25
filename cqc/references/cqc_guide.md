# Close Quarters Combat (CQC) Sandbox & Boundary Guide

## 1. Overview
The CQC Skill provides micro-scope execution sandbox validation for agent tool invocations. It ensures that commands executed by AI agents operate strictly within a pre-defined perimeter directory, preventing side-effects, unauthorized file modifications outside the perimeter, or unintentional system modifications.

---

## 2. Core Concepts

### 2.1 Perimeter Directory (`--perimeter-dir`)
The absolute or relative directory within which all file modifications, creations, and deletions are allowed. Any change outside this directory is flagged as a `boundary_violation`.

### 2.2 Micro-Verification Containment
Before executing any action, CQC runs two layers of validation:
1. **Static Analysis**: Inspects the command string for references to paths outside `--perimeter-dir` or parent directory escape attempts (`../`).
2. **Dynamic Filesystem Snapshot**: Captures a file modification timestamp map of surrounding directory trees before and after command execution to detect out-of-perimeter delta.

---

## 3. CLI Helper Usage

### 3.1 CLI Arguments
- `--command "<cmd>"`: Shell command string to execute (Required).
- `--perimeter-dir <dir>`: Target sandbox directory path (Default: Current Working Directory).
- `--dry-run`: Flag to perform static boundary validation without running the command.

### 3.2 Dry Run Example
```bash
python3 scripts/cqc_executor.py --command "pytest tests/unit/" --perimeter-dir "skills/cqc" --dry-run
```

### 3.3 Active Execution Example
```bash
python3 scripts/cqc_executor.py --command "python3 -m unittest" --perimeter-dir "skills/cqc"
```

### 3.4 JSON Output Specification
```json
{
  "status": "passed",
  "exit_code": 0,
  "stdout": "...",
  "stderr": "",
  "boundary_violations": []
}
```

If a violation occurs:
```json
{
  "status": "failed",
  "exit_code": 1,
  "stdout": "",
  "stderr": "",
  "boundary_violations": [
    "Boundary violation: File created outside perimeter dir: /Users/.../unauthorized.tmp"
  ]
}
```

---

## 4. Remediation Runbook

If CQC status returns `"failed"`:
1. Check `boundary_violations` list for specific files created, modified, or deleted outside `--perimeter-dir`.
2. Re-scope the command to target paths strictly within `--perimeter-dir`.
3. If out-of-perimeter edits were intentional, expand `--perimeter-dir` to the parent workspace directory.
