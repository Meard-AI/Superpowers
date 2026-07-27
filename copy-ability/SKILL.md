---
name: copy-ability
description: Trajectory ingestion and skill generator. Use when an execution log, session transcript, or CLI turn history should be packaged into a reusable SKILL.md playbook.
allowed-tools:
  - Bash
  - Read
  - Write
metadata:
  version: 2.0.0
  author: Agent Superpowers Team
  category: automation
---

# Copy Ability Skill Playbook

Parse an execution transcript into the commands that were actually run, and emit a
SKILL.md playbook from them.

## Triggers & Scope
Activate copy-ability when:
1. The user supplies execution logs or CLI transcripts to package into a skill.
2. An observed successful workflow should be cloned into a reusable playbook.

## Protocol

Preview what would be extracted, without writing anything:

```bash
python3 ./scripts/trajectory_cloner.py --log '<log_file>' --dry-run --json
```

Generate the skill:

```bash
python3 ./scripts/trajectory_cloner.py --log '<log_file>' --name '<skill_name>' --output-dir '<dir>' --json
```

Constrain where it may write:

```bash
python3 ./scripts/trajectory_cloner.py --log '<log_file>' --name '<skill_name>' --output-dir '<dir>' --allowed-root "$PWD" --json
```

Transcript text may also be piped on stdin instead of `--log`.

## Recognized Transcript Format
A line is treated as a **command** when it starts with `$`, `>`, `%`, `CMD:`, `RUN:`,
or `Action:`, or contains `tool_call`. Every other line is counted as that command's
output and is not merged into the command text. Immediately-repeated commands (retry
loops) collapse into a single step with a `repeated Nx` note.

If no commands are detected, the result carries a `warning` and the generated
Workflow section says so explicitly rather than emitting a fabricated step list.

## Safety Rules
- **Never overwrites.** An existing `SKILL.md` causes exit `3`. Pass `--force` to replace it.
- **`--description` cannot inject frontmatter.** It is emitted as a JSON-quoted YAML
  scalar, so newlines and `:` are escaped rather than creating new keys.
- **`--allowed-root` constrains `--output-dir`.** Without it, the output directory is
  unrestricted — pass it whenever the destination is derived from untrusted input.

## Review Requirement
Generated playbooks are extracted from a transcript and have **not** been validated.
Read every command in the output before running it, and edit the generated
`description` so it states the skill's trigger conditions concretely — that field is
what an agent matches on to decide whether to activate the skill.
