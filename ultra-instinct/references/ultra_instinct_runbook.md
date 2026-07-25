# Ultra Instinct Offline Runbook

## Overview
Ultra Instinct (UI) is the high-velocity compute routing engine for deterministic and recurring agent operations.

## CLI Quick Reference
- Evaluate query: python3 scripts/reflex_router.py --query 'check status' --json
- Add route: python3 scripts/reflex_router.py --add-route '(?i).*lint.*' --command 'flake8 .' --json
- Invalidate route: python3 scripts/reflex_router.py --invalidate '(?i).*lint.*' --json
- List routes: python3 scripts/reflex_router.py --list --json
