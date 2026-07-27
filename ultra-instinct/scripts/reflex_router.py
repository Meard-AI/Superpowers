#!/usr/bin/env python3
"""
reflex_router.py — Ultra Instinct: Dynamic Compute Routing & Deterministic Reflex Engine.

Classifies a query as 'reflex' (run the mapped command directly, no LLM reasoning)
or 'reasoning' (fall through to the normal loop).

Ordering matters and is deliberate: reasoning intent is checked FIRST and vetoes any
route match. "explain why our eslint config is failing" contains 'eslint' but is a
reasoning request, and must never be answered by shelling out to a linter.

A reflex verdict is only ever returned alongside a concrete matched_command. If the
heuristics like a query but no command is mapped, the verdict downgrades to reasoning.
"""

import sys
import os
import json
import argparse
import re
import select
import signal
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Bound the work a single classification can do. Route patterns are user-supplied
# via --add-route and persist to disk, so a catastrophic-backtracking pattern like
# ^(a+)+$ would otherwise pin the CPU for minutes on a crafted query — turning a
# "zero-overhead fast path" into the slowest thing in the agent loop.
MAX_QUERY_LEN = 1000
MATCH_BUDGET_SECONDS = 2.0

# Heuristic for nested quantifiers, the classic ReDoS shape: a quantified group
# that itself contains a quantifier, e.g. (a+)+ (a*)* (a|aa)+ .
NESTED_QUANTIFIER_RE = re.compile(r"\([^)]*[+*]\)[+*{]|\([^)]*\{\d+,\}?\)[+*{]")


class MatchTimeout(Exception):
    pass


@contextmanager
def match_budget(seconds: float = MATCH_BUDGET_SECONDS):
    """Interrupt regex matching that runs too long.

    SIGALRM is the only way to break out of a single long-running re.search.
    It requires the main thread on POSIX; elsewhere this degrades to no timeout,
    which is why MAX_QUERY_LEN also caps the input independently.
    """
    if not hasattr(signal, "SIGALRM"):
        yield False
        return

    def _fire(signum, frame):
        raise MatchTimeout()

    try:
        previous = signal.signal(signal.SIGALRM, _fire)
    except (ValueError, OSError):
        yield False  # not the main thread
        return

    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield True
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


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

DEFAULT_CACHE_FILE = Path(__file__).resolve().parent.parent / "references" / "reflex_routes.json"

# Every command here must be a real, directly-executable command string.
# Placeholders like "sys_info" are forbidden: the playbook tells the agent to run
# matched_command verbatim, so a non-command here becomes a guaranteed failure.
DEFAULT_ROUTES = [
    {
        "pattern": r"(?i)^\s*(git\s+status|repo\s+status|check\s+git\s+status)\s*$",
        "command": "git status --short",
        "description": "Check git repository state",
        "confidence": 0.95,
    },
    {
        "pattern": r"(?i)^\s*git\s+diff\s*$",
        "command": "git diff --stat",
        "description": "Summarize unstaged changes",
        "confidence": 0.95,
    },
    {
        "pattern": r"(?i)^\s*(npm|yarn|pnpm)\s+test\s*$",
        "command": "npm test",
        "description": "Run the JavaScript test suite",
        "confidence": 0.90,
    },
    {
        "pattern": r"(?i)^\s*(pytest|run\s+pytest|python\s+tests?)\s*$",
        "command": "python3 -m pytest",
        "description": "Run the Python test suite",
        "confidence": 0.90,
    },
    {
        "pattern": r"(?i)^\s*(flake8|run\s+flake8|python\s+lint)\s*$",
        "command": "flake8 .",
        "description": "Run the Python linter",
        "confidence": 0.90,
    },
    {
        "pattern": r"(?i)^\s*(eslint|run\s+eslint|js\s+lint)\s*$",
        "command": "npx eslint .",
        "description": "Run the JavaScript linter",
        "confidence": 0.90,
    },
    {
        "pattern": r"(?i)^\s*(python\s+--version|python\s+version)\s*$",
        "command": "python3 --version",
        "description": "Report the Python interpreter version",
        "confidence": 0.98,
    },
    {
        "pattern": r"(?i)^\s*(node\s+--version|node\s+version)\s*$",
        "command": "node --version",
        "description": "Report the Node interpreter version",
        "confidence": 0.98,
    },
]

REFLEX_KEYWORDS = [
    "status", "lint", "format", "version", "help", "list", "check",
    "clean", "clear", "diff", "log", "show", "ping", "info", "inspect",
]

REASONING_KEYWORDS = [
    "design", "architect", "refactor", "debug", "why", "explain", "analyze",
    "optimize", "strategy", "tradeoff", "compare", "synthesize", "plan",
    "should", "recommend", "review", "improve", "investigate", "decide",
]

COMPLEXITY_MARKERS = ["&&", ";", "|", " then ", " because ", " so that ", " and then "]


def load_routes(cache_file: Path) -> List[Dict[str, Any]]:
    """Load routes, discarding non-dict entries.

    The route file is on disk and hand-editable. A list of bare values would
    otherwise reach the matching loop and raise AttributeError on r.get().
    """
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [r for r in data if isinstance(r, dict)]
        except Exception:
            pass
    return [dict(r) for r in DEFAULT_ROUTES]


def save_routes(cache_file: Path, routes: List[Dict[str, Any]]) -> Optional[str]:
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(routes, f, indent=2)
        return None
    except Exception as e:
        return f"Failed to save routes to {cache_file}: {e}"


def compile_route(pattern: str):
    """Compile a stored pattern, returning None if it is invalid.

    Stored patterns come from --add-route and persist to disk. An uncompilable
    pattern must degrade to 'skip this route', never take down classification
    for every subsequent query.
    """
    try:
        return re.compile(pattern)
    except re.error:
        return None


def reasoning_signal(query: str) -> Tuple[int, float, List[str]]:
    words = [w.lower() for w in re.findall(r"\w+", query)]
    hits = [w for w in words if w in REASONING_KEYWORDS]
    lowered = f" {query.lower()} "
    complexity = 0.20 if any(m in lowered for m in COMPLEXITY_MARKERS) else 0.0
    return len(hits), complexity, hits


def classify_query(query: str, routes: List[Dict[str, Any]], threshold: float = 0.70) -> Dict[str, Any]:
    q_clean = (query or "").strip()
    base = {
        "tier": "reasoning",
        "confidence": 0.0,
        "reason": "",
        "matched_command": None,
        "matched_pattern": None,
        "invalid_routes": [],
    }

    if not q_clean:
        base["reason"] = "Empty query passed"
        return base

    # 1. Reasoning intent VETO — evaluated before route matching.
    reasoning_hits, complexity, hit_words = reasoning_signal(q_clean)
    if reasoning_hits > 0 or complexity > 0:
        conf = min(0.95, 0.60 + reasoning_hits * 0.15 + complexity)
        base["confidence"] = round(conf, 2)
        detail = f"reasoning_keywords={hit_words}" if hit_words else "compound command structure"
        base["reason"] = f"Reasoning intent detected ({detail}); route matching vetoed"
        return base

    # 2. Registered route patterns, under a length cap and a wall-clock budget.
    q_match = q_clean[:MAX_QUERY_LEN]
    invalid: List[str] = []
    timed_out: Optional[str] = None

    with match_budget():
        for r in routes:
            pattern = r.get("pattern", "")
            if not pattern:
                continue
            rx = compile_route(pattern)
            if rx is None:
                invalid.append(pattern)
                continue
            try:
                hit = rx.search(q_match)
            except MatchTimeout:
                # A pathological pattern must not stall the agent. Abandon route
                # matching entirely and fall through to reasoning.
                timed_out = pattern
                invalid.append(pattern)
                break
            except re.error:
                invalid.append(pattern)
                continue
            if hit:
                command = r.get("command")
                conf = float(r.get("confidence", 0.90))
                if not command:
                    invalid.append(pattern)
                    continue
                tier = "reflex" if conf >= threshold else "reasoning"
                return {
                    "tier": tier,
                    "confidence": conf,
                    "reason": f"Query matched route pattern '{pattern}'",
                    "matched_command": command if tier == "reflex" else None,
                    "matched_pattern": pattern,
                    "invalid_routes": invalid,
                }

    base["invalid_routes"] = invalid
    if timed_out:
        base["confidence"] = 0.0
        base["reason"] = (
            f"Route matching aborted after {MATCH_BUDGET_SECONDS}s on pattern "
            f"'{timed_out}' (catastrophic backtracking); defaulting to reasoning. "
            f"Remove it with --invalidate."
        )
        base["timed_out_pattern"] = timed_out
        return base

    # 3. Reflex heuristics. These can never produce a reflex verdict on their own,
    #    because there is no command to run — surface the signal, stay in reasoning.
    words = [w.lower() for w in re.findall(r"\w+", q_clean)]
    reflex_hits = sum(1 for w in words if w in REFLEX_KEYWORDS)
    if reflex_hits > 0 and len(words) <= 10:
        base["confidence"] = 0.55
        base["reason"] = (
            f"Query looks routine (reflex_keywords={reflex_hits}) but no route maps it "
            "to a command; no reflex verdict without an executable command"
        )
        return base

    base["confidence"] = 0.50
    base["reason"] = "Query did not hit deterministic reflex patterns; defaulting to LLM reasoning"
    return base


def emit(payload: Dict[str, Any], as_json: bool, text_fn) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        text_fn(payload)


def main():
    parser = argparse.ArgumentParser(description="Ultra Instinct Dynamic Compute & Reflex Router")
    parser.add_argument("--query", type=str, help="Query text to evaluate")
    parser.add_argument("--tier-threshold", type=float, default=0.70,
                        help="Confidence threshold for reflex tier (default 0.70)")
    parser.add_argument("--add-route", type=str, metavar="PATTERN", help="Regex pattern for new route")
    parser.add_argument("--command", type=str, help="Command associated with new route")
    parser.add_argument("--confidence", type=float, default=0.95, help="Confidence for the new route")
    parser.add_argument("--invalidate", type=str, metavar="PATTERN", help="Invalidate route matching pattern")
    parser.add_argument("--list", action="store_true", help="List all registered reflex routes")
    parser.add_argument("--verify", action="store_true", help="Check every stored route compiles and has a command")
    parser.add_argument("--json", action="store_true", help="Output results in clean JSON format")
    parser.add_argument("--dry-run", action="store_true", help="Simulate route updates without persisting")
    parser.add_argument("--cache-file", type=str, help="Custom route cache JSON file path")

    args = parser.parse_args()
    cache_file = Path(args.cache_file) if args.cache_file else DEFAULT_CACHE_FILE
    routes = load_routes(cache_file)

    if args.list:
        res = {"status": "SUCCESS", "routes": routes, "count": len(routes)}

        def _text(p):
            print(f"Registered Reflex Routes ({p['count']}):")
            for idx, r in enumerate(p["routes"], 1):
                print(f"  {idx}. '{r.get('pattern')}' -> '{r.get('command')}' "
                      f"(conf={r.get('confidence', 0.9)})")
        emit(res, args.json, _text)
        sys.exit(0)

    if args.verify:
        problems = []
        for r in routes:
            pattern = r.get("pattern", "")
            if not pattern:
                problems.append({"pattern": pattern, "issue": "empty pattern"})
                continue
            if compile_route(pattern) is None:
                problems.append({"pattern": pattern, "issue": "does not compile"})
            elif not r.get("command"):
                problems.append({"pattern": pattern, "issue": "no command mapped"})
            elif NESTED_QUANTIFIER_RE.search(pattern):
                problems.append({"pattern": pattern,
                                 "issue": "nested quantifier — risks catastrophic backtracking"})
        res = {
            "status": "SUCCESS" if not problems else "INVALID",
            "checked": len(routes),
            "problems": problems,
        }

        def _text(p):
            print(f"[{p['status']}] Checked {p['checked']} route(s); {len(p['problems'])} problem(s)")
            for pr in p["problems"]:
                print(f"  - '{pr['pattern']}': {pr['issue']}")
        emit(res, args.json, _text)
        sys.exit(0 if not problems else 1)

    if args.add_route:
        if not args.command:
            err = {"status": "ERROR", "error": "Parameter --command is required when adding a route"}
            emit(err, args.json, lambda p: print(f"Error: {p['error']}", file=sys.stderr))
            sys.exit(1)
        if compile_route(args.add_route) is None:
            err = {"status": "ERROR",
                   "error": f"Pattern '{args.add_route}' is not a valid regular expression"}
            emit(err, args.json, lambda p: print(f"Error: {p['error']}", file=sys.stderr))
            sys.exit(1)
        if NESTED_QUANTIFIER_RE.search(args.add_route):
            err = {"status": "ERROR",
                   "error": f"Pattern '{args.add_route}' has a nested quantifier and risks "
                            f"catastrophic backtracking. Rewrite it without a quantified "
                            f"group containing a quantifier."}
            emit(err, args.json, lambda p: print(f"Error: {p['error']}", file=sys.stderr))
            sys.exit(1)
        if any(r.get("pattern") == args.add_route for r in routes):
            err = {"status": "ERROR",
                   "error": f"Route with pattern '{args.add_route}' already registered"}
            emit(err, args.json, lambda p: print(f"Error: {p['error']}", file=sys.stderr))
            sys.exit(1)

        new_route = {
            "pattern": args.add_route,
            "command": args.command,
            "description": f"Custom route for pattern '{args.add_route}'",
            "confidence": args.confidence,
        }
        routes.append(new_route)
        res = {"status": "SUCCESS", "added": new_route, "dry_run": args.dry_run}
        if not args.dry_run:
            err = save_routes(cache_file, routes)
            if err:
                res = {"status": "ERROR", "error": err}
        emit(res, args.json, lambda p: print(f"[{p['status']}] Added route (dry-run={args.dry_run})"))
        sys.exit(0 if res["status"] == "SUCCESS" else 1)

    if args.invalidate:
        filtered = [r for r in routes if r.get("pattern") != args.invalidate]
        removed_count = len(routes) - len(filtered)
        res = {"status": "SUCCESS", "removed_count": removed_count,
               "pattern": args.invalidate, "dry_run": args.dry_run}
        if not args.dry_run and removed_count > 0:
            err = save_routes(cache_file, filtered)
            if err:
                res = {"status": "ERROR", "error": err}
        emit(res, args.json,
             lambda p: print(f"[{p['status']}] Invalidated {removed_count} route(s) "
                             f"matching '{args.invalidate}' (dry-run={args.dry_run})"))
        sys.exit(0 if res["status"] == "SUCCESS" else 1)

    query_text = args.query
    if not query_text:
        query_text = read_available_stdin().strip()

    if query_text:
        result = classify_query(query_text, routes, threshold=args.tier_threshold)

        def _text(p):
            print(f"Tier: {p['tier'].upper()} (Confidence: {p['confidence']})")
            print(f"Reason: {p['reason']}")
            if p.get("matched_command"):
                print(f"Command: {p['matched_command']}")
            for bad in p.get("invalid_routes") or []:
                print(f"Warning: skipped unusable route '{bad}'", file=sys.stderr)
        emit(result, args.json, _text)
        sys.exit(0)

    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    main()
