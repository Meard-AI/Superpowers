# Animal Instinct Offline Runbook

## Overview
Animal Instinct provides automated genetic fuzzing and mutation testing against target scripts, APIs, and CLI tools.

## Operational Workflow
1. **Prepare Target**: Identify target script or CLI tool path.
2. **Execute Fuzzing Loop**:
   ```bash
   python3 ./scripts/mutation_fuzzer.py --target-script "<script_path>" --mutations 10 --seed "initial_seed" --json
   ```
3. **Analyze Crashes**: Check report for exit codes outside standard range (`0`, `1`, `2`).
