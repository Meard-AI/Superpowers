---
name: copy-ability
description: Trajectory ingestion and skill generator engine. Parses raw execution logs, session transcripts, or CLI turn histories to extract workflow steps and output auto-generated custom Antigravity SKILL.md playbooks.
allowed-tools:
  - run_command
  - view_file
  - write_to_file
metadata:
  version: 1.0.0
  author: Agent Superpowers Team
  category: automation
---

# Copy Ability (copy-ability) Skill Playbook

Parse raw execution transcripts or CLI logs to auto-generate production-ready custom Antigravity SKILL.md playbooks.

## Triggers & Scope
Activate copy-ability when:
1. User provides execution logs or CLI transcripts to package into a skill.
2. An observed successful workflow trajectory needs to be cloned into a reusable skill playbook.

## Protocol
Run trajectory_cloner.py to parse execution log and write generated SKILL.md:

  python3 scripts/trajectory_cloner.py --log '<log_file>' --name '<skill_name>' --output-dir '<dir>' --json
