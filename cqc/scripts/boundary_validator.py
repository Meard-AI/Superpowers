#!/usr/bin/env python3
"""
boundary_validator.py - CQC Sandbox Perimeter Boundary Validator

Utility module and CLI for inspecting command boundaries, taking filesystem snapshots,
and detecting out-of-perimeter side-effects.

SCOPE HONESTY: this module performs STATIC ANALYSIS of a command string plus
BEST-EFFORT post-hoc filesystem diffing. Neither is a security boundary. A shell
command can defeat string analysis with variable expansion, command substitution,
eval, or an interpreter, and the filesystem diff only covers directories it is
told to watch. Use this to catch mistakes, and an OS sandbox (sandbox-exec,
Landlock/seccomp, bubblewrap, a container) to stop attacks.
"""

import sys
import os
import json
import argparse
import re
import shlex
from pathlib import Path
from typing import List, Dict, Optional

# Shell constructs whose expansion is unknowable without running them. Their
# presence makes static path analysis UNDECIDABLE, and we say so rather than
# reporting a clean bill of health.
DYNAMIC_CONSTRUCTS = [
    ("$(", "command substitution"),
    ("`", "backtick command substitution"),
    ("${", "parameter expansion"),
    ("$", "variable expansion"),
    ("~", "home-directory expansion"),
    ("eval", "eval"),
    ("exec", "exec"),
    ("xargs", "xargs"),
    ("base64", "base64 decoding"),
]

# Read-only system prefixes that are normal for any command to reference.
SYSTEM_PREFIXES = ["/bin", "/sbin", "/usr", "/opt", "/dev", "/proc", "/sys", "/etc/ssl", "/Library"]

SKIP_DIR_NAMES = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", ".mypy_cache"}


def resolve_abs(path_str: str, base_dir: str) -> str:
    """Resolves relative or absolute path string against a base directory."""
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = Path(base_dir) / path
    return str(path.resolve())


def is_within(child: str, parent: str) -> bool:
    """True when `child` is `parent` or lives underneath it.

    Component-wise containment via relative_to. A prefix string comparison is
    WRONG here: '/x/app-secrets'.startswith('/x/app') is True, which would place
    a sibling directory inside the perimeter.
    """
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except (ValueError, OSError):
        return False


def validate_boundary(check_path: str, allowed_paths: List[str]) -> bool:
    """Validates if check_path is contained within any of the allowed_paths."""
    for allowed in allowed_paths:
        if is_within(check_path, allowed):
            return True
    return False


def is_system_path(path_str: str) -> bool:
    for prefix in SYSTEM_PREFIXES:
        if path_str == prefix or path_str.startswith(prefix + os.sep):
            return True
    return False


def looks_like_path(token: str) -> bool:
    if not token or token.startswith("-"):
        return False
    return token.startswith(("/", "./", "../", "~")) or os.sep in token


def detect_dynamic_constructs(command: str) -> List[str]:
    found = []
    for marker, label in DYNAMIC_CONSTRUCTS:
        if marker in command:
            found.append(label)
    return sorted(set(found))


def inspect_command_bounds(command: str, perimeter_dir: str) -> List[str]:
    """Static check for perimeter escape. Returns a list of violation strings.

    Tokenizes with shlex so QUOTED paths are seen — the previous regex only
    matched whitespace-delimited absolute paths, so `> "/etc/x"` slipped through.
    """
    violations: List[str] = []
    abs_perimeter = str(Path(perimeter_dir).expanduser().resolve())

    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError:
        # Unbalanced quotes — fall back to whitespace splitting rather than
        # silently analysing nothing.
        tokens = command.split()

    for token in tokens:
        if not looks_like_path(token):
            continue
        try:
            resolved = resolve_abs(token, abs_perimeter)
        except Exception:
            continue
        if is_system_path(resolved):
            continue
        if not is_within(resolved, abs_perimeter):
            violations.append(
                f"Static analysis: command references path outside perimeter: {token} -> {resolved}"
            )

    return violations


def analyze_command(command: str, perimeter_dir: str) -> Dict:
    """Full static verdict, including whether the analysis is even decidable."""
    dynamic = detect_dynamic_constructs(command)
    violations = inspect_command_bounds(command, perimeter_dir)
    return {
        "violations": violations,
        "dynamic_constructs": dynamic,
        "undecidable": bool(dynamic),
        "note": (
            "Command contains shell constructs that expand at runtime "
            f"({', '.join(dynamic)}); static path analysis cannot be trusted. "
            "Use an OS-level sandbox to enforce this boundary."
        ) if dynamic else "",
    }


def snapshot_filesystem(watch_dirs: List[str], perimeter_dir: str) -> Dict[str, float]:
    """Capture mtimes of files in watch_dirs that lie OUTSIDE perimeter_dir."""
    abs_perimeter = str(Path(perimeter_dir).resolve())
    snapshot: Dict[str, float] = {}

    for watch_dir in watch_dirs:
        try:
            abs_watch = str(Path(watch_dir).resolve())
        except Exception:
            continue
        try:
            for root, dirs, files in os.walk(abs_watch):
                # Prune in place so os.walk does not descend into skipped trees.
                dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES]
                if is_within(root, abs_perimeter):
                    dirs[:] = []
                    continue
                for file_name in files:
                    full_path = os.path.join(root, file_name)
                    try:
                        snapshot[full_path] = os.path.getmtime(full_path)
                    except Exception:
                        pass
        except Exception:
            pass

    return snapshot


def detect_delta(pre_snapshot: Dict[str, float], post_snapshot: Dict[str, float]) -> List[str]:
    """Compare snapshots to find created, modified, or deleted files outside perimeter."""
    violations = []
    pre_files = set(pre_snapshot.keys())
    post_files = set(post_snapshot.keys())

    for f in sorted(post_files - pre_files):
        violations.append(f"Boundary violation: file created outside perimeter: {f}")
    for f in sorted(pre_files & post_files):
        if abs(post_snapshot[f] - pre_snapshot[f]) > 1e-4:
            violations.append(f"Boundary violation: file modified outside perimeter: {f}")
    for f in sorted(pre_files - post_files):
        violations.append(f"Boundary violation: file deleted outside perimeter: {f}")

    return violations


def main():
    parser = argparse.ArgumentParser(description="CQC Boundary Validator")
    parser.add_argument("--allowed-paths", type=str, help="Comma-separated allowed root paths")
    parser.add_argument("--check-path", type=str, help="Path to validate against boundary")
    parser.add_argument("--check-command", type=str, help="Command string to statically analyze")
    parser.add_argument("--perimeter-dir", type=str, help="Perimeter for --check-command (default: CWD)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--dry-run", action="store_true", help="Simulate boundary check without side effects")

    args = parser.parse_args()

    if args.check_command:
        perimeter = args.perimeter_dir or os.getcwd()
        analysis = analyze_command(args.check_command, perimeter)
        blocked = bool(analysis["violations"])
        res = {
            "status": "BLOCKED" if blocked else ("UNDECIDABLE" if analysis["undecidable"] else "ALLOWED"),
            "valid": not blocked,
            "command": args.check_command,
            "perimeter_dir": str(Path(perimeter).resolve()),
            **analysis,
            "dry_run": args.dry_run,
        }
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"[{res['status']}] {args.check_command}")
            for v in analysis["violations"]:
                print(f"  - {v}")
            if analysis["note"]:
                print(f"  ! {analysis['note']}")
        sys.exit(0 if not blocked else 1)

    if not args.check_path:
        parser.print_help()
        sys.exit(0)

    allowed_raw = args.allowed_paths.split(",") if args.allowed_paths else [str(Path.cwd())]
    allowed_paths = [p.strip() for p in allowed_raw if p.strip()]

    is_valid = validate_boundary(args.check_path, allowed_paths)

    res = {
        "status": "ALLOWED" if is_valid else "BLOCKED",
        "valid": is_valid,
        "check_path": args.check_path,
        "resolved_path": str(Path(args.check_path).expanduser().resolve()),
        "allowed_paths": allowed_paths,
        "dry_run": args.dry_run,
    }

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"[{res['status']}] {res['resolved_path']}")
        print(f"Allowed roots: {', '.join(allowed_paths)}")
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
