# Mastery () Offline Reference Runbook

## Overview
Mastery provides stage-specific context adapters that dynamically tune system prompts, context budgets, and tool access filters as agents transition across development lifecycle stages.

## Key Capabilities
1. **Stage-Specific Adapters**: Standardized adapter configurations for , , , and  ().
2. **Context Budgeting**: Prescribed token and byte budgets per stage to optimize context window space.
3. **Prompt Disclosure**: Extraction of raw system prompt snippets ().
4. **Tool Scope Filtering**: Tool recommendation matrices matched to lifecycle objectives.

## CLI Usage Guide
{
  "status": "SUCCESS",
  "stage": "build",
  "canonical_stage": "building",
  "context_budget": {
    "token_limit": 16000,
    "byte_limit": 65536,
    "priority_focus": "Minimal code edits, targeted helper logic, co-located test validation"
  },
  "allowed_tools": [
    "view_file",
    "replace_file_content",
    "run_command",
    "write_to_file"
  ],
  "focus_rules": [
    "Re-read every target file before modifying it.",
    "Follow minimal change principle—edit only what is necessary.",
    "Run build and test validation after every edit."
  ],
  "system_prompt": "[MASTERY ADAPTER: BUILDING STAGE] You are in the BUILDING stage. Focus on minimal, high-precision code implementation. Verify all edits using test runner CLI commands.",
  "dry_run": false
}
[MASTERY ADAPTER: PLANNING STAGE] You are in the PLANNING stage. Focus strictly on system design, requirement verification, and architectural layout. Avoid code edits until the implementation plan is fully established.
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
