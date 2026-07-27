# Mastery — Offline Runbook

Condensed operational steps. For budget rationale and the handoff template see
[`mastery_guide.md`](./mastery_guide.md).

## Standard loop
1. **Load** the adapter when entering a stage:
   ```bash
   python3 ./scripts/context_adapter.py --stage build --json
   ```
2. **Apply it to yourself.** Adopt `system_prompt`, respect `context_budget`, restrict
   work to `allowed_tools`, follow `focus_rules`. Nothing enforces this for you.
3. **Re-load** on every stage transition.

## Stages
| Short | Canonical | Tokens | Focus |
|---|---|---|---|
| `plan` | `planning` | 8,000 | Architecture, specs, layout discovery |
| `build` | `building` | 16,000 | Minimal edits, test validation |
| `audit` | `auditing` | 12,000 | QA, boundary checks, CLI compliance |
| `format` | `refactoring` | 8,000 | Runbooks, cleanup, handoff |

## Flags
| Flag | Purpose |
|---|---|
| `--stage NAME` (`--load-adapter`) | Load a stage adapter |
| `--list` (`--list-stages`) | Show all stages and aliases |
| `--get-prompt` | Print only the system prompt |
| `--tool-vocabulary standard\|antigravity` | Tool-name dialect (default `standard`) |
| `--json` | Machine-readable output |

## Tool vocabularies
| Capability | `standard` | `antigravity` |
|---|---|---|
| read | `Read` | `view_file` |
| write | `Write` | `write_to_file` |
| edit | `Edit` | `replace_file_content` |
| run | `Bash` | `run_command` |
| grep | `Grep` | `grep_search` |
| glob | `Glob` | `find_by_name` |

## Exit codes
| Code | Meaning |
|---|---|
| 0 | Adapter loaded or listed |
| 1 | Unknown stage name |

## Failure modes
- **Unknown stage** — run `--list` for accepted names; both short and canonical work.
- **Tool names do not match your host** — switch `--tool-vocabulary`.
- **Budget appears not to apply** — correct. This adapter is advisory; see
  `enforcement` in the output.
