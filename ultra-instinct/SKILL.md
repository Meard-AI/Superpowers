---
name: ultra-instinct
description: Deterministic reflex routing for routine queries. Use before starting a reasoning loop on a short, routine request (status checks, linting, running tests) to check whether a pre-mapped command answers it directly.
allowed-tools:
  - Bash
  - Read
  - Write
metadata:
  version: 2.0.0
  author: Agent Superpowers Team
  category: compute-optimization
---

# Ultra Instinct Skill Playbook

Skip a multi-step reasoning loop for genuinely routine operations by matching the query
against a pre-computed reflex route table.

## Triggers & Activation Scenarios
Activate ultra-instinct when:
1. Receiving a short, routine subtask (repository status checks, linting, test execution).
2. Operating under low-latency constraints where a reasoning round-trip is wasteful.

## Protocol

Classify the query before reasoning:

```bash
python3 ./scripts/reflex_router.py --query '<query>' --json
```

- **`tier == "reflex"`** — run `matched_command` directly. It is always a real,
  executable command string.
- **`tier == "reasoning"`** — proceed with the standard reasoning loop.

## Classification Order (important)

Reasoning intent is evaluated **first** and vetoes any route match. A query containing
`explain`, `why`, `refactor`, `design`, `compare`, `review`, or a compound structure
(`&&`, `;`, `then`, `because`) always returns `reasoning`, even when it also mentions a
tool name.

> `explain why our eslint config is failing` → `reasoning`, not a linter invocation.

A `reflex` verdict is **only** returned alongside a concrete `matched_command`. If the
query looks routine but no route maps it, the verdict is `reasoning`.

## Managing Routes

```bash
python3 ./scripts/reflex_router.py --list --json
```

```bash
python3 ./scripts/reflex_router.py --add-route '(?i)^\s*make\s+build\s*$' --command 'make build' --json
```

```bash
python3 ./scripts/reflex_router.py --invalidate '(?i)^\s*make\s+build\s*$' --json
```

Check that every stored route compiles and maps to a command:

```bash
python3 ./scripts/reflex_router.py --verify --json
```

## Route Authoring Rules
- **Anchor patterns** with `^\s*...\s*$`. An unanchored `.*lint.*` matches
  "explain the lint failures" and mis-routes it.
- **Every route needs a real command.** Placeholder values are rejected by `--verify`
  and skipped at match time — the playbook runs `matched_command` verbatim.
- **Invalid regexes are rejected at `--add-route` time** and skipped (not fatal) at
  match time, so a bad route can never take down classification.

## Error Handling
`--verify` exits `1` and lists every unusable route. Repair or `--invalidate` them
before relying on reflex routing.
