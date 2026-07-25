#!/usr/bin/env python3
"""
reflex_router.py — Ultra Instinct: Dynamic Compute Routing & Deterministic Reflex Engine.
Classifies input queries into 'reflex' vs 'reasoning' tiers and routes deterministic queries with 0ms LLM overhead.
"""

import sys
import os
import json
import argparse
import re
from pathlib import Path

DEFAULT_CACHE_FILE = Path(__file__).resolve().parent.parent / "references" / "reflex_routes.json"

DEFAULT_ROUTES = [
    {
        "pattern": r"(?i).*(lint|check format|style|flake8|pylint|rubocop|eslint).*",
        "command": "flake8 .",
        "description": "Run standard linter check",
        "confidence": 0.95
    },
    {
        "pattern": r"(?i).*(run test|pytest|unit test|test suite|npm test).*",
        "command": "python3 -m unittest discover -s tests",
        "description": "Run unit test suite",
        "confidence": 0.90
    },
    {
        "pattern": r"(?i).*(git status|repo status|check status|git diff).*",
        "command": "git status --short",
        "description": "Check git repository state",
        "confidence": 0.95
    },
    {
        "pattern": r"(?i).*(python --version|node --version|cat package.json|ls -la).*",
        "command": "sys_info",
        "description": "System environment inspection",
        "confidence": 0.98
    }
]

REFLEX_KEYWORDS = [
    "status", "lint", "format", "version", "help", "list", "check",
    "clean", "clear", "diff", "log", "show", "ping", "info", "inspect"
]

REASONING_KEYWORDS = [
    "design", "architect", "refactor", "debug", "why", "explain", "analyze",
    "optimize", "strategy", "tradeoff", "compare", "synthesize", "plan"
]


def load_routes(cache_file: Path):
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_ROUTES.copy()


def save_routes(cache_file: Path, routes: list):
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(routes, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save routes to {cache_file}: {e}", file=sys.stderr)


def classify_query(query: str, routes: list, threshold: float = 0.70) -> dict:
    q_clean = query.strip()
    if not q_clean:
        return {
            "tier": "reasoning",
            "confidence": 0.0,
            "reason": "Empty query passed",
            "matched_command": None,
            "matched_pattern": None
        }

    # 1. Match against registered route patterns
    for r in routes:
        pattern = r.get("pattern", "")
        if pattern and re.search(pattern, q_clean):
            conf = float(r.get("confidence", 0.90))
            tier = "reflex" if conf >= threshold else "reasoning"
            return {
                "tier": tier,
                "confidence": conf,
                "reason": f"Query matched route pattern '{pattern}'",
                "matched_command": r.get("command"),
                "matched_pattern": pattern
            }

    # 2. Keyword & heuristic classification
    words = [w.lower() for w in re.findall(r'\w+', q_clean)]
    reflex_hits = sum(1 for w in words if w in REFLEX_KEYWORDS)
    reasoning_hits = sum(1 for w in words if w in REASONING_KEYWORDS)

    # Complexity indicators: length, nested clauses, conjunctions
    length_penalty = min(len(words) * 0.02, 0.40)
    complexity_boost = 0.20 if any(c in q_clean for c in ["&&", ";", "|", "then", "because"]) else 0.0

    if reasoning_hits > 0 or complexity_boost > 0:
        conf = min(0.85, 0.50 + reasoning_hits * 0.15 + complexity_boost)
        return {
            "tier": "reasoning",
            "confidence": round(conf, 2),
            "reason": f"Query contains reasoning triggers (reasoning_keywords={reasoning_hits}, complexity={complexity_boost})",
            "matched_command": None,
            "matched_pattern": None
        }

    if reflex_hits > 0 and len(words) <= 10:
        conf = max(0.70, 0.90 - length_penalty)
        tier = "reflex" if conf >= threshold else "reasoning"
        return {
            "tier": tier,
            "confidence": round(conf, 2),
            "reason": f"Query matched reflex heuristics (reflex_keywords={reflex_hits}, length={len(words)})",
            "matched_command": None,
            "matched_pattern": None
        }

    # Fallback default: reasoning tier for unmapped complex text
    conf = 0.50
    tier = "reflex" if conf >= threshold else "reasoning"
    return {
        "tier": tier,
        "confidence": round(conf, 2),
        "reason": "Query did not hit deterministic reflex patterns; defaulting to LLM reasoning",
        "matched_command": None,
        "matched_pattern": None
    }


def main():
    parser = argparse.ArgumentParser(description="Ultra Instinct Dynamic Compute & Reflex Router")
    parser.add_argument("--query", type=str, help="Query text to evaluate")
    parser.add_argument("--tier-threshold", type=float, default=0.70, help="Confidence threshold for reflex tier (default 0.70)")
    parser.add_argument("--add-route", type=str, metavar="PATTERN", help="Regex pattern for new route")
    parser.add_argument("--command", type=str, help="Command associated with new route")
    parser.add_argument("--invalidate", type=str, metavar="PATTERN", help="Invalidate route matching pattern")
    parser.add_argument("--list", action="store_true", help="List all registered reflex routes")
    parser.add_argument("--json", action="store_true", help="Output results in clean JSON format")
    parser.add_argument("--dry-run", action="store_true", help="Simulate route updates without persisting")
    parser.add_argument("--cache-file", type=str, help="Custom route cache JSON file path")

    args = parser.parse_args()

    cache_file = Path(args.cache_file) if args.cache_file else DEFAULT_CACHE_FILE
    routes = load_routes(cache_file)

    if args.list:
        res = {"status": "SUCCESS", "routes": routes, "count": len(routes)}
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Registered Reflex Routes ({len(routes)}):")
            for idx, r in enumerate(routes, 1):
                print(f"  {idx}. Pattern: '{r['pattern']}' -> Command: '{r['command']}' (conf={r.get('confidence', 0.9)})")
        sys.exit(0)

    if args.add_route:
        if not args.command:
            err = {"error": "Parameter --command is required when adding a route"}
            if args.json:
                print(json.dumps(err))
            else:
                print(f"Error: {err['error']}", file=sys.stderr)
            sys.exit(1)

        new_route = {
            "pattern": args.add_route,
            "command": args.command,
            "description": f"Custom route for pattern '{args.add_route}'",
            "confidence": 0.95
        }
        routes.append(new_route)
        if not args.dry_run:
            save_routes(cache_file, routes)

        res = {"status": "SUCCESS", "added": new_route, "dry_run": args.dry_run}
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Successfully added route (dry-run={args.dry_run}): {new_route}")
        sys.exit(0)

    if args.invalidate:
        filtered = [r for r in routes if r["pattern"] != args.invalidate]
        removed_count = len(routes) - len(filtered)
        if not args.dry_run and removed_count > 0:
            save_routes(cache_file, filtered)
        res = {"status": "SUCCESS", "removed_count": removed_count, "pattern": args.invalidate, "dry_run": args.dry_run}
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Invalidated {removed_count} route(s) matching '{args.invalidate}' (dry-run={args.dry_run})")
        sys.exit(0)

    query_text = args.query
    if not query_text and not sys.stdin.isatty():
        query_text = sys.stdin.read().strip()

    if query_text is not None:
        result = classify_query(query_text, routes, threshold=args.tier_threshold)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Tier: {result['tier'].upper()} (Confidence: {result['confidence']})")
            print(f"Reason: {result['reason']}")
            if result['matched_command']:
                print(f"Command: {result['matched_command']}")
        sys.exit(0)

    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    main()
