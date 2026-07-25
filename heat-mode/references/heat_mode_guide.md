# Heat-Mode Offline Reference Guide & Runbook

## 1. Executive Summary
Heat-Mode is an anti-stall self-healing execution mode designed to prevent AI agents from getting trapped in tool error cycles, JSON formatting deadlocks, interactive command permission timeouts, or context degradation loops.

When standard execution stalls (defined as consecutive repeated errors reaching a threshold), Heat-Mode alters the agent's behavior strategy: it relaxes non-essential constraints, simplifies formats, switches diagnostic tools, and offloads state.

---

## 2. Stall Detection Mechanics

### 2.1 Indicators of Execution Stall
1. **Tool Error Cycles**: Calling the same tool repeatedly with identical parameters and receiving identical error messages.
2. **Schema & JSON Failures**: Retrying JSON parsing or strict formatting checks >3 times.
3. **Permission & Timeout Deadlocks**: Commands hanging or timing out while waiting for interactive input or external resources.
4. **Context Degradation**: Unproductive context window bloat where no new file changes or task progress occurs.

### 2.2 Threshold Configuration
- **Default Threshold**: 3 consecutive failures.
- **Aggressive Threshold**: 2 consecutive failures (for high-risk or time-sensitive tasks).
- **Relaxed Threshold**: 5 consecutive failures (for complex exploratory or multi-stage tasks).

---

## 3. CLI Helper: `anti_stall.py`

### 3.1 Usage
```bash
python3 scripts/anti_stall.py --help
```

### 3.2 Analyzing Log Files
```bash
python3 scripts/anti_stall.py --log /path/to/task.log --threshold 3
```

### 3.3 Passing Raw Strings
```bash
python3 scripts/anti_stall.py --log "Error: JSONDecodeError at line 1\nError: JSONDecodeError at line 1\nError: JSONDecodeError at line 1" --threshold 3
```

### 3.4 Pipe Input
```bash
cat task_output.log | python3 scripts/anti_stall.py --threshold 3
```

### 3.5 Expected JSON Schema Output
```json
{
  "stall_detected": true,
  "consecutive_failures": 3,
  "recovery_strategy": "Relax JSON strictness and drop non-essential format constraints.",
  "suggested_actions": [
    "Relax strict JSON schema validation and accept partial/flexible model output",
    "Use regex pattern extraction on raw output strings instead of strict json.loads()",
    "Drop non-essential output formatting rules to unblock execution flow"
  ]
}
```

---

## 4. Recovery Escalation Runbook

| Escalation Level | Trigger Condition | Recommended Recovery Action |
|------------------|-------------------|-----------------------------|
| **Level 1** | Repeated JSON or schema parsing errors | Switch to loose regex parsing, drop optional format checks, write raw string output to scratch file. |
| **Level 2** | Tool permission timeouts or path errors | Verify working directory is within workspace root, switch from interactive CLI commands to direct atomic scripts. |
| **Level 3** | Deadlocked tasks or process hangs | Terminate background tasks via `manage_task`, reset active execution memory, offload progress to `.agents/scratch/`. |
| **Level 4** | Persistent unrecoverable failure | Perform partial handoff with structured state dump to parent orchestrator. |

---

## 5. Integration Patterns
Agents should run `anti_stall.py` whenever a tool call fails or when error count accumulates. If `stall_detected: true` is returned, immediately execute the top item in `suggested_actions`.
