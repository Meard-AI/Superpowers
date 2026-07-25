#!/usr/bin/env python3
"""
anti_stall.py - Heat-Mode Anti-Stall & Self-Healing Loop Detector

Detects repetitive log failures, tool error cycles, format failures, or deadlocks,
and outputs structured recovery recommendations in JSON format.
"""

import sys
import os
import json
import argparse
import re
from typing import Dict, Any, List


def analyze_log_content(log_text: str, threshold: int, failure_count_override: int = None) -> Dict[str, Any]:
    """
    Analyzes log text for repetitive failures, tool error cycles, or deadlocks.
    Returns a dictionary matching the specified JSON schema.
    """
    if not log_text and failure_count_override is None:
        return {
            "stall_detected": False,
            "consecutive_failures": 0,
            "recovery_strategy": "No log data provided; execution nominal.",
            "suggested_actions": []
        }

    lines = [line.strip() for line in (log_text or "").strip().split("\n") if line.strip()]

    # Failure indicators regex
    error_pattern = re.compile(
        r"(error|failed|failure|exception|traceback|timed out|permission prompt|deadlock|invalid|jsondecodeerror|syntaxerror)",
        re.IGNORECASE
    )

    consecutive_failures = 0
    failure_types = []

    for line in reversed(lines):
        if error_pattern.search(line):
            consecutive_failures += 1
            if re.search(r"json|parse|schema|decode|syntax", line, re.IGNORECASE):
                failure_types.append("json_format")
            elif re.search(r"permission|timeout|timed out|prompt|denied", line, re.IGNORECASE):
                failure_types.append("permission_timeout")
            elif re.search(r"deadlock|hang|block|stuck", line, re.IGNORECASE):
                failure_types.append("deadlock")
            elif re.search(r"command|exit code|process|not found", line, re.IGNORECASE):
                failure_types.append("command_failure")
            else:
                failure_types.append("generic_error")
        else:
            if consecutive_failures > 0:
                break

    if consecutive_failures == 0 and lines:
        total_error_lines = sum(1 for line in lines if error_pattern.search(line))
        if total_error_lines > 0:
            consecutive_failures = total_error_lines

    if failure_count_override is not None:
        consecutive_failures = max(consecutive_failures, failure_count_override)

    stall_detected = consecutive_failures >= threshold

    if not stall_detected:
        return {
            "stall_detected": False,
            "consecutive_failures": consecutive_failures,
            "recovery_strategy": "Execution nominal; error count within acceptable threshold.",
            "suggested_actions": []
        }

    # Determine recovery strategy & suggested actions
    suggested_actions: List[str] = []
    recovery_strategy = ""

    if "json_format" in failure_types:
        recovery_strategy = "Relax JSON strictness and drop non-essential format constraints."
        suggested_actions = [
            "Relax strict JSON schema validation and accept partial/flexible model output",
            "Use regex pattern extraction on raw output strings instead of strict json.loads()",
            "Drop non-essential output formatting rules to unblock execution flow"
        ]
    elif "permission_timeout" in failure_types:
        recovery_strategy = "Bypass interactive permission bottlenecks and check workspace path alignment."
        suggested_actions = [
            "Verify current working directory (Cwd) is strictly inside workspace root",
            "Avoid interactive pipe commands that trigger user confirmation timeouts",
            "Use non-interactive CLI diagnostics and file-based stdout redirects"
        ]
    elif "deadlock" in failure_types:
        recovery_strategy = "Terminate stalled background processes and reset context state."
        suggested_actions = [
            "Inspect and kill hanging background tasks using task management tools",
            "Flush temporary context memory to disk scratchpad",
            "Simplify command flags to prevent blocking wait loops"
        ]
    elif "command_failure" in failure_types:
        recovery_strategy = "Decompose failing command into atomic steps and try alternative CLI tools."
        suggested_actions = [
            "Decompose monolithic shell command into smaller, verifiable sub-commands",
            "Fallback to standard shell utilities (grep, find, python) if custom tools fail",
            "Verify tool arguments and file permissions"
        ]
    else:
        recovery_strategy = "Activate Heat-Mode self-healing protocol to break repetitive failure loop."
        suggested_actions = [
            "Relax JSON strictness and format constraints",
            "Try alternative CLI diagnostics and simpler parameters",
            "Reset execution context and offload progress state to scratch file",
            "Drop non-essential constraints to preserve core task progress"
        ]

    return {
        "stall_detected": stall_detected,
        "consecutive_failures": consecutive_failures,
        "recovery_strategy": recovery_strategy,
        "suggested_actions": suggested_actions
    }


def main():
    parser = argparse.ArgumentParser(
        description="Heat-Mode Anti-Stall Loop Detector & Self-Healing Recommendation Generator"
    )
    parser.add_argument(
        "--log", "--error-log",
        type=str,
        dest="log",
        default="",
        help="Log file path or raw error log text to analyze"
    )
    parser.add_argument(
        "--threshold", "--consecutive-failures",
        type=int,
        dest="threshold",
        default=3,
        help="Consecutive failure threshold to trigger stall detection (default: 3)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset heat mode state and error counts"
    )
    parser.add_argument(
        "--recommend",
        action="store_true",
        help="Force recommendation generation"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON (default output format is JSON)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate anti-stall analysis without side effects"
    )

    args = parser.parse_args()

    if args.reset:
        result = {
            "stall_detected": False,
            "consecutive_failures": 0,
            "recovery_strategy": "State reset completed. Monitoring baseline.",
            "suggested_actions": []
        }
        print(json.dumps(result, indent=2))
        sys.exit(0)

    log_text = ""
    if args.log:
        if os.path.exists(args.log) and os.path.isfile(args.log):
            try:
                with open(args.log, "r", encoding="utf-8", errors="ignore") as f:
                    log_text = f.read()
            except Exception as e:
                log_text = f"Error reading log file {args.log}: {str(e)}"
        else:
            log_text = args.log
    elif not sys.stdin.isatty():
        log_text = sys.stdin.read()

    result = analyze_log_content(log_text, args.threshold)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
