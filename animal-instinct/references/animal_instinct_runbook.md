# Animal Instinct — Offline Runbook

Condensed operational steps. For outcome semantics and scope see
[`animal_instinct_guide.md`](./animal_instinct_guide.md).

## Standard loop
1. **Preview** the mutations without executing anything:
   ```bash
   python3 ./scripts/mutation_fuzzer.py --dry-run --mutations 10 --random-seed 1234 --json
   ```
2. **Run** against the target:
   ```bash
   python3 ./scripts/mutation_fuzzer.py --target "<script_path>" --mutations 100 --seed-inputs "tests/seeds/" --json
   ```
3. **Triage** `findings`. Each entry carries `outcome`, `mutation`, `payload`,
   `returncode`, and `detail`.
4. **Reproduce** with the reported seed:
   ```bash
   python3 ./scripts/mutation_fuzzer.py --target "<script_path>" --mutations 100 --random-seed <seed> --json
   ```
5. **Regress** — copy the failing `payload` into a permanent test case.

## Outcomes
| Outcome | Counts toward risk | Meaning |
|---|---|---|
| `ok` | no | Exit 0 |
| `rejected` | **no** | Exit 1/2, no traceback — correct input validation |
| `crash` | yes | Signal, unhandled traceback, or exit ≥ 3 |
| `timeout` | yes | Exceeded `--timeout` |
| `harness_error` | no | Target could not be executed — check `--target` |
| `unencodable` | no | Payload holds a NUL byte; argv cannot carry it. Excluded from the denominator |

## Flags
| Flag | Purpose |
|---|---|
| `--target PATH_OR_CMD` (`--target-script`) | **Required.** What to fuzz |
| `--mutations N` | Iterations (default 20) |
| `--seed-inputs SRC` (`--corpus`) | Dir, JSON file, or raw JSON string |
| `--random-seed N` | Reproducible run; always reported if omitted |
| `--timeout SEC` | Per-execution timeout (default 5) |
| `--max-findings N` | Recorded findings cap (default 25) |
| `--dry-run` | Print mutations, execute nothing |

## Exit codes
| Code | Meaning |
|---|---|
| 0 | Ran, no crashes or timeouts |
| 1 | At least one crash or timeout — usable as a CI gate |
| 2 | `--target` missing |

## Failure modes
- **Everything is `harness_error`** — `--target` is wrong. Report `status: ERROR`.
- **`risk_score` is 0 but the tool clearly rejects input** — correct. Graceful
  rejection is not a crash.
- **`findings_truncated` > 0** — raise `--max-findings`.
