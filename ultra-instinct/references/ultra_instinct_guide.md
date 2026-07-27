# Ultra Instinct — Reflex Routing Guide

## 1. Overview
Ultra Instinct decides whether a query deserves a reasoning loop at all. Routine
requests ("git status", "npm test") map to a fixed command and run with no model
round-trip. Everything else falls through untouched.

This is the *rule-based* tier of query routing — the simplest of the three common
strategies (rule-based, semantic, predictive). It is cheap and fully deterministic,
and its weakness is precision: a badly written rule silently runs the wrong command.
Most of this guide is about not writing badly written rules.

---

## 2. Classification Order

The order is deliberate and is the single most important property of the router.

```
1. Empty query            → reasoning
2. Reasoning-intent veto  → reasoning     ← evaluated BEFORE route matching
3. Route pattern match    → reflex (with command) or reasoning (low confidence)
4. Reflex heuristics      → reasoning (no command available to run)
5. Fallback               → reasoning
```

### 2.1 Why the veto comes first
A query can contain a tool name *and* be a reasoning request:

> "explain why our eslint config is failing and refactor it"

Matching routes first would hit an `eslint` pattern and answer a design question by
shelling out to a linter. The veto scans for reasoning keywords (`explain`, `why`,
`design`, `refactor`, `analyze`, `compare`, `review`, `recommend`, `investigate`,
`decide`, …) and compound-command markers (`&&`, `;`, `|`, `then`, `because`) and
returns `reasoning` before any route is consulted.

### 2.2 Why a reflex verdict always carries a command
The playbook instructs the agent to run `matched_command` verbatim. A `reflex` verdict
with `matched_command: null` would be an instruction to execute nothing. When the
heuristics find a query routine but no route maps it, the verdict downgrades to
`reasoning` with an explanatory `reason`.

---

## 3. Route Authoring Rules

### 3.1 Anchor every pattern
```
BAD   (?i).*lint.*              matches "explain the lint failures"
GOOD  (?i)^\s*(flake8|python\s+lint)\s*$
```
Unanchored `.*x.*` patterns are the primary source of mis-routing.

### 3.2 One command per intent
Do not map a family of queries to one command. `git status|git diff` sharing a single
`git status --short` command means asking for a diff silently returns a status.

### 3.3 Commands must be real
Every `command` value is executed verbatim. Placeholders (`sys_info`, `TODO`) are
rejected by `--verify` and skipped at match time.

### 3.4 Match the ecosystem
`npm test` must map to `npm test`, not to `python3 -m unittest`. Separate routes per
language rather than one "run tests" route.

---

## 4. CLI Reference

| Flag | Purpose |
|---|---|
| `--query TEXT` | Classify a query (also reads stdin) |
| `--tier-threshold FLOAT` | Confidence floor for a `reflex` verdict (default `0.70`) |
| `--list` | Print all registered routes |
| `--verify` | Check every route compiles and has a command; exit `1` on problems |
| `--add-route PATTERN --command CMD` | Register a route (`--confidence` optional) |
| `--invalidate PATTERN` | Remove routes with an exactly matching pattern |
| `--cache-file PATH` | Use an alternate route file |
| `--json` | Machine-readable output |
| `--dry-run` | Do not persist route mutations |

---

## 5. Route Storage

Routes persist to `references/reflex_routes.json`. If that file is missing or
unparseable, the built-in `DEFAULT_ROUTES` are used.

Because this file lives inside the distributed skill folder, **do not commit
experimental routes** — a stale route added while testing ships to every user who
copies the folder. Use `--cache-file` for scratch work.

---

## 6. Robustness Guarantees

- An invalid regex is rejected at `--add-route` time.
- An invalid regex that reaches the file by other means (hand-editing, a merge) is
  *skipped* during classification and reported in `invalid_routes`, never raised. A
  single bad pattern cannot break classification for every subsequent query.
- Duplicate patterns are rejected at add time.

---

## 7. Integration Pattern

```
query → reflex_router --json
      ├── tier=reflex   → run matched_command → done, no model call
      └── tier=reasoning → normal agent loop
```

Run `--verify` in CI. A route table that stops compiling is a silent capability loss:
every query quietly falls through to reasoning and the cost saving disappears with no
error surfaced.
