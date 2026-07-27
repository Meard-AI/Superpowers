# Ultra Instinct — Offline Runbook

Condensed operational steps. For rationale and route-authoring theory see
[`ultra_instinct_guide.md`](./ultra_instinct_guide.md).

## Standard loop
1. **Classify** the incoming query:
   ```bash
   python3 ./scripts/reflex_router.py --query '<query>' --json
   ```
2. **Branch** on `tier`:
   - `reflex` → execute `matched_command` verbatim, return its output.
   - `reasoning` → fall through to the normal reasoning loop.
3. Never execute when `matched_command` is `null`. The router will not emit a
   `reflex` verdict without a command, but check anyway.

## Route maintenance
| Task | Command |
|---|---|
| List routes | `python3 ./scripts/reflex_router.py --list --json` |
| Health check | `python3 ./scripts/reflex_router.py --verify --json` |
| Add route | `python3 ./scripts/reflex_router.py --add-route '<regex>' --command '<cmd>' --json` |
| Remove route | `python3 ./scripts/reflex_router.py --invalidate '<regex>' --json` |
| Preview only | append `--dry-run` |

## Exit codes
| Code | Meaning |
|---|---|
| 0 | Classification or route operation succeeded |
| 1 | `--verify` found unusable routes, or an add/remove was rejected |

## Failure modes
- **`--verify` reports `does not compile`** — a hand-edited route file contains an
  invalid regex. Classification skips it, but repair or `--invalidate` it.
- **Everything returns `reasoning`** — check `--list`. An empty or corrupt route file
  falls back to built-in defaults; a file that parsed but has no matching anchors will
  match nothing.
- **A routine query is not matching** — patterns are anchored `^\s*...\s*$` by design.
  Add a route for the exact phrasing rather than loosening an existing pattern.
