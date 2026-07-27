---
name: animal-instinct
description: Mutation fuzzing for CLI tools and scripts. Use during bug hunting or robustness testing to mutate seed inputs against a target and get reproducible crash findings with the exact payloads.
allowed-tools:
  - Bash
  - Read
metadata:
  version: 2.0.0
  author: Agent Superpowers Team
  category: testing
---

# Animal Instinct Playbook

**Animal Instinct** runs mutation fuzzing against a target script or CLI to expose
unhandled exceptions, signal crashes, and hangs.

## Triggers & Scope
- Trigger during deep bug hunting, edge-case testing, or robustness verification.
- Trigger when validating that a CLI parser handles malformed input gracefully.

## Workflow Instructions

### 1. Preview the mutations (no execution)

```bash
python3 ./scripts/mutation_fuzzer.py --dry-run --mutations 10 --random-seed 1234 --json
```

### 2. Run the fuzzer

```bash
python3 ./scripts/mutation_fuzzer.py --target "<script_path>" --mutations 100 --seed-inputs "tests/seeds/" --json
```

`--target` is **required**. Without it the tool exits `2` rather than emitting a report
for work it never did.

### 3. Reproduce a finding

Every report includes `random_seed` and a `replay_hint`. Re-running with the same
`--random-seed` and `--mutations` regenerates the identical mutation sequence, and each
finding records the exact `payload` that produced it.

```bash
python3 ./scripts/mutation_fuzzer.py --target "<script_path>" --mutations 100 --random-seed <seed> --json
```

### 4. Read the outcomes

| Outcome | Meaning | Counts toward risk? |
|---|---|---|
| `ok` | Exit 0 | No |
| `rejected` | Exit 1 or 2 with no traceback — the target correctly refused bad input | **No** |
| `crash` | Killed by a signal, unhandled traceback, or exit ≥ 3 | Yes |
| `timeout` | Exceeded `--timeout` (default 5s) | Yes |
| `harness_error` | The target could not be executed at all | No (flags a bad `--target`) |
| `unencodable` | Payload contains a NUL byte, which POSIX argv cannot carry | No (excluded from the denominator) |

Exit code is `1` when any crash or timeout was found, `0` otherwise — usable as a CI gate.

## Execution Model
The target is invoked through an **argv list with `shell=False`**. Fuzz payloads can
never be interpreted as shell commands, so the fuzzer cannot execute its own payloads
against the host. Payloads are delivered as a single positional argument.

## Scope
This is a blackbox random fuzzer: no coverage feedback and no test-case minimization.
For deeper work use a coverage-guided engine (Atheris) or a property-based tester
(Hypothesis), both of which shrink failures to a minimal reproducer.

## Error Handling
When a crash is found:
1. Save the `payload` and `random_seed` into a regression test.
2. Report the finding, including `mutation` and `detail`, in the handoff.
