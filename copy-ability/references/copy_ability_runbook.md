# Copy Ability Offline Runbook

## Overview
Copy Ability ingests unstructured tool call logs and CLI transcripts, converting them into valid Antigravity SKILL.md playbooks.

## CLI Quick Reference
- Clone trajectory: python3 scripts/trajectory_cloner.py --log session.log --name my-cloned-skill --json
- Dry run generation: python3 scripts/trajectory_cloner.py --log session.log --dry-run --json
