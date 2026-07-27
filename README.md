# Agent Superpowers — Skills Package

Seven self-contained agent skills, compatible with the [Agent Skills](https://github.com/anthropics/skills) `SKILL.md` standard read by Claude Code, Codex, Cursor, Gemini CLI, Windsurf, OpenCode, and others.

**Python 3.8+, standard library only. Zero `pip` dependencies.**

## The skills

| Skill | What it does |
|---|---|
| **ultra-instinct** | Routes routine queries (status checks, lint, tests) straight to a mapped command, skipping the reasoning loop. Reasoning intent always vetoes a route match. |
| **copy-ability** | Parses an execution transcript into the commands that were run and emits a `SKILL.md` playbook. |
| **invisible-attacks** | Validates path mutations against an allowed root; queues, runs, and tracks speculative background tasks. |
| **mastery** | Serves per-stage (plan / build / audit / format) context budgets, tool allowlists, focus rules, and system prompts. |
| **heat-mode** | Classifies repeated tool failures and returns a concrete recovery plan. |
| **cqc** | Checks a command for perimeter escape before running it, then diffs the filesystem for side-effects. |
| **animal-instinct** | Reproducible mutation fuzzing of a target CLI, with the exact payload recorded for every finding. |

## Directory structure

```text
Superpowers/
├── ultra-instinct/        # scripts/reflex_router.py
├── copy-ability/          # scripts/trajectory_cloner.py
├── invisible-attacks/     # scripts/sandbox_enforcer.py
├── mastery/               # scripts/context_adapter.py
├── heat-mode/             # scripts/anti_stall.py
├── cqc/                   # scripts/cqc_executor.py, scripts/boundary_validator.py
├── animal-instinct/       # scripts/mutation_fuzzer.py
├── tests/                 # stdlib regression suite
└── index_1.html           # landing page
```

Every skill folder has the same shape:

```text
<skill>/
├── SKILL.md                     # frontmatter + agent-facing playbook
├── scripts/*.py                 # standalone argparse CLIs
└── references/<slug>_guide.md    # rationale, threat model, schemas
    references/<slug>_runbook.md  # condensed steps + failure modes
```

## Install

Copy any skill folder into your agent's skill directory:

| Agent | Path |
|---|---|
| Claude Code | `.claude/skills/<skill>` (project) or `~/.claude/skills/<skill>` (global) |
| Antigravity | `.agents/skills/<skill>` at the workspace root |
| Cursor | `.cursor/skills/<skill>` (also reads `.agents/` and `.claude/`) |
| Windsurf | `.windsurf/skills/<skill>` (reload the workspace after adding) |
| OpenCode | `.opencode/skills/<skill>` (also reads `.claude/` and `.agents/`) |
| Others | `.agents/skills/<skill>` — the emerging cross-tool convention |

Nothing to install or build. Each skill is portable on its own; copy one or all seven.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

71 tests, no runner to install. Each one pins a behaviour that was previously wrong in a way that produced a confident but incorrect result.

## Scope and limits

These skills are honest about what they cannot do, and say so in their output rather than in a footnote:

- **`cqc` and `invisible-attacks` are mistake detectors, not security sandboxes.** Static analysis of a shell command is defeated by variable expansion, command substitution, `eval`, or any interpreter — those cases return `UNDECIDABLE` rather than "clean". Filesystem diffing only covers the roots it is told to watch, and every result names that scope. For an actual boundary use `sandbox-exec` (macOS), Landlock + seccomp or bubblewrap (Linux), or a container.
- **`mastery` is advisory.** It returns configuration for the calling agent to apply to itself; it cannot enforce a token budget or restrict a tool.
- **`animal-instinct` is a blackbox fuzzer** — no coverage feedback, no test-case minimization. For deeper work use [Atheris](https://github.com/google/atheris) or [Hypothesis](https://hypothesis.readthedocs.io/).
- **`copy-ability` output is a draft.** Generated commands come from a transcript and are unvalidated; review before running.

## Runtime state

Skills that persist state write to `$AGENT_SUPERPOWERS_STATE`, else `$XDG_STATE_HOME/agent-superpowers/`, else `~/.local/state/agent-superpowers/` — never inside the skill folder, so a copied folder stays a clean read-only artifact.
