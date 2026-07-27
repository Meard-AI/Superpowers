# Copy Ability — Offline Runbook

Condensed operational steps. For transcript format details see
[`copy_ability_guide.md`](./copy_ability_guide.md).

## Standard loop
1. **Preview** what would be extracted:
   ```bash
   python3 ./scripts/trajectory_cloner.py --log '<log_file>' --dry-run --json
   ```
2. **Check `extracted_steps`.** If it is empty, the transcript uses an unrecognized
   format — see the prefix table below before proceeding.
3. **Generate**:
   ```bash
   python3 ./scripts/trajectory_cloner.py --log '<log_file>' --name '<skill_name>' --output-dir '<dir>' --json
   ```
4. **Review the generated SKILL.md by hand.** Commands came from a transcript and are
   unvalidated. Rewrite the `description` so it states trigger conditions concretely.

## Recognized command prefixes
`$ ` · `> ` · `% ` · `CMD:` · `RUN:` · `Action:` · any line containing `tool_call`

Every other line counts as the preceding command's output.

## Flags
| Flag | Purpose |
|---|---|
| `--log PATH` (`--input-log`) | Transcript file; stdin also accepted |
| `--name SLUG` (`--skill-name`) | Skill slug (sanitized) |
| `--output-dir DIR` | Destination (default `./.agents/skills/<slug>`) |
| `--allowed-root DIR` | Constrain `--output-dir` beneath this root |
| `--description TEXT` | Frontmatter description (safely escaped) |
| `--max-steps N` | Extraction cap (default 100) |
| `--force` | Overwrite an existing SKILL.md |
| `--dry-run` | Extract without writing |

## Exit codes
| Code | Meaning |
|---|---|
| 0 | Generated (or previewed) successfully |
| 1 | Bad input — missing log, unreadable file, output outside `--allowed-root` |
| 3 | Refused to overwrite an existing SKILL.md; pass `--force` |

## Failure modes
- **`extracted_steps` empty + `warning` set** — no line matched a command prefix.
  Preprocess the transcript to prefix commands with `$ `.
- **Exit 3** — target exists. Confirm you want to lose it, then `--force`.
- **`steps_truncated: true`** — hit `--max-steps`; raise it.
