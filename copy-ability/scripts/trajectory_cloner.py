#!/usr/bin/env python3
"""
trajectory_cloner.py — Copy Ability: Trajectory Ingestion & Skill Generator.

Parses an execution transcript into the commands that were actually run, and emits
a SKILL.md playbook from them.

Safety properties:
  - NEVER overwrites an existing file without --force.
  - The description is emitted as a JSON-quoted scalar, so it cannot inject
    additional YAML frontmatter keys.
  - --output-dir can be constrained with --allowed-root.
"""

import sys
import os
import json
import argparse
import re
import select
from pathlib import Path
from typing import Any, Dict, List, Optional


def read_available_stdin(timeout: float = 0.2) -> str:
    """Read piped stdin without ever blocking on a writer that never comes.

    Agent harnesses routinely hand a script an open stdin pipe that nothing will
    write to. isatty() is False there, so a bare sys.stdin.read() hangs forever —
    the script never returns and the agent stalls. Poll for readability first.

    select() on a file object is POSIX-only; on Windows this degrades to "no
    piped input", which is far better than an unkillable hang.
    """
    try:
        if sys.stdin is None or sys.stdin.closed or sys.stdin.isatty():
            return ""
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if not ready:
            return ""
        return sys.stdin.read()
    except Exception:
        return ""

COMMAND_PREFIXES = ("$ ", "> ", "CMD:", "RUN:", "Action:", "% ")
COMMAND_MARKERS = ("tool_call", "Action:")
STRIP_PREFIX_RE = re.compile(r"^(?:[$>%]\s*|(?:RUN|CMD|Action):\s*)")

# Transcript noise that is never a real command.
NOISE_RE = re.compile(r"^(?:\.{3}|-{3,}|={3,}|\s*$)")


def is_command_line(stripped: str) -> bool:
    if NOISE_RE.match(stripped):
        return False
    if stripped.startswith(COMMAND_PREFIXES):
        return True
    return any(marker in stripped for marker in COMMAND_MARKERS)


def parse_log_content(content: str, max_steps: int = 100) -> Dict[str, Any]:
    """Extract executed commands from a transcript.

    Each command is ONE step. Output lines that follow a command are recorded as
    that step's output, never concatenated onto the command itself — the previous
    behaviour joined every following line into the command string, producing a
    single unusable mega-step.
    """
    steps: List[Dict[str, Any]] = []
    preamble: List[str] = []
    truncated = False

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if is_command_line(stripped):
            if len(steps) >= max_steps:
                truncated = True
                continue
            command = STRIP_PREFIX_RE.sub("", stripped).strip()
            if command:
                steps.append({"command": command, "output_lines": 0})
        elif steps:
            steps[-1]["output_lines"] += 1
        else:
            preamble.append(stripped)

    # Collapse immediately-repeated commands (retry loops in transcripts).
    deduped: List[Dict[str, Any]] = []
    for step in steps:
        if deduped and deduped[-1]["command"] == step["command"]:
            deduped[-1]["output_lines"] += step["output_lines"]
            deduped[-1]["repeats"] = deduped[-1].get("repeats", 1) + 1
        else:
            deduped.append(step)

    return {
        "steps": deduped,
        "preamble_lines": len(preamble),
        "truncated": truncated,
        "detected_commands": len(steps),
    }


def fence_for(text: str) -> str:
    """Pick a fence long enough that the content cannot break out of it."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def generate_skill_md(skill_name: str, steps: List[Dict[str, Any]],
                      description: Optional[str] = None) -> str:
    desc = description or (
        f"Auto-generated skill cloned from an execution trajectory for '{skill_name}'."
    )
    # json.dumps yields a double-quoted, fully escaped scalar. YAML accepts it, and
    # a newline or ':' in the description can no longer create new frontmatter keys.
    desc_yaml = json.dumps(desc)

    if steps:
        body_lines = []
        for idx, step in enumerate(steps, 1):
            suffix = f"  (repeated {step['repeats']}x)" if step.get("repeats") else ""
            body_lines.append(f"# Step {idx}{suffix}")
            body_lines.append(step["command"])
        block = "\n".join(body_lines)
        fence = fence_for(block)
        steps_section = f"{fence}bash\n{block}\n{fence}"
    else:
        steps_section = "_No commands were detected in the supplied transcript._"

    title = skill_name.replace("-", " ").title()
    return f"""---
name: {skill_name}
description: {desc_yaml}
allowed-tools:
  - Bash
  - Read
  - Write
metadata:
  version: 1.0.0
  author: Copy Ability Trajectory Cloner
---

# {title} Playbook

Cloned from an observed execution trajectory. Review every command before running it —
these were extracted from a transcript and have not been validated.

## Triggers & Scope
- Triggered when executing workflow routines matching the `{skill_name}` pattern.

## Workflow Instructions

{steps_section}

## Verification & Error Handling
- Validate execution output after each step.
- If a command fails, inspect the error and consult the `heat-mode` skill for
  anti-stall recovery recommendations.
"""


def main():
    parser = argparse.ArgumentParser(description="Copy Ability Trajectory Cloner & SKILL.md Generator")
    parser.add_argument("--log", "--input-log", dest="input_log", type=str,
                        help="Path to execution log or transcript file")
    parser.add_argument("--name", "--skill-name", dest="skill_name", type=str, default="cloned-skill",
                        help="Name slug for generated skill")
    parser.add_argument("--output-dir", type=str, help="Destination directory for generated skill")
    parser.add_argument("--allowed-root", type=str,
                        help="Constrain --output-dir to live under this root")
    parser.add_argument("--description", type=str, help="Description for generated SKILL.md")
    parser.add_argument("--max-steps", type=int, default=100, help="Maximum steps to extract (default: 100)")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing SKILL.md")
    parser.add_argument("--json", action="store_true", help="Output result in clean JSON format")
    parser.add_argument("--dry-run", action="store_true", help="Simulate generation without writing files")

    args = parser.parse_args()

    def fail(message: str, code: int = 1):
        err = {"status": "ERROR", "error": message}
        if args.json:
            print(json.dumps(err, indent=2))
        else:
            print(f"Error: {message}", file=sys.stderr)
        sys.exit(code)

    raw_text = None
    if args.input_log:
        log_path = Path(args.input_log).expanduser()
        if not log_path.is_file():
            fail(f"Input log file '{args.input_log}' not found")
        try:
            raw_text = log_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            fail(f"Failed to read log file: {e}")
    else:
        raw_text = read_available_stdin()

    if not raw_text or not raw_text.strip():
        fail("No input log provided via --log / --input-log or stdin")

    parsed = parse_log_content(raw_text, max_steps=args.max_steps)
    steps = parsed["steps"]

    skill_slug = re.sub(r"-+", "-", re.sub(r"[^a-zA-Z0-9_-]", "-", args.skill_name.strip().lower())).strip("-")
    if not skill_slug:
        fail("Skill name reduced to an empty slug; supply a name with alphanumeric characters")

    skill_content = generate_skill_md(skill_slug, steps, args.description)

    output_dir = Path(args.output_dir).expanduser() if args.output_dir \
        else Path.cwd() / ".agents" / "skills" / skill_slug

    if args.allowed_root:
        root = Path(args.allowed_root).expanduser().resolve()
        try:
            output_dir.resolve().relative_to(root)
        except ValueError:
            fail(f"Output directory '{output_dir}' is outside allowed root '{root}'")

    target_skill_file = output_dir / "SKILL.md"

    # A symlink at the destination redirects the write to wherever it points, so
    # --force would clobber an arbitrary file outside --output-dir (and outside
    # --allowed-root, since the directory itself is allowed). Never follow it.
    if target_skill_file.is_symlink():
        fail(f"Refusing to write through symlink '{target_skill_file}' -> "
             f"'{os.readlink(target_skill_file)}'. Remove the symlink first.", code=4)

    if target_skill_file.exists() and not args.force and not args.dry_run:
        fail(f"Refusing to overwrite existing file '{target_skill_file}'. Pass --force to replace it.", code=3)

    # Re-check the fully resolved destination: a symlinked parent directory can
    # also move the real write target outside the permitted root.
    if args.allowed_root and not args.dry_run:
        root = Path(args.allowed_root).expanduser().resolve()
        resolved_parent = output_dir.resolve() if output_dir.exists() else output_dir.parent.resolve()
        try:
            resolved_parent.relative_to(root)
        except ValueError:
            fail(f"Resolved output path '{resolved_parent}' escapes allowed root '{root}'")

    if not args.dry_run:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            target_skill_file.write_text(skill_content, encoding="utf-8")
        except Exception as e:
            fail(f"Failed to write '{target_skill_file}': {e}")

    res = {
        "status": "SUCCESS",
        "skill_name": skill_slug,
        "extracted_steps_count": len(steps),
        "detected_commands": parsed["detected_commands"],
        "steps_truncated": parsed["truncated"],
        "preamble_lines_ignored": parsed["preamble_lines"],
        "target_file": str(target_skill_file),
        "overwrote_existing": target_skill_file.exists() and args.force,
        "dry_run": args.dry_run,
        "extracted_steps": [s["command"] for s in steps],
    }
    if not steps:
        res["warning"] = "No commands detected. Transcript lines must start with " \
                         "'$', '>', '%', 'CMD:', 'RUN:', or 'Action:'."

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"[SUCCESS] Cloned into skill '{skill_slug}' (dry-run={args.dry_run})")
        print(f"Destination: {target_skill_file}")
        print(f"Extracted {len(steps)} step(s).")
        if res.get("warning"):
            print(f"Warning: {res['warning']}")
    sys.exit(0)


if __name__ == "__main__":
    main()
