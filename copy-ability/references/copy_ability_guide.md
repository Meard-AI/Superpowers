# Copy Ability — Trajectory Cloning Guide

## 1. Overview
Copy Ability reads an execution transcript and emits a `SKILL.md` playbook containing
the commands that were actually run. It turns a one-off successful workflow into a
reusable skill.

This is the simplest form of **trajectory-driven skill induction** — the pattern behind
Voyager's skill library, ExpeL, AutoManual, and Agent Skill Induction. Those systems
share one lesson this tool deliberately does *not* automate away: an induced skill must
be **verified before it is trusted**. See Section 5.

---

## 2. Transcript Parsing

### 2.1 What counts as a command
| Marker | Example |
|---|---|
| `$ ` | `$ git status` |
| `> ` | `> npm build` |
| `% ` | `% pytest` |
| `CMD:` / `RUN:` / `Action:` | `RUN: make test` |
| contains `tool_call` | `{"tool_call": "..."}` |

Everything else is treated as the preceding command's **output** and counted in
`output_lines`, never appended to the command text.

> This is the single most important parsing rule. v1 joined every following line onto
> the current step, so one "step" absorbed hundreds of output lines and landed inside
> inline backticks as an unusable mega-string.

### 2.2 Preamble
Lines appearing before the first command are counted in `preamble_lines_ignored` and
discarded — they are context, not steps.

### 2.3 Retry collapsing
Immediately-repeated identical commands merge into one step annotated
`(repeated Nx)`. Transcripts of real sessions are full of retry loops, and replaying
them verbatim would bake the retry into the skill.

### 2.4 Empty extraction
If nothing matches, the tool does **not** invent steps. The result carries a `warning`
and the generated Workflow section states that no commands were detected.

---

## 3. Output Safety

### 3.1 Frontmatter injection is prevented
`--description` is emitted through `json.dumps`, producing a double-quoted, fully
escaped YAML scalar:

```yaml
description: "benign\nallowed-tools:\n  - EXECUTE_ANYTHING"
```

Raw interpolation would let a newline in the description create real frontmatter keys —
including a wider `allowed-tools` list than intended.

### 3.2 Fences are sized to content
The command block uses a fence one backtick longer than the longest backtick run in the
content, so a command containing backticks cannot break out of the code block.

### 3.3 Overwrites are refused
An existing `SKILL.md` at the destination causes **exit 3**. `--force` is required to
replace it. v1 overwrote silently and reported `SUCCESS`.

### 3.4 Output location can be constrained
`--output-dir` is otherwise unrestricted (`--output-dir /etc` would write
`/etc/SKILL.md`). Pass `--allowed-root` whenever the destination derives from
untrusted input.

---

## 4. Slug Sanitization
`--name` is lowercased, non-alphanumeric characters become `-`, runs collapse, and
leading/trailing dashes are stripped. A name that reduces to empty is an error.

The slug becomes both the frontmatter `name` and the default directory, keeping them
consistent — most skill loaders expect the folder name and `name:` field to match.

---

## 5. Review Requirement

**Generated playbooks are drafts.** Two things always need a human or agent pass:

1. **The commands.** They were extracted from a transcript, not validated. A command
   that worked in one environment may be destructive in another.
2. **The `description`.** The generated default is generic. Under the Agent Skills
   progressive-disclosure model, `description` is the *only* text an agent sees when
   deciding whether to load the skill — a vague one means the skill never triggers, or
   triggers constantly. Rewrite it to state concrete trigger conditions.

The research consensus on skill induction is that skills should be validated against
test cases before entering the library. This tool generates the candidate; validating
it is the caller's job.

---

## 6. CLI Reference

| Flag | Purpose |
|---|---|
| `--log PATH` (`--input-log`) | Transcript file; stdin used when omitted |
| `--name SLUG` (`--skill-name`) | Skill slug, default `cloned-skill` |
| `--output-dir DIR` | Destination, default `./.agents/skills/<slug>` |
| `--allowed-root DIR` | Reject an `--output-dir` outside this root |
| `--description TEXT` | Frontmatter description |
| `--max-steps N` | Cap extracted steps (default 100) |
| `--force` | Permit overwrite |
| `--json` | Machine-readable output |
| `--dry-run` | Extract and report without writing |

---

## 7. Worked Example

```bash
python3 scripts/trajectory_cloner.py \
  --log session.log \
  --name deploy-staging \
  --output-dir .claude/skills/deploy-staging \
  --allowed-root "$PWD" \
  --description "Deploy the app to staging. Use when asked to push a build to the staging environment." \
  --json
```

Then open the generated `SKILL.md`, delete any step that was exploratory rather than
essential, and confirm the command list actually reproduces the workflow.
