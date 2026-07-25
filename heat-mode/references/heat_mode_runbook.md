# Heat Mode Offline Runbook

## Overview
Heat Mode triggers automatically upon experiencing 2 or more consecutive tool execution failures, providing self-healing anti-stall diagnostics to recover from deadlock states.

## Operational Workflow
1. **Detect Stall**: Monitor error count. If consecutive errors >= 2:
2. **Invoke Anti-Stall Diagnosis**:
   ```bash
   python3 ./scripts/anti_stall.py --error-log "<error_text>" --consecutive-failures 2 --recommend --json
   ```
3. **Execute Remediation**: Apply the recommended fallback step.
4. **Reset State**: Call `python3 ./scripts/anti_stall.py --reset` once task succeeds.
