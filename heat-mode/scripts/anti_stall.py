#!/usr/bin/env python3
"""
anti_stall.py - Heat-Mode Anti-Stall & Self-Healing Loop Detector

Detects repetitive log failures, tool error cycles, format failures, or deadlocks,
and outputs structured recovery recommendations.

Failure count is the MAXIMUM of three independent signals:
  1. --consecutive-failures N   caller-reported count (the agent knows its own retry count)
  2. trailing error lines in the analyzed log text
  3. the persisted counter, incremented by --record-failure and cleared by --reset

Stall fires when that count reaches --threshold (default 2, matching the skill contract).
"""

import sys
import os
import json
import argparse
import re
import select
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, List, Optional


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


def default_state_file() -> Path:
    """Resolve the persistent state path OUTSIDE the skill package.

    The skill folder is meant to be copied around read-only; runtime counters
    belong in the user's state dir, not in the distributed package.
    """
    override = os.environ.get("AGENT_SUPERPOWERS_STATE")
    if override:
        return Path(override).expanduser() / "heat-mode.json"
    base = os.environ.get("XDG_STATE_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".local" / "state"
    return root / "agent-superpowers" / "heat-mode.json"


def load_state(state_file: Path) -> Dict[str, Any]:
    """Load persistent state, coercing anything malformed back to a safe default.

    The state file is on disk and can be hand-edited, truncated by a crash, or
    written by an older version. A counter of "NaN" or -5 must not crash the
    caller or produce a negative failure count.
    """
    default = {"recorded_failures": 0, "last_strategy": None}
    if not state_file.exists():
        return default
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return default
    if not isinstance(data, dict):
        return default

    try:
        recorded = int(data.get("recorded_failures", 0))
    except (TypeError, ValueError):
        recorded = 0
    strategy = data.get("last_strategy")
    return {
        "recorded_failures": max(0, recorded),
        "last_strategy": strategy if isinstance(strategy, str) else None,
    }


@contextmanager
def state_lock(state_file: Path):
    """Serialize read-modify-write on the state file across processes.

    Without this, concurrent --record-failure calls each read the old counter and
    write back old+1, so most increments are silently lost. flock is POSIX-only;
    elsewhere this degrades to no locking, which is the prior behaviour.
    """
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        lock_path = state_file.with_name(state_file.name + ".lock")
        handle = open(lock_path, "w")
    except Exception:
        yield
        return
    try:
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except Exception:
            pass
        yield
    finally:
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        handle.close()


def save_state(state_file: Path, state: Dict[str, Any]) -> Optional[str]:
    """Write atomically so a crash mid-write cannot leave a truncated file."""
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = state_file.with_name(state_file.name + f".tmp.{os.getpid()}")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, state_file)
        return None
    except Exception as e:
        return f"Failed to persist state to {state_file}: {e}"


ERROR_PATTERN = re.compile(
    r"(error|failed|failure|exception|traceback|timed out|timeout|permission|"
    r"denied|refused|deadlock|invalid|unable to|cannot |not found|"
    r"jsondecodeerror|syntaxerror)",
    re.IGNORECASE,
)

# Ordered most-specific first; first match wins for a given line.
FAILURE_CLASSIFIERS = [
    ("json_format", re.compile(r"json|parse|schema|decode|syntax", re.IGNORECASE)),
    ("permission_timeout", re.compile(r"permission|timeout|timed out|prompt|denied", re.IGNORECASE)),
    ("deadlock", re.compile(r"deadlock|hang|block|stuck", re.IGNORECASE)),
    ("command_failure", re.compile(r"command|exit code|process|not found", re.IGNORECASE)),
]

RECOVERY_PLAYBOOK = {
    "json_format": (
        "Relax JSON strictness and drop non-essential format constraints.",
        [
            "Relax strict JSON schema validation and accept partial/flexible model output",
            "Use regex pattern extraction on raw output strings instead of strict json.loads()",
            "Drop non-essential output formatting rules to unblock execution flow",
        ],
    ),
    "permission_timeout": (
        "Bypass interactive permission bottlenecks and check workspace path alignment.",
        [
            "Verify current working directory is strictly inside workspace root",
            "Avoid interactive pipe commands that trigger user confirmation timeouts",
            "Use non-interactive CLI diagnostics and file-based stdout redirects",
        ],
    ),
    "deadlock": (
        "Terminate stalled background processes and reset context state.",
        [
            "Inspect and kill hanging background tasks using task management tools",
            "Flush temporary context memory to disk scratchpad",
            "Simplify command flags to prevent blocking wait loops",
        ],
    ),
    "command_failure": (
        "Decompose failing command into atomic steps and try alternative CLI tools.",
        [
            "Decompose monolithic shell command into smaller, verifiable sub-commands",
            "Fallback to standard shell utilities (grep, find, python) if custom tools fail",
            "Verify tool arguments and file permissions",
        ],
    ),
    "generic_error": (
        "Activate Heat-Mode self-healing protocol to break repetitive failure loop.",
        [
            "Relax JSON strictness and format constraints",
            "Try alternative CLI diagnostics and simpler parameters",
            "Reset execution context and offload progress state to scratch file",
            "Drop non-essential constraints to preserve core task progress",
        ],
    ),
}


def classify_line(line: str) -> str:
    for name, pattern in FAILURE_CLASSIFIERS:
        if pattern.search(line):
            return name
    return "generic_error"


def scan_log(log_text: str) -> Dict[str, Any]:
    """Count TRAILING consecutive error lines and classify the failure streak.

    Trailing-consecutive is the honest reading of 'consecutive failures': a run of
    errors interrupted by a success is no longer a stall. total_error_lines is
    reported separately rather than silently substituted for the streak.
    """
    lines = [ln.strip() for ln in (log_text or "").strip().split("\n") if ln.strip()]
    streak = 0
    streak_types: List[str] = []

    for line in reversed(lines):
        if ERROR_PATTERN.search(line):
            streak += 1
            streak_types.append(classify_line(line))
        else:
            break

    total_error_lines = sum(1 for ln in lines if ERROR_PATTERN.search(ln))
    return {
        "log_streak": streak,
        "log_streak_types": streak_types,
        "total_error_lines": total_error_lines,
        "analyzed_lines": len(lines),
    }


def dominant_type(streak_types: List[str]) -> str:
    """Pick the failure class to act on: most recent wins ties.

    streak_types is built newest-first, so the first entry is the latest failure.
    Ranking by count with the newest as tiebreak beats the old behaviour, which
    always let a single stale json error dominate the whole recommendation.
    """
    if not streak_types:
        return "generic_error"
    counts: Dict[str, int] = {}
    for t in streak_types:
        counts[t] = counts.get(t, 0) + 1
    best = max(counts.values())
    for t in streak_types:  # newest-first order breaks the tie
        if counts[t] == best:
            return t
    return "generic_error"


def analyze(
    log_text: str,
    threshold: int,
    reported_failures: Optional[int] = None,
    recorded_failures: int = 0,
    force_recommend: bool = False,
) -> Dict[str, Any]:
    scan = scan_log(log_text)

    signals = {
        "log_streak": scan["log_streak"],
        "caller_reported": reported_failures or 0,
        "persisted": recorded_failures,
    }
    consecutive_failures = max(signals.values())
    stall_detected = consecutive_failures >= threshold

    result: Dict[str, Any] = {
        "status": "SUCCESS",
        "stall_detected": stall_detected,
        "consecutive_failures": consecutive_failures,
        "threshold": threshold,
        "signals": signals,
        "total_error_lines": scan["total_error_lines"],
        "analyzed_lines": scan["analyzed_lines"],
    }

    if not stall_detected and not force_recommend:
        result["failure_class"] = None
        result["recovery_strategy"] = "Execution nominal; error count within acceptable threshold."
        result["suggested_actions"] = []
        return result

    streak_types = scan["log_streak_types"]
    if not streak_types and log_text and log_text.strip():
        # The caller reported failures but no line matched the error vocabulary.
        # The text they passed IS the error trace, so classify it directly rather
        # than falling back to a generic recommendation.
        tail = [ln.strip() for ln in log_text.strip().split("\n") if ln.strip()]
        streak_types = [classify_line(tail[-1])]

    failure_class = dominant_type(streak_types)
    strategy, actions = RECOVERY_PLAYBOOK[failure_class]

    result["failure_class"] = failure_class
    result["recovery_strategy"] = strategy
    result["suggested_actions"] = actions
    if not stall_detected and force_recommend:
        result["note"] = (
            f"Below threshold ({consecutive_failures}/{threshold}); "
            "recommendations forced by --recommend."
        )
    return result


def emit(result: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2))
        return
    flag = "STALL DETECTED" if result.get("stall_detected") else "NOMINAL"
    print(f"[{flag}] consecutive_failures={result.get('consecutive_failures')} "
          f"threshold={result.get('threshold')}")
    if result.get("failure_class"):
        print(f"Failure class: {result['failure_class']}")
    print(f"Strategy: {result.get('recovery_strategy')}")
    for i, action in enumerate(result.get("suggested_actions") or [], 1):
        print(f"  {i}. {action}")
    if result.get("note"):
        print(f"Note: {result['note']}")


def main():
    parser = argparse.ArgumentParser(
        description="Heat-Mode Anti-Stall Loop Detector & Self-Healing Recommendation Generator"
    )
    parser.add_argument(
        "--log", "--error-log",
        type=str, dest="log", default="",
        help="Log file path, or raw error log text, to analyze"
    )
    parser.add_argument(
        "--consecutive-failures",
        type=int, dest="consecutive_failures", default=None,
        help="Number of consecutive failures the CALLER has already observed"
    )
    parser.add_argument(
        "--threshold",
        type=int, dest="threshold", default=2,
        help="Failure count at which a stall is declared (default: 2)"
    )
    parser.add_argument(
        "--record-failure", action="store_true",
        help="Increment the persistent failure counter, then analyze"
    )
    parser.add_argument("--reset", action="store_true", help="Reset persistent failure counter to zero")
    parser.add_argument("--recommend", action="store_true", help="Emit recommendations even below threshold")
    parser.add_argument("--state-file", type=str, help="Override persistent state file path")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without writing persistent state")

    args = parser.parse_args()
    state_file = Path(args.state_file).expanduser() if args.state_file else default_state_file()

    if args.reset:
        result = {
            "status": "SUCCESS",
            "action": "reset",
            "state_file": str(state_file),
            "recorded_failures": 0,
            "dry_run": args.dry_run,
        }
        if not args.dry_run:
            err = save_state(state_file, {"recorded_failures": 0, "last_strategy": None})
            if err:
                result["status"] = "ERROR"
                result["error"] = err
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"[{result['status']}] Failure counter reset (state: {state_file})")
        sys.exit(0 if result["status"] == "SUCCESS" else 1)

    # Resolve log input. A path that looks like a path but is missing is an ERROR,
    # not silently reinterpreted as log body text.
    log_text = ""
    if args.log:
        candidate = Path(args.log).expanduser()
        looks_like_path = ("\n" not in args.log) and (
            os.sep in args.log or args.log.endswith((".log", ".txt", ".json", ".out"))
        )
        if candidate.is_file():
            try:
                log_text = candidate.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                err = {"status": "ERROR", "error": f"Failed to read log file '{args.log}': {e}"}
                print(json.dumps(err, indent=2) if args.json else f"Error: {err['error']}",
                      file=None if args.json else sys.stderr)
                sys.exit(1)
        elif looks_like_path:
            err = {"status": "ERROR",
                   "error": f"Log path '{args.log}' does not exist. "
                            f"Pass raw log text without path separators to analyze inline."}
            print(json.dumps(err, indent=2) if args.json else f"Error: {err['error']}",
                  file=None if args.json else sys.stderr)
            sys.exit(1)
        else:
            log_text = args.log
    else:
        log_text = read_available_stdin()

    # Read-modify-write under a lock so concurrent --record-failure calls do not
    # each read the old counter and clobber one another's increment.
    with state_lock(state_file):
        state = load_state(state_file)
        if args.record_failure:
            state["recorded_failures"] = int(state.get("recorded_failures", 0)) + 1

        result = analyze(
            log_text,
            threshold=args.threshold,
            reported_failures=args.consecutive_failures,
            recorded_failures=int(state.get("recorded_failures", 0)),
            force_recommend=args.recommend,
        )
        result["state_file"] = str(state_file)
        result["dry_run"] = args.dry_run

        if args.record_failure and not args.dry_run:
            state["last_strategy"] = result.get("recovery_strategy")
            err = save_state(state_file, state)
            if err:
                result["state_warning"] = err

    emit(result, args.json)
    sys.exit(0)


if __name__ == "__main__":
    main()
