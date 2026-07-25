---
name: invisible-attacks
description: Speculative execution shadowing and path boundary enforcement protocol. Manages background speculative pre-fetching, shadow task queues, and enforces file path mutation boundaries.
allowed-tools:
  - run_command
  - view_file
  - write_to_file
metadata:
  version: 1.0.0
  author: Agent Superpowers Team
  category: security-and-speculation
---

# Invisible Attacks () Skill Playbook

Execute non-destructive speculative background tasks (step N+1 pre-fetching, parallel background builds) while strictly enforcing path mutation boundaries to guarantee workspace isolation.

## Triggers & Scope
Activate  when:
1. Executing multi-step pipelines where background step N+1 preparation reduces total workflow latency.
2. Modifying critical or sensitive directories requiring strict path perimeter validation.
3. Queueing background speculative tasks to optimize task throughput.

## Path Boundary Enforcement Protocol
Before performing any file write or mutation operation, validate the target path against allowed root boundaries:

{
  "allowed": false,
  "target_path": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite/<target_file>",
  "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite/<allowed_dir>",
  "action": "write",
  "reason": "Target path '/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite/<target_file>' violates allowed boundary root '/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite/<allowed_dir>'"
}

- **If  (exit code 0)**: Proceed with file mutation.
- **If  (exit code 1)**: HALT file mutation immediately. Log security boundary breach and notify orchestrator.

## Speculative Queue & Shadowing Protocol
To enqueue a background speculative pre-fetch task:

{
  "status": "QUEUED",
  "task_id": "spec-014",
  "command": "<command>",
  "queue_length": 14,
  "dry_run": false
}

To query queued speculative task status:

{
  "status": "OK",
  "queue_length": 14,
  "speculative_queue": [
    {
      "task_id": "spec-001",
      "command": "npm build",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-002",
      "command": "<cmd>",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-003",
      "command": "npm test",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-004",
      "command": "ls -la",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-005",
      "command": "ls -la",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-006",
      "command": "ls -la",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-007",
      "command": "ls -la",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-008",
      "command": "ls -la",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-009",
      "command": "ls -la",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-010",
      "command": "ls -la",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-011",
      "command": "ls -la",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-012",
      "command": "ls -la",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-013",
      "command": "ls -la",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    },
    {
      "task_id": "spec-014",
      "command": "<command>",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    }
  ]
}

To run a isolated subshell execution:

{
  "status": "ERROR",
  "error": "[Errno 2] No such file or directory: '<allowed_dir>'",
  "command": "<command>"
}

## Security & Boundary Verification
Periodically verify background process isolation and detect orphan process leaks:

{
  "status": "SECURE",
  "leaks_detected": false,
  "monitored_directory": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite",
  "orphan_processes": []
}

## Error Recovery
- **Boundary Denials**: If a path mutation is blocked by boundary enforcement, do not attempt to bypass or force write outside permitted root. Request boundary relaxation from parent agent or scope update.
