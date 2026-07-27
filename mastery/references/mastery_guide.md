# Mastery — Context Adapter Guide

## 1. Overview
Mastery supplies stage-specific operating parameters — context budget, tool allowlist,
focus rules, and system prompt — for the four phases of a development task:
**planning**, **building**, **auditing**, **refactoring**.

The premise is that an agent's ideal posture differs sharply by phase. A planning agent
that can edit files starts editing. An auditing agent that can add features adds
features. Naming the stage explicitly, and narrowing capability to match, keeps each
phase honest.

---

## 2. Enforcement Boundary — read this first

This adapter is **advisory and stateless**. It returns configuration; the calling agent
applies it to itself. It cannot restrict a tool, cap a token count, or verify
compliance. Only the host runtime can do that.

Every result carries an `enforcement` field saying exactly this, so the output is never
mistaken for a guarantee. There is no `--dry-run` because nothing is ever persisted.

---

## 3. Stage Lifecycle Matrix

| Stage | Slug | Tokens | Bytes | Capabilities | Priority focus |
|---|---|---|---|---|---|
| `plan` | `planning` | 8,000 | 32 KB | read, grep, glob | Architecture specs, layout definitions, interface contracts |
| `build` | `building` | 16,000 | 64 KB | read, edit, write, run | Minimal code edits, targeted helpers, co-located tests |
| `audit` | `auditing` | 12,000 | 48 KB | read, run, grep | Edge cases, boundary enforcement, CLI compliance, regression |
| `format` | `refactoring` | 8,000 | 32 KB | read, edit, run | Runbooks, clean layout, handoff compilation |

Aliases: `planning`, `building`, `auditing`, `refactoring` also resolve.

### 3.1 Why building gets the largest budget
Building is the only stage that must hold *both* the target file and its surrounding
contracts in working memory while producing an edit. Planning reads broadly but
shallowly; auditing and refactoring work from an already-narrowed set.

These figures are deliberate starting points, not measurements. Tune them per project.

---

## 4. Progressive Context Disclosure

| Stage | Discipline |
|---|---|
| **Planning** | Read and search only. Produce a plan before touching code. Keep working memory light. |
| **Building** | Re-read every target file before modifying it. Minimal-change principle. Validate after each edit. |
| **Auditing** | Re-check boundary safety, run the harness, verify `--help` output. Add no features. Hunt for hardcoded verification cheats. |
| **Refactoring** | Finalize docs and runbooks. Confirm scripts still run from `scripts/`. Compile the handoff report. |

---

## 5. Tool Vocabularies

Tool names are host-specific. The adapter stores neutral *capabilities* and maps them
at output time.

| Capability | `standard` (default) | `antigravity` |
|---|---|---|
| read | `Read` | `view_file` |
| write | `Write` | `write_to_file` |
| edit | `Edit` | `replace_file_content` |
| run | `Bash` | `run_command` |
| grep | `Grep` | `grep_search` |
| glob | `Glob` | `find_by_name` |

`standard` matches the Agent Skills convention used by Claude Code, Codex, Cursor,
Gemini CLI, and the other implementations of the shared `SKILL.md` specification.
Use `--tool-vocabulary antigravity` on Antigravity or Windsurf.

Adding a host means adding one entry to `TOOL_VOCABULARIES`; the stage definitions
never change.

---

## 6. Handoff Report Template

The refactoring stage's focus rules call for a handoff report. It has five components:

1. **Objective** — what the task set out to change, in one or two sentences.
2. **Changes made** — files touched and why, grouped by intent rather than by file.
3. **Verification** — commands run and their actual results. Failures included.
4. **Known gaps** — anything skipped, deferred, or left uncertain, stated plainly.
5. **Next steps** — the concrete follow-up actions, ordered.

Write it to `handoff.md` in the working directory. Component 4 is the one most often
dropped and the one most worth keeping.

---

## 7. CLI Reference

| Flag | Purpose |
|---|---|
| `--stage NAME` (`--load-adapter`) | Load a stage adapter |
| `--list` (`--list-stages`) | List stages, aliases, and vocabularies |
| `--get-prompt` | Emit only the system prompt string |
| `--tool-vocabulary NAME` | `standard` or `antigravity` |
| `--json` | Machine-readable output |

---

## 8. Output Schema

```json
{
  "status": "SUCCESS",
  "stage": "build",
  "canonical_stage": "building",
  "stage_name": "Build & Implement Features",
  "context_budget": { "token_limit": 16000, "byte_limit": 65536, "priority_focus": "..." },
  "capabilities": ["read", "edit", "write", "run"],
  "tool_vocabulary": "standard",
  "allowed_tools": ["Read", "Edit", "Write", "Bash"],
  "focus_rules": ["..."],
  "system_prompt": "[MASTERY ADAPTER: BUILDING STAGE] ...",
  "enforcement": "advisory — the calling agent must apply this itself; ..."
}
```

---

## 9. Integration Pattern
Call the adapter at each phase boundary, adopt the returned `system_prompt`, and hold
yourself to `focus_rules` for the duration of the stage. The value is the explicit
transition — deciding *which* phase you are in is most of the benefit.
