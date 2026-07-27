---
name: mastery
description: Stage-specific context adapter. Use when transitioning between development lifecycle phases (planning, building, auditing, refactoring) to load that stage's context budget, tool allowlist, focus rules, and system prompt.
allowed-tools:
  - Bash
  - Read
  - Write
metadata:
  version: 2.0.0
  author: Agent Superpowers Team
  category: context-optimization
---

# Mastery Skill Playbook

Manage context budget allocation, system prompt directives, and progressive disclosure
across the software development lifecycle stages: **planning**, **building**,
**auditing**, and **refactoring**.

## Triggers & Scope
Activate mastery when:
1. Transitioning between lifecycle phases (e.g. from architectural planning to active building).
2. Operating under strict context window budgets where unused tool directives should be pruned.
3. Aligning agent execution persona with stage-specific constraints.

## Context Adapter Protocol

Load the budget, tool allowlist, and focus rules for a stage:

```bash
python3 ./scripts/context_adapter.py --stage build --json
```

Extract only the raw system prompt for a stage:

```bash
python3 ./scripts/context_adapter.py --stage audit --get-prompt
```

List every registered stage adapter:

```bash
python3 ./scripts/context_adapter.py --list --json
```

Emit legacy Antigravity/Windsurf tool names instead of the standard vocabulary:

```bash
python3 ./scripts/context_adapter.py --stage build --tool-vocabulary antigravity --json
```

## Stage Lifecycle Matrix

| Stage | Canonical Slug | Token Budget | Byte Budget | Priority Focus |
|---|---|---|---|---|
| `plan` | `planning` | 8,000 | 32 KB | Architecture, specifications, layout discovery |
| `build` | `building` | 16,000 | 64 KB | Minimal code edits, unit test validation |
| `audit` | `auditing` | 12,000 | 48 KB | Quality assurance, boundary validation, CLI compliance |
| `format` | `refactoring` | 8,000 | 32 KB | Runbooks, code cleanup, handoff compilation |

## Progressive Context Disclosure Rules
- **Planning**: Restrict to read and search capabilities (`Read`, `Grep`, `Glob`). Keep working memory light.
- **Building**: Enable editing capabilities (`Read`, `Edit`, `Write`, `Bash`). Maintain strict minimal-change focus.
- **Auditing**: Re-check boundary safety and execute test harnesses. Focus on detecting defects and hardcoded verification cheats.
- **Refactoring**: Finalize documentation and offline runbooks, then compile the handoff report.

## Enforcement Boundary
This adapter is **advisory and stateless**. It returns configuration for the calling
agent to apply to itself. It cannot restrict a tool or enforce a token budget — only
the host runtime can do that. Treat the output as instructions to follow, not as a
guarantee that has already been applied.

## Error Handling
An unknown stage exits `1` with `{"status": "ERROR"}`. Valid stage names are listed by
`--list`; both short (`plan`) and canonical (`planning`) forms are accepted.
