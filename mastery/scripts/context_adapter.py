#!/usr/bin/env python3
"""
context_adapter.py — Mastery: Stage-Specific Context Adapter Engine.

Emits the context budget, tool allowlist, focus rules, and system prompt for a
given lifecycle stage (plan | build | audit | format).

This engine is ADVISORY and stateless: it returns configuration for the calling
agent to apply to itself. It does not and cannot enforce a token budget or
restrict a tool — only the host runtime can do that.

Tool names differ per host, so they are emitted through a vocabulary mapping.
Default is the Agent Skills standard vocabulary (Read/Write/Edit/Bash/Grep/Glob);
--tool-vocabulary antigravity emits the legacy Antigravity/Windsurf names.
"""

import sys
import json
import argparse

STAGE_MAPPINGS = {
    "plan": "planning",
    "planning": "planning",
    "build": "building",
    "building": "building",
    "audit": "auditing",
    "auditing": "auditing",
    "format": "refactoring",
    "refactoring": "refactoring",
}

# Canonical capability -> per-host tool name.
TOOL_VOCABULARIES = {
    "standard": {
        "read": "Read", "write": "Write", "edit": "Edit",
        "run": "Bash", "grep": "Grep", "glob": "Glob",
    },
    "antigravity": {
        "read": "view_file", "write": "write_to_file", "edit": "replace_file_content",
        "run": "run_command", "grep": "grep_search", "glob": "find_by_name",
    },
}

ADAPTER_CONFIGS = {
    "planning": {
        "canonical_stage": "planning",
        "stage_name": "Plan & Scope Architecture",
        "context_budget": {
            "token_limit": 8000,
            "byte_limit": 32768,
            "priority_focus": "Architecture specifications, layout definitions, interface contracts",
        },
        "capabilities": ["read", "grep", "glob"],
        "focus_rules": [
            "Validate upstream analysis and verify layout requirements before code changes.",
            "Formulate a step-by-step implementation plan.",
            "Keep context lightweight during initial discovery.",
        ],
        "system_prompt": "[MASTERY ADAPTER: PLANNING STAGE] You are in the PLANNING stage. "
                         "Focus strictly on system design, requirement verification, and architectural "
                         "layout. Avoid code edits until the implementation plan is fully established.",
    },
    "building": {
        "canonical_stage": "building",
        "stage_name": "Build & Implement Features",
        "context_budget": {
            "token_limit": 16000,
            "byte_limit": 65536,
            "priority_focus": "Minimal code edits, targeted helper logic, co-located test validation",
        },
        "capabilities": ["read", "edit", "write", "run"],
        "focus_rules": [
            "Re-read every target file before modifying it.",
            "Follow the minimal change principle — edit only what is necessary.",
            "Run build and test validation after every edit.",
        ],
        "system_prompt": "[MASTERY ADAPTER: BUILDING STAGE] You are in the BUILDING stage. "
                         "Focus on minimal, high-precision code implementation. Verify all edits "
                         "using test runner CLI commands.",
    },
    "auditing": {
        "canonical_stage": "auditing",
        "stage_name": "Audit & Quality Assurance",
        "context_budget": {
            "token_limit": 12000,
            "byte_limit": 49152,
            "priority_focus": "Edge cases, boundary enforcement, CLI argument compliance, regression testing",
        },
        "capabilities": ["read", "run", "grep"],
        "focus_rules": [
            "Run the full test harness and verify CLI --help outputs.",
            "Test error handling paths and boundary conditions.",
            "Ensure no dummy logic or hardcoded verification cheats exist.",
        ],
        "system_prompt": "[MASTERY ADAPTER: AUDITING STAGE] You are in the AUDITING stage. "
                         "Inspect implementations for defects, boundary violations, and edge-case "
                         "failures. Do not add new features.",
    },
    "refactoring": {
        "canonical_stage": "refactoring",
        "stage_name": "Refactor, Format & Handoff",
        "context_budget": {
            "token_limit": 8000,
            "byte_limit": 32768,
            "priority_focus": "Offline reference runbooks, clean code layout, handoff report compilation",
        },
        "capabilities": ["read", "edit", "run"],
        "focus_rules": [
            "Ensure all helper scripts remain executable from the skill's scripts/ directory.",
            "Verify offline reference runbooks cover operational workflows.",
            "Compile the handoff report (see the Handoff Report Template in the skill guide).",
        ],
        "system_prompt": "[MASTERY ADAPTER: REFACTORING STAGE] You are in the REFACTORING & HANDOFF "
                         "stage. Finalize documentation, synchronize script integration, and compile "
                         "the final handoff report.",
    },
}


def resolve_tools(capabilities, vocabulary: str):
    vocab = TOOL_VOCABULARIES[vocabulary]
    return [vocab[c] for c in capabilities if c in vocab]


def main():
    parser = argparse.ArgumentParser(description="Mastery Stage-Specific Context Adapter Engine")
    parser.add_argument("--stage", "--load-adapter", dest="stage", type=str,
                        help="Target workflow stage (plan|build|audit|format)")
    parser.add_argument("--tool-vocabulary", choices=sorted(TOOL_VOCABULARIES.keys()),
                        default="standard",
                        help="Tool-name vocabulary for allowed_tools (default: standard)")
    parser.add_argument("--list", "--list-stages", action="store_true", dest="list_stages",
                        help="List all registered context stage adapters")
    parser.add_argument("--get-prompt", action="store_true",
                        help="Output only the raw system prompt string for the stage")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON format")

    args = parser.parse_args()

    if args.list_stages:
        res = {
            "status": "SUCCESS",
            "stages": list(ADAPTER_CONFIGS.keys()),
            "mappings": STAGE_MAPPINGS,
            "tool_vocabularies": sorted(TOOL_VOCABULARIES.keys()),
        }
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("Available Context Stage Adapters:")
            for k, v in ADAPTER_CONFIGS.items():
                print(f"  - [{k}] {v['stage_name']} "
                      f"(token limit: {v['context_budget']['token_limit']})")
        sys.exit(0)

    if not args.stage:
        parser.print_help()
        sys.exit(0)

    stage_key = STAGE_MAPPINGS.get(args.stage.lower().strip())
    if not stage_key:
        err = {"status": "ERROR",
               "error": f"Unknown stage adapter '{args.stage}'. "
                        f"Allowed: {', '.join(sorted(STAGE_MAPPINGS))}."}
        if args.json:
            print(json.dumps(err, indent=2))
        else:
            print(f"Error: {err['error']}", file=sys.stderr)
        sys.exit(1)

    adapter = ADAPTER_CONFIGS[stage_key]

    if args.get_prompt:
        if args.json:
            print(json.dumps({"status": "SUCCESS", "stage": stage_key,
                              "system_prompt": adapter["system_prompt"]}, indent=2))
        else:
            print(adapter["system_prompt"])
        sys.exit(0)

    allowed_tools = resolve_tools(adapter["capabilities"], args.tool_vocabulary)
    res = {
        "status": "SUCCESS",
        "stage": args.stage,
        "canonical_stage": adapter["canonical_stage"],
        "stage_name": adapter["stage_name"],
        "context_budget": adapter["context_budget"],
        "capabilities": adapter["capabilities"],
        "tool_vocabulary": args.tool_vocabulary,
        "allowed_tools": allowed_tools,
        "focus_rules": adapter["focus_rules"],
        "system_prompt": adapter["system_prompt"],
        "enforcement": "advisory — the calling agent must apply this itself; "
                       "this tool cannot restrict tools or enforce a token budget",
    }

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"[MASTERY ADAPTER] {adapter['canonical_stage'].upper()} ({adapter['stage_name']})")
        print(f"Token budget : {adapter['context_budget']['token_limit']}")
        print(f"Allowed tools: {', '.join(allowed_tools)}  [{args.tool_vocabulary}]")
        print("Focus rules:")
        for rule in adapter["focus_rules"]:
            print(f"  - {rule}")
        print(f"Note: {res['enforcement']}")

    sys.exit(0)


if __name__ == "__main__":
    main()
