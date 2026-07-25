# CQC (Close-Quarters Combat) Offline Runbook

## Overview
CQC enforces strict sub-path micro-scope sandboxing to prevent unauthorized path mutations during high-risk file modifications.

## Operational Workflow
1. **Validate Target Path**: Check whether target path is within allowed perimeter:
   ```bash
   python3 ./scripts/boundary_validator.py --allowed-paths "<allowed_dir>" --check-path "<target_path>" --json
   ```
2. **Execute Bounded Command**:
   ```bash
   python3 ./scripts/cqc_executor.py --target-dir "<allowed_dir>" --cmd "<command_string>" --json
   ```
3. **Verify Compliance**: Confirm no files outside `<allowed_dir>` were created or modified.
