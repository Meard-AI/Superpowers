---
name: heat-mode
description: Anti-stall self-healing & error recovery engine. Triggers upon 2+ consecutive tool failures, temporarily spiking reasoning flexibility, dropping format constraints, and executing raw fallback diagnostics.
allowed-tools:
  - run_command
  - view_file
metadata:
  version: 1.0.0
  author: Antigravity Core Team
---

# Heat Mode Playbook

**Heat Mode** is an emergency anti-stall recovery mechanism. When an agent experiences 2 or more consecutive tool execution failures or command loops, standard constraints are temporarily relaxed to diagnose and break out of the stall loop.

## Triggers & Scope
- Triggered automatically after 2 consecutive tool or command failures.
- Triggered when encountering execution deadlocks or infinite retry loops.

## Workflow Instructions

### 1. Diagnose Stall State
Pass the error log to the anti-stall recovery engine:
```bash
python3 ./scripts/anti_stall.py --error-log "<error_trace>" --consecutive-failures 2 --recommend --json
```

### 2. Execute Remediation Plan
Follow the returned fallback action (e.g. relaxing JSON strictness, running raw CLI diagnostics, checking directory permissions).

### 3. Reset Operational Heat
Once execution succeeds, reset error counters:
```bash
python3 ./scripts/anti_stall.py --reset --json
```

## Error Handling
If Heat Mode fails to break the stall loop:
1. Escalate to parent orchestrator with full diagnostic trace.
2. Log partial handoff report explaining failure point.
