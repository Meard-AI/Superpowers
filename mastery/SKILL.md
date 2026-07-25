---
name: mastery
description: Stage-specific context adapter engine. Dynamically reconfigures system prompts, context budgets, allowed tool scopes, and focus rules based on active lifecycle stage (plan, build, audit, format).
allowed-tools:
  - run_command
  - view_file
  - write_to_file
metadata:
  version: 1.0.0
  author: Agent Superpowers Team
  category: context-optimization
---

# Mastery () Skill Playbook

Dynamically manage context budget allocation, system prompt directives, and progressive disclosure across software development lifecycle stages (, , , ).

## Triggers & Scope
Activate  when:
1. Transitioning between development lifecycle phases (e.g. from architectural planning to active building, or from building to auditing).
2. Operating under strict context window budgets where unused tool directives must be pruned.
3. Aligning agent execution persona with stage-specific constraints.

## Context Adapter Protocol
To load context guidance and budget limits for a specific stage:



To extract the raw system prompt adapter for a stage:



To list all registered stage adapters:

{
  "status": "SUCCESS",
  "stages": [
    "planning",
    "building",
    "auditing",
    "refactoring"
  ],
  "mappings": {
    "plan": "planning",
    "planning": "planning",
    "build": "building",
    "building": "building",
    "audit": "auditing",
    "auditing": "auditing",
    "format": "refactoring",
    "refactoring": "refactoring"
  }
}

## Stage Lifecycle Matrix

| Stage | Canonical Slug | Token Budget | Byte Budget | Priority Focus |
|---|---|---|---|---|
|  |  | 8,000 | 32 KB | Architecture, specifications, layout discovery |
|  |  | 16,000 | 64 KB | Minimal code edits, unit test validation |
|  |  | 12,000 | 48 KB | Quality assurance, boundary validation, CLI compliance |
|  |  | 8,000 | 32 KB | Runbooks, code cleanup, handoff compilation |

## Progressive Context Disclosure Rules
- **Planning**: Restrict tool access to view and search tools (, , ). Keep working memory light.
- **Building**: Enable code editing tools (, , ). Maintain strict minimal change focus.
- **Auditing**: Re-check boundary safety and execute test harnesses. Focus on detecting defects and hardcoding violations.
- **Refactoring**: Finalize documentation and offline runbooks. Compile the 5-component handoff report.
