---
name: animal-instinct
description: Genetic fuzzing & mutation testing engine. Runs parallel input mutations, edge-case payload injections, and crash detection loops to find hidden bugs or boundary vulnerabilities.
allowed-tools:
  - run_command
  - view_file
metadata:
  version: 1.0.0
  author: Antigravity Core Team
---

# Animal Instinct Playbook

**Animal Instinct** executes genetic mutation fuzzing against target scripts, APIs, or CLI tools to expose unhandled exceptions, null pointer bugs, or crash conditions.

## Triggers & Scope
- Triggered during deep bug hunting, edge-case testing, or security fuzzing.
- Triggered when verifying robustness of CLI parsers and script interfaces.

## Workflow Instructions

### 1. Execute Genetic Fuzzer
Run mutation fuzzing against target script using seed payloads:
```bash
python3 ./scripts/mutation_fuzzer.py --target-script "<script_path>" --mutations 10 --seed "test_payload" --json
```

### 2. Analyze Fuzzing Report
Review generated mutations and crash logs. If a mutation triggers a crash (exit code != 0), document the crash payload.

## Error Handling
If target script crashes on mutation $K$:
1. Save seed payload and backtrace for regression test suite.
2. Report boundary vulnerability in handoff report.
