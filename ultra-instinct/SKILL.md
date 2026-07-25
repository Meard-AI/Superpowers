---
name: ultra-instinct
description: Dynamic compute routing and deterministic reflex caching engine. Evaluates queries against pre-computed reflex routes to execute low-complexity or routine operations with zero LLM overhead.
allowed-tools:
  - run_command
  - view_file
  - write_to_file
metadata:
  version: 1.0.0
  author: Agent Superpowers Team
  category: compute-optimization
---

# Ultra Instinct (ultra-instinct) Skill Playbook

Bypass heavy multi-step LLM reasoning loops for routine or deterministic operations by dynamically routing queries through a pre-computed reflex dictionary.

## Triggers & Activation Scenarios
Activate ultra-instinct when:
1. Receiving routine subtasks (e.g. repository status checks, file linting, test execution).
2. Operating under low-latency or low-overhead constraints where zero LLM reasoning latency is required.

## Protocol
Before running multi-step reasoning, evaluate candidate query via reflex_router.py:

  python3 scripts/reflex_router.py --query '<query>' --json

- If tier == 'reflex': execute matched_command directly.
- If tier == 'reasoning': proceed with standard deep reasoning loop.
