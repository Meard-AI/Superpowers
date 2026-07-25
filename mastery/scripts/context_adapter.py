#!/usr/bin/env python3
"""
context_adapter.py — Mastery: Stage-Specific Context Adapter Engine.
Manages context window budgets, dynamic system prompts, and tool filters across workflow stages.
"""

import sys
import os
import json
import argparse
from pathlib import Path

STAGE_MAPPINGS = {
    "plan": "planning",
    "planning": "planning",
    "build": "building",
    "building": "building",
    "audit": "auditing",
    "auditing": "auditing",
    "format": "refactoring",
    "refactoring": "refactoring"
}

ADAPTER_CONFIGS = {
    "planning": {
        "canonical_stage": "planning",
        "stage_name": "Plan & Scope Architecture",
        "context_budget": {
            "token_limit": 8000,
            "byte_limit": 32768,
            "priority_focus": "Architecture specifications, layout definitions, interface contracts"
        },
        "allowed_tools": ["view_file", "grep_search", "find_by_name"],
        "focus_rules": [
            "Validate upstream analysis and verify layout requirements before code changes.",
            "Formulate step-by-step implementation plan.",
            "Keep context lightweight during initial discovery."
        ],
        "system_prompt": "[MASTERY ADAPTER: PLANNING STAGE] You are in the PLANNING stage. Focus strictly on system design, requirement verification, and architectural layout. Avoid code edits until the implementation plan is fully established."
    },
    "building": {
        "canonical_stage": "building",
        "stage_name": "Build & Implement Features",
        "context_budget": {
            "token_limit": 16000,
            "byte_limit": 65536,
            "priority_focus": "Minimal code edits, targeted helper logic, co-located test validation"
        },
        "allowed_tools": ["view_file", "replace_file_content", "run_command", "write_to_file"],
        "focus_rules": [
            "Re-read every target file before modifying it.",
            "Follow minimal change principle—edit only what is necessary.",
            "Run build and test validation after every edit."
        ],
        "system_prompt": "[MASTERY ADAPTER: BUILDING STAGE] You are in the BUILDING stage. Focus on minimal, high-precision code implementation. Verify all edits using test runner CLI commands."
    },
    "auditing": {
        "canonical_stage": "auditing",
        "stage_name": "Audit & Quality Assurance",
        "context_budget": {
            "token_limit": 12000,
            "byte_limit": 49152,
            "priority_focus": "Edge cases, boundary enforcement, CLI argument compliance, regression testing"
        },
        "allowed_tools": ["view_file", "run_command", "grep_search"],
        "focus_rules": [
            "Run full unit test harness and verify CLI --help outputs.",
            "Test error handling paths and boundary conditions.",
            "Ensure no dummy logic or hardcoded verification cheats exist."
        ],
        "system_prompt": "[MASTERY ADAPTER: AUDITING STAGE] You are in the AUDITING stage. Inspect implementations for defects, boundary violations, and edge-case failures. Do not add new features."
    },
    "refactoring": {
        "canonical_stage": "refactoring",
        "stage_name": "Refactor, Format & Handoff",
        "context_budget": {
            "token_limit": 8000,
            "byte_limit": 32768,
            "priority_focus": "Offline reference runbooks, clean code layout, handoff report compilation"
        },
        "allowed_tools": ["view_file", "replace_file_content", "run_command"],
        "focus_rules": [
            "Ensure all helper scripts are executable at top-level scripts/ directory.",
            "Verify offline reference runbooks cover operational workflows.",
            "Compile complete 5-component handoff.md report."
        ],
        "system_prompt": "[MASTERY ADAPTER: REFACTORING STAGE] You are in the REFACTORING & HANDOFF stage. Finalize documentation, synchronize top-level script integration, and compile the final handoff report."
    }
}


def main():
    parser = argparse.ArgumentParser(description="Mastery Stage-Specific Context Adapter Engine")
    parser.add_argument("--stage", type=str, help="Target workflow stage (plan|build|audit|format)")
    parser.add_argument("--load-adapter", type=str, help="Load stage adapter by name")
    parser.add_argument("--list", "--list-stages", action="store_true", help="List all registered context stage adapters")
    parser.add_argument("--get-prompt", action="store_true", help="Output raw system prompt string for active stage")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON format")
    parser.add_argument("--dry-run", action="store_true", help="Preview stage adapter loading without applying state")

    args = parser.parse_args()

    if args.list:
        res = {
            "status": "SUCCESS",
            "stages": list(ADAPTER_CONFIGS.keys()),
            "mappings": STAGE_MAPPINGS
        }
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("Available Context Stage Adapters:")
            for k, v in ADAPTER_CONFIGS.items():
                print(f"  - [{k}] {v['stage_name']} (token limit: {v['context_budget']['token_limit']})")
        sys.exit(0)

    target_stage_raw = args.stage or args.load_adapter
    if not target_stage_raw:
        parser.print_help()
        sys.exit(0)

    stage_key = STAGE_MAPPINGS.get(target_stage_raw.lower().strip())
    if not stage_key or stage_key not in ADAPTER_CONFIGS:
        err = {"status": "ERROR", "error": f"Unknown stage adapter '{target_stage_raw}'. Allowed stages: plan, build, audit, format."}
        if args.json:
            print(json.dumps(err))
        else:
            print(f"Error: {err['error']}", file=sys.stderr)
        sys.exit(1)

    adapter = ADAPTER_CONFIGS[stage_key]

    if args.get_prompt:
        print(adapter["system_prompt"])
        sys.exit(0)

    res = {
        "status": "SUCCESS",
        "stage": target_stage_raw,
        "canonical_stage": adapter["canonical_stage"],
        "context_budget": adapter["context_budget"],
        "allowed_tools": adapter["allowed_tools"],
        "focus_rules": adapter["focus_rules"],
        "system_prompt": adapter["system_prompt"],
        "dry_run": args.dry_run
    }

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"[MASTERY ADAPTER LOADED] Stage: {adapter['canonical_stage'].upper()} ({adapter['stage_name']})")
        print(f"Context Token Budget: {adapter['context_budget']['token_limit']} tokens")
        print(f"Allowed Tools: {', '.join(adapter['allowed_tools'])}")
        print(f"System Prompt Preview: {adapter['system_prompt'][:100]}...")

    sys.exit(0)


if __name__ == "__main__":
    main()
