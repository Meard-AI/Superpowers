---
name: cqc
description: Close-Quarters Combat micro-scope sandboxing & boundary enforcement engine. Locks agent execution perimeter to specific subdirectories or file globs to prevent out-of-scope code modifications.
allowed-tools:
  - run_command
  - view_file
  - write_to_file
  - replace_file_content
metadata:
  version: 1.0.0
  author: Antigravity Core Team
---

# Close-Quarters Combat (CQC) Playbook

**CQC** establishes a strict operational perimeter when modifying sensitive codebases or isolated sub-modules, preventing collateral modifications outside the allowed boundary.

## Triggers & Scope
- Triggered before performing code modifications in target sub-paths or high-risk repositories.
- Triggered when enforcing path security boundaries.

## Workflow Instructions

### 1. Validate Operational Boundary
Check whether a target path is allowed under the active whitelist:
```bash
python3 ./scripts/boundary_validator.py --allowed-paths "src/,lib/,skills/" --check-path "<target_file_path>" --json
```

### 2. Execute Bounded Command
Run commands strictly inside the locked scope using CQC Executor:
```bash
python3 ./scripts/cqc_executor.py --target-dir "<allowed_subpath>" --cmd "<command_string>" --json
```

## Error Handling
If path validation fails (`BOUNDARY_VIOLATION`):
1. Halt execution immediately without modifying out-of-bounds files.
2. Log boundary violation in handoff report.
