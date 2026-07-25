#!/usr/bin/env python3
"""
cqc_executor.py - Close Quarters Combat (CQC) Sandbox Executor

Runs micro-verification commands within an exact execution perimeter, inspects exit codes,
and reports boundary violations or side-effects outside the target perimeter directory.
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path

try:
    from boundary_validator import inspect_command_bounds, snapshot_filesystem, detect_delta
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from boundary_validator import inspect_command_bounds, snapshot_filesystem, detect_delta


def execute_cqc(command: str, perimeter_dir: str, dry_run: bool) -> dict:
    """
    Executes a command within the specified sandbox perimeter and checks for side-effects.
    """
    if not command:
        return {
            "status": "failed",
            "exit_code": 1,
            "stdout": "",
            "stderr": "Missing required command parameter",
            "boundary_violations": ["No command provided"]
        }

    perimeter_path = Path(perimeter_dir or os.getcwd()).resolve()
    
    if not perimeter_path.exists():
        return {
            "status": "failed",
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Pre-condition failed: Perimeter directory does not exist: {perimeter_dir}",
            "boundary_violations": [f"Invalid perimeter directory: {perimeter_dir}"]
        }

    abs_perimeter = str(perimeter_path)
    parent_watch_dir = str(perimeter_path.parent)

    static_violations = inspect_command_bounds(command, abs_perimeter)

    if dry_run:
        status = "failed" if static_violations else "passed"
        exit_code = 1 if static_violations else 0
        return {
            "status": status,
            "exit_code": exit_code,
            "stdout": f"[DRY-RUN] Command static analysis completed for perimeter: {abs_perimeter}",
            "stderr": "\n".join(static_violations) if static_violations else "",
            "boundary_violations": static_violations
        }

    pre_snapshot = snapshot_filesystem(parent_watch_dir, abs_perimeter)

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=abs_perimeter,
            capture_output=True,
            text=True
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except Exception as e:
        return {
            "status": "failed",
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Subprocess execution error: {str(e)}",
            "boundary_violations": static_violations
        }

    post_snapshot = snapshot_filesystem(parent_watch_dir, abs_perimeter)
    dynamic_violations = detect_delta(pre_snapshot, post_snapshot)

    all_violations = list(set(static_violations + dynamic_violations))
    passed = (exit_code == 0) and (len(all_violations) == 0)
    status = "passed" if passed else "failed"

    return {
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "boundary_violations": all_violations
    }


def main():
    parser = argparse.ArgumentParser(
        description="CQC Sandbox Micro-Verification Executor & Boundary Validator"
    )
    parser.add_argument(
        "--command", "--cmd",
        type=str,
        dest="command",
        default="",
        help="Command string to execute within the micro-sandbox"
    )
    parser.add_argument(
        "--perimeter-dir", "--target-dir",
        type=str,
        dest="perimeter_dir",
        default=os.getcwd(),
        help="Sandbox perimeter directory path (default: CWD)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution and perform static perimeter validation without running command"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON (default output format is JSON)"
    )

    args = parser.parse_args()

    result = execute_cqc(args.command, args.perimeter_dir, args.dry_run)
    print(json.dumps(result, indent=2))
    if result["status"] == "failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
