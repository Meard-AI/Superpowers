#!/usr/bin/env python3
"""
cqc_executor.py - Close Quarters Combat (CQC) Sandbox Executor

Runs a command inside a declared perimeter directory, refuses commands whose static
analysis shows a perimeter escape, and diffs the watched filesystem afterwards to
report side-effects.

SCOPE HONESTY: this is a MISTAKE DETECTOR, not a security sandbox.
  - Static analysis is string analysis of a shell command and is defeated by
    variable expansion, command substitution, eval, or any interpreter.
  - The filesystem diff only covers --watch-dir roots (default: the perimeter's
    parent). Writes anywhere else are invisible, and the output says so.
By default the command is BLOCKED when static analysis finds an escape
(--warn-only downgrades that to a warning). Enforce real boundaries with an OS
sandbox: sandbox-exec (macOS), Landlock+seccomp or bubblewrap (Linux), or a container.
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List

try:
    from boundary_validator import analyze_command, snapshot_filesystem, detect_delta
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from boundary_validator import analyze_command, snapshot_filesystem, detect_delta


def execute_cqc(command: str, perimeter_dir: str, dry_run: bool,
                watch_dirs: List[str] = None, warn_only: bool = False,
                timeout: int = 300) -> Dict:
    """Execute a command within the perimeter and report boundary side-effects."""
    if not command:
        return {
            "status": "failed",
            "reason": "missing_command",
            "exit_code": 1,
            "stdout": "",
            "stderr": "Missing required command parameter",
            "boundary_violations": ["No command provided"],
        }

    perimeter_path = Path(perimeter_dir or os.getcwd()).expanduser()
    if not perimeter_path.exists():
        return {
            "status": "failed",
            "reason": "invalid_perimeter",
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Perimeter directory does not exist: {perimeter_dir}",
            "boundary_violations": [f"Invalid perimeter directory: {perimeter_dir}"],
        }

    perimeter_path = perimeter_path.resolve()
    abs_perimeter = str(perimeter_path)
    resolved_watch = [str(Path(w).expanduser().resolve()) for w in (watch_dirs or [])] \
        or [str(perimeter_path.parent)]

    analysis = analyze_command(command, abs_perimeter)
    static_violations = analysis["violations"]

    base = {
        "command": command,
        "perimeter_dir": abs_perimeter,
        "watch_scope": resolved_watch,
        "watch_scope_note": (
            "Filesystem side-effects are only detected inside watch_scope. "
            "Writes outside these roots are NOT monitored."
        ),
        "static_analysis": {
            "violations": static_violations,
            "dynamic_constructs": analysis["dynamic_constructs"],
            "undecidable": analysis["undecidable"],
            "note": analysis["note"],
        },
    }

    if dry_run:
        return {
            **base,
            "status": "failed" if static_violations else "passed",
            "reason": "static_violation" if static_violations else "dry_run_clean",
            "exit_code": 1 if static_violations else 0,
            "stdout": f"[DRY-RUN] Static analysis completed for perimeter: {abs_perimeter}",
            "stderr": "\n".join(static_violations),
            "boundary_violations": static_violations,
            "executed": False,
        }

    # Refuse to run a command already known to escape, unless explicitly waived.
    if static_violations and not warn_only:
        return {
            **base,
            "status": "blocked",
            "reason": "static_violation",
            "exit_code": 1,
            "stdout": "",
            "stderr": "Execution refused: static analysis found perimeter escape. "
                      "Re-run with --warn-only to override.",
            "boundary_violations": static_violations,
            "executed": False,
        }

    pre_snapshot = snapshot_filesystem(resolved_watch, abs_perimeter)

    try:
        proc = subprocess.run(
            command, shell=True, cwd=abs_perimeter,
            capture_output=True, text=True, timeout=timeout,
        )
        exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return {
            **base,
            "status": "failed",
            "reason": "timeout",
            "exit_code": 124,
            "stdout": "",
            "stderr": f"Command exceeded timeout of {timeout}s",
            "boundary_violations": static_violations,
            "executed": True,
        }
    except Exception as e:
        return {
            **base,
            "status": "failed",
            "reason": "subprocess_error",
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Subprocess execution error: {e}",
            "boundary_violations": static_violations,
            "executed": True,
        }

    post_snapshot = snapshot_filesystem(resolved_watch, abs_perimeter)
    dynamic_violations = detect_delta(pre_snapshot, post_snapshot)
    all_violations = static_violations + dynamic_violations

    if all_violations:
        status, reason = "violated", "boundary_violation"
    elif exit_code != 0:
        status, reason = "failed", "command_failed"
    else:
        status, reason = "passed", "clean"

    return {
        **base,
        "status": status,
        "reason": reason,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "boundary_violations": all_violations,
        "executed": True,
    }


def main():
    parser = argparse.ArgumentParser(
        description="CQC Sandbox Micro-Verification Executor & Boundary Validator"
    )
    parser.add_argument("--command", "--cmd", type=str, dest="command", default="",
                        help="Command string to execute within the micro-sandbox")
    parser.add_argument("--perimeter-dir", "--target-dir", type=str, dest="perimeter_dir",
                        default=os.getcwd(), help="Sandbox perimeter directory (default: CWD)")
    parser.add_argument("--watch-dir", action="append", dest="watch_dirs", default=None,
                        help="Extra root to monitor for side-effects (repeatable). "
                             "Default: the perimeter's parent directory")
    parser.add_argument("--warn-only", action="store_true",
                        help="Run the command even when static analysis finds an escape")
    parser.add_argument("--timeout", type=int, default=300, help="Command timeout in seconds (default: 300)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Static perimeter validation only; do not run the command")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args()

    result = execute_cqc(
        args.command, args.perimeter_dir, args.dry_run,
        watch_dirs=args.watch_dirs, warn_only=args.warn_only, timeout=args.timeout,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"[{result['status'].upper()}] reason={result['reason']} exit_code={result['exit_code']}")
        sa = result.get("static_analysis", {})
        if sa.get("undecidable"):
            print(f"  ! {sa['note']}")
        for v in result.get("boundary_violations", []):
            print(f"  - {v}")
        if result.get("stdout"):
            print(result["stdout"], end="" if result["stdout"].endswith("\n") else "\n")
        if result.get("stderr"):
            print(result["stderr"], file=sys.stderr,
                  end="" if result["stderr"].endswith("\n") else "\n")

    # Propagate a meaningful code: boundary problems are 2, command failure keeps
    # the child's own exit code, clean runs are 0.
    if result["status"] in ("blocked", "violated"):
        sys.exit(2)
    sys.exit(result["exit_code"])


if __name__ == "__main__":
    main()
