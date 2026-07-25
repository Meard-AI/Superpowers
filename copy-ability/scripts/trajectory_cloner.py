#!/usr/bin/env python3
"""
trajectory_cloner.py — Copy Ability: Trajectory Ingestion & Skill Generator.
Parses execution logs or transcripts to auto-generate production-ready custom Antigravity SKILL.md playbooks.
"""

import sys
import os
import json
import argparse
import re
from pathlib import Path


def parse_log_content(content: str) -> list:
    """Extract commands, tool calls, and operational steps from transcript content."""
    lines = content.splitlines()
    steps = []
    current_step = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("$") or stripped.startswith(">") or stripped.startswith("CMD:") or stripped.startswith("RUN:") or "tool_call" in stripped or "Action:" in stripped:
            if current_step:
                steps.append(" ".join(current_step))
                current_step = []
            cmd_part = re.sub(r"^[$\>]\s*", "", stripped)
            cmd_part = re.sub(r"^(RUN:|CMD:|Action:)\s*", "", cmd_part)
            current_step.append(cmd_part)
        else:
            if current_step:
                current_step.append(stripped)

    if current_step:
        steps.append(" ".join(current_step))

    if not steps:
        steps = [l.strip() for l in lines if l.strip()][:15]

    return steps


def generate_skill_md(skill_name: str, steps: list, description: str = None) -> str:
    desc = description or f"Auto-generated custom skill cloned from execution trajectory log for '{skill_name}'."
    steps_formatted = "\n".join([f"{idx + 1}. Execute step: `{step}`" for idx, step in enumerate(steps)])

    content = f"""---
name: {skill_name}
description: {desc}
allowed-tools:
  - run_command
  - view_file
  - write_to_file
metadata:
  version: 1.0.0
  author: Copy Ability Trajectory Cloner
---

# {skill_name.replace('-', ' ').title()} Playbook

This custom Antigravity skill was cloned from an observed execution trajectory.

## Triggers & Scope
- Triggered when executing workflow routines matching the `{skill_name}` pattern.

## Workflow Instructions

{steps_formatted}

## Verification & Error Handling
- Validate execution output after each step.
- If any command fails, inspect error logs and execute anti-stall fallback via `anti_stall.py`.
"""
    return content


def main():
    parser = argparse.ArgumentParser(description="Copy Ability Trajectory Cloner & SKILL.md Generator")
    parser.add_argument("--log", "--input-log", dest="input_log", type=str, help="Path to execution log or transcript file")
    parser.add_argument("--name", "--skill-name", dest="skill_name", type=str, default="cloned-skill", help="Name slug for generated skill")
    parser.add_argument("--output-dir", type=str, help="Destination directory for generated skill")
    parser.add_argument("--description", type=str, help="Description for generated SKILL.md")
    parser.add_argument("--json", action="store_true", help="Output result in clean JSON format")
    parser.add_argument("--dry-run", action="store_true", help="Simulate generation without writing files to disk")

    args = parser.parse_args()

    raw_text = None
    if args.input_log:
        log_path = Path(args.input_log)
        if not log_path.exists():
            err = {"status": "ERROR", "error": f"Input log file '{args.input_log}' not found"}
            if args.json:
                print(json.dumps(err))
            else:
                print(f"Error: {err['error']}", file=sys.stderr)
            sys.exit(1)
        try:
            raw_text = log_path.read_text(encoding="utf-8")
        except Exception as e:
            err = {"status": "ERROR", "error": f"Failed to read log file: {str(e)}"}
            if args.json:
                print(json.dumps(err))
            else:
                print(f"Error: {err['error']}", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty():
        raw_text = sys.stdin.read()

    if not raw_text:
        err = {"status": "ERROR", "error": "No input log provided via --log / --input-log or stdin"}
        if args.json:
            print(json.dumps(err))
        else:
            print(f"Error: {err['error']}", file=sys.stderr)
            parser.print_help()
        sys.exit(1)

    steps = parse_log_content(raw_text)
    skill_slug = re.sub(r'[^a-zA-Z0-9_-]', '-', args.skill_name.strip().lower())
    skill_content = generate_skill_md(skill_slug, steps, args.description)

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path.cwd() / ".agents" / "skills" / skill_slug

    target_skill_file = output_dir / "SKILL.md"

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        target_skill_file.write_text(skill_content, encoding="utf-8")

    res = {
        "status": "SUCCESS",
        "skill_name": skill_slug,
        "extracted_steps_count": len(steps),
        "target_file": str(target_skill_file),
        "dry_run": args.dry_run,
        "extracted_steps": steps
    }

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"[SUCCESS] Trajectory cloned into skill '{skill_slug}' (dry-run={args.dry_run})")
        print(f"Destination: {target_skill_file}")
        print(f"Extracted {len(steps)} steps.")

    sys.exit(0)


if __name__ == "__main__":
    main()
