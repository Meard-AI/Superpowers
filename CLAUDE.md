# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A distribution package of **7 self-contained AI agent skills** (published as `github.com/Meard-AI/Superpowers`), plus a single-file marketing landing page. It is *not* an application — there is no build system and no package manager. Each skill folder is designed to be copied verbatim into an agent's skill directory (`.agents/skills/`, `.claude/skills/`, `~/.claude/skills/`) and run there.

**Python 3.8+, standard library only.** Adding a `pip` dependency to any script breaks the core portability promise — and `tests/test_skills.py::test_no_script_imports_third_party_modules` will fail.

## Commands

```bash
python3 -m unittest discover -s tests -v
```

That's the whole suite — 71 stdlib-only tests, no runner to install. Run a single test:

```bash
python3 -m unittest tests.test_skills.TestReflexRouter.test_reasoning_intent_vetoes_route_match
```

Every test corresponds to a defect from the v1 audit. They exist because each of these behaviours was once wrong in a way that produced a *confident, incorrect* answer — a boundary check that passed an escape, a stall detector that reported "nominal" while stalled. Treat a failure here as a correctness regression, not a style nit.

Verifying a script by hand: all of them accept `--json` and `--dry-run`, and most have a read-only mode (`--list`, `--status`, `--verify`, `--get-prompt`). Prefer those.

## Repository layout

Seven sibling skill directories, all identical in shape:

```
<skill-name>/
├── SKILL.md                     # YAML frontmatter + agent-facing playbook
├── scripts/*.py                 # standalone argparse CLI(s), stdlib only
└── references/<slug>_guide.md    # deep reference: rationale, threat model, schemas
    references/<slug>_runbook.md  # condensed operational steps + failure modes
```

`<slug>` is the skill name with `-` replaced by `_`. `tests/test_skills.py::test_every_skill_has_the_expected_layout` enforces this.

| Skill | Script(s) | Purpose |
|---|---|---|
| `ultra-instinct` | `reflex_router.py` | Classifies a query `reflex` vs `reasoning` to skip LLM loops on routine work |
| `copy-ability` | `trajectory_cloner.py` | Parses execution transcripts into a generated `SKILL.md` |
| `invisible-attacks` | `sandbox_enforcer.py` | Path boundary validation + speculative background task queue |
| `mastery` | `context_adapter.py` | Per-lifecycle-stage context budgets, tool allowlists, system prompts |
| `heat-mode` | `anti_stall.py` | Failure classification and recovery plans after repeated tool failures |
| `cqc` | `cqc_executor.py`, `boundary_validator.py` | Perimeter checking: validate a path/command, run inside a perimeter, diff for side-effects |
| `animal-instinct` | `mutation_fuzzer.py` | Reproducible mutation fuzzing of a target CLI |

`index_1.html` is a standalone manga-themed landing page (anime.js v3 + Lenis via CDN, inline CSS/JS). Open it directly in a browser — no server or build step.

## Conventions every script follows

Load-bearing across the suite; match them in any new or edited script.

- **`--json` everywhere, human text by default.** All eight scripts honour the flag. Agents consume the JSON path, so its shape must stay stable.
- **Status envelope.** JSON results carry `status` (`SUCCESS`, `ERROR`, `BLOCKED`, `OK`, `QUEUED`, `INVALID`, …) alongside domain fields.
- **Exit codes are semantic.** `boundary_validator` 0/1 = allowed/violation; `cqc_executor` 2 = blocked-or-violated, otherwise the child's own code; `trajectory_cloner` 3 = refused overwrite; `mutation_fuzzer` 1 = crashes found (CI gate), 2 = no target; `sandbox_enforcer --check-leak` 1 = live processes. Playbooks branch on these — don't collapse them.
- **Dual flag names.** Aliases keep older documented invocations working: `--command`/`--cmd`, `--perimeter-dir`/`--target-dir`, `--target`/`--target-script`, `--seed-inputs`/`--corpus`, `--log`/`--error-log`, `--name`/`--skill-name`, `--allowed-root`/`--target-dir`, `--run-cmd`/`--isolate-cmd`, `--stage`/`--load-adapter`. Keep the old name as an alias rather than breaking a documented command.
- **Runtime state lives outside the package.** Skills write to `$AGENT_SUPERPOWERS_STATE`, else `$XDG_STATE_HOME/agent-superpowers/`, else `~/.local/state/agent-superpowers/`. The skill folder is a read-only artifact that gets copied between machines; never write state into it. (`reflex_routes.json` is the one exception — it is shipped *configuration*, so don't commit experimental routes into it; use `--cache-file` for scratch work.)

## The honesty rule

Three skills previously returned hardcoded or fabricated results that were shaped exactly like real ones: a leak check that always said `SECURE`, a fuzzer that emitted `Simulated crash` findings with no target, a `--reset` for state that did not exist. This is the failure mode this repo is most prone to, because every tool here reports on something it cannot fully observe.

So: **a check that cannot fail must not exist, and a limit must be stated in the output, not hidden.**

In practice that means `cqc_executor` reports `watch_scope` and `watch_scope_note` naming what it did *not* monitor; static analysis returns `UNDECIDABLE` rather than "clean" when a command contains `$VAR`/`$(...)`/`~`/`eval`; `sandbox_enforcer --check-leak` carries a `scope_note` saying it only tracks processes it spawned; `context_adapter` returns `enforcement: "advisory"`; `mutation_fuzzer` excludes graceful rejections from `risk_score` and refuses to run without a target.

`cqc` and `invisible-attacks` are **mistake detectors, not security boundaries** — string analysis before `shell=True` cannot be made sound. Their docs say so explicitly and point at `sandbox-exec` / Landlock+seccomp / containers. Don't let a doc edit quietly upgrade that claim.

## Editing SKILL.md files

Frontmatter contract: `name` (must equal the folder name), `description`, `allowed-tools`, `metadata.version`. `description` is what an agent matches on to decide whether to load the skill, so it must state trigger conditions concretely — tests enforce the name match and a minimum description length.

Body shape: **Triggers & Scope** → **Workflow/Protocol** (numbered steps, each with the exact `python3 ./scripts/... --json` invocation) → **Enforcement Boundary** (where one applies) → **Error Handling**.

Use standard Agent Skills tool names (`Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob`), not the legacy Antigravity vocabulary. `context_adapter.py --tool-vocabulary antigravity` emits the legacy names for hosts that need them.

`tests/test_skills.py::TestSuiteContracts::test_skill_docs_reference_only_real_flags` parses every documented `script.py --flag` out of the markdown and checks it against the script's real `--help`. Doc drift is how the v1 playbooks became inert, so it is a test failure here, not a chore.

## When adding a new skill

Mirror an existing folder exactly: `SKILL.md` + `scripts/` + both `references/<slug>_guide.md` and `references/<slug>_runbook.md` (guide and runbook must be genuinely different — four pairs were byte-identical in v1). Then update the tree in [README.md](README.md) and add a matching `<article class="panel" data-skill="...">` card to [index_1.html](index_1.html) — the landing page enumerates skills by hand and will silently fall out of sync otherwise.

## Landing page constraints

- **CDN failure must stay survivable.** anime.js and Lenis are external. Capability is feature-detected (`typeof anime === 'function'`), each animation block is wrapped in `safely()`, and entrance `opacity: 0` is gated behind a `.js-animate` class set by a head script only when anime.js actually loaded. Without that gate a blocked CDN leaves the nav, cover, and all seven panels permanently invisible. The `.tear-overlay` is likewise `visibility: hidden` until JS adds `.tear-armed`.
- **`prefers-reduced-motion` disables the tear, the smooth-scroll hijack, and all entrance animations** — in CSS (with `!important`) as well as JS, so the CSS holds even if the JS path changes.
- **`prefers-color-scheme` sets the initial theme**; the toggle writes an explicit `data-theme` that overrides it. The toggle resolves the *current effective* theme before flipping — removing the attribute would be a no-op for a user whose OS is already dark.
- **Clipboard**: `navigator.clipboard` rejects on `file://` in Chrome. There is an `execCommand` fallback, and the button only says `DONE` when a copy actually happened.
