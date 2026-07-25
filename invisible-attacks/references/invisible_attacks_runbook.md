# Invisible Attacks () Offline Reference Runbook

## Overview
Invisible Attacks provides speculative background shadowing and sandbox boundary enforcement. By pre-fetching resources or launching speculative tasks in background shadow queues while enforcing strict path boundaries, agents maintain high speed and process safety.

## Key Capabilities
1. **Path Boundary Enforcement**: Hard validation of target file paths against allowed root boundaries (, , ). Non-zero exit code on unauthorized mutations.
2. **Speculative Queue Management**: Async queuing and status tracking for speculative pre-fetch commands (, ).
3. **Subshell Isolation**: Isolated execution context with  environment variables ().
4. **Leak Detection**: Systems process tree checks for orphan processes ().

## CLI Usage Guide
{
  "allowed": true,
  "target_path": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite/scripts/sandbox_enforcer.py",
  "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite",
  "action": "write",
  "reason": "Path '/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite/scripts/sandbox_enforcer.py' is within allowed root '/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite'"
}
{
  "allowed": false,
  "target_path": "/private/etc/passwd",
  "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite",
  "action": "write",
  "reason": "Target path '/private/etc/passwd' violates allowed boundary root '/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite'"
}
{
  "status": "QUEUED",
  "task_id": "spec-015",
  "command": "pytest tests/",
  "queue_length": 15,
  "dry_run": false
}
{
  "status": "OK",
  "queue_length": 15,
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
    },
    {
      "task_id": "spec-015",
      "command": "pytest tests/",
      "status": "QUEUED",
      "allowed_root": "/Users/kushagargargsmacbook/meard-skills/agent-superpowers-suite"
    }
  ]
}
{
  "status": "SUCCESS",
  "exit_code": 0,
  "command": "ls -la",
  "stdout": "total 24
drwxr-xr-x@  5 kushagargargsmacbook  staff    160 25 Jul 16:55 __pycache__
-rw-r--r--   1 kushagargargsmacbook  staff      0 25 Jul 17:03 --json
drwxr-xr-x  10 kushagargargsmacbook  staff    320 25 Jul 17:02 .
drwxr-xr-x   5 kushagargargsmacbook  staff    160 25 Jul 16:49 ..
drwxr-xr-x  16 kushagargargsmacbook  staff    512 25 Jul 17:01 .agents
-rw-r--r--   1 kushagargargsmacbook  staff  11530 25 Jul 16:49 PROJECT.md
drwxr-xr-x  18 kushagargargsmacbook  staff    576 25 Jul 16:57 references
drwxr-xr-x  11 kushagargargsmacbook  staff    352 25 Jul 16:51 scripts
drwxr-xr-x   9 kushagargargsmacbook  staff    288 25 Jul 16:48 skills
drwxr-xr-x  10 kushagargargsmacbook  staff    320 25 Jul 16:57 tests",
  "stderr": ""
}
