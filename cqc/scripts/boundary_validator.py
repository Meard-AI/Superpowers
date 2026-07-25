#!/usr/bin/env python3
"""
boundary_validator.py - CQC Sandbox Perimeter Boundary Validator

Utility module and CLI for inspecting command boundaries, taking filesystem snapshots,
and detecting out-of-perimeter side-effects.
"""

import sys
import os
import json
import argparse
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple


def resolve_abs(path_str: str, base_dir: str) -> str:
    """Resolves relative or absolute path string against a base directory."""
    path = Path(path_str)
    if not path.is_absolute():
        path = (Path(base_dir) / path).resolve()
    else:
        path = path.resolve()
    return str(path)


def validate_boundary(check_path: str, allowed_paths: List[str]) -> bool:
    """Validates if check_path is contained within any of the allowed_paths."""
    target = Path(check_path).resolve()
    for allowed in allowed_paths:
        allowed_resolved = Path(allowed).resolve()
        try:
            target.relative_to(allowed_resolved)
            return True
        except ValueError:
            continue
    return False


def inspect_command_bounds(command: str, perimeter_dir: str) -> List[str]:
    """
    Performs static checks on command string to detect potential perimeter escape.
    """
    violations = []
    abs_perimeter = str(Path(perimeter_dir).resolve())

    # Detect absolute paths in command pointing outside perimeter
    abs_path_matches = re.findall(r'(?:^|\s)(/[a-zA-Z0-9_\.\-/]+)', command)
    for path_str in abs_path_matches:
        if path_str.startswith(('/bin', '/usr/bin', '/usr/local/bin', '/opt', '/dev', '/proc', '/sys')):
            continue
        try:
            resolved = str(Path(path_str).resolve())
            if not resolved.startswith(abs_perimeter):
                violations.append(f"Static analysis: Command references path outside perimeter: {path_str}")
        except Exception:
            pass

    # Detect parent directory traversal attempts
    if "../" in command or "..\\" in command:
        parts = command.split()
        for p in parts:
            if ".." in p:
                try:
                    resolved = resolve_abs(p, abs_perimeter)
                    if not resolved.startswith(abs_perimeter):
                        violations.append(f"Static analysis: Path traversal attempts to escape perimeter: {p}")
                except Exception:
                    pass

    return violations


def snapshot_filesystem(parent_dir: str, perimeter_dir: str) -> Dict[str, float]:
    """
    Captures snapshot of file modification times in parent_dir outside perimeter_dir.
    """
    abs_parent = str(Path(parent_dir).resolve())
    abs_perimeter = str(Path(perimeter_dir).resolve())
    snapshot = {}

    try:
        for root, dirs, files in os.walk(abs_parent):
            if ".git" in root or "__pycache__" in root or ".pytest_cache" in root:
                continue
            abs_root = str(Path(root).resolve())
            if abs_root == abs_perimeter or abs_root.startswith(abs_perimeter + os.sep):
                continue
            for file_name in files:
                full_path = os.path.join(root, file_name)
                try:
                    mtime = os.path.getmtime(full_path)
                    snapshot[full_path] = mtime
                except Exception:
                    pass
    except Exception:
        pass

    return snapshot


def detect_delta(pre_snapshot: Dict[str, float], post_snapshot: Dict[str, float]) -> List[str]:
    """
    Compares pre and post snapshots to find created, modified, or deleted files outside perimeter.
    """
    violations = []
    pre_files = set(pre_snapshot.keys())
    post_files = set(post_snapshot.keys())

    created = post_files - pre_files
    for f in created:
        violations.append(f"Boundary violation: File created outside perimeter dir: {f}")

    common = pre_files & post_files
    for f in common:
        if abs(post_snapshot[f] - pre_snapshot[f]) > 1e-4:
            violations.append(f"Boundary violation: File modified outside perimeter dir: {f}")

    deleted = pre_files - post_files
    for f in deleted:
        violations.append(f"Boundary violation: File deleted outside perimeter dir: {f}")

    return violations


def main():
    parser = argparse.ArgumentParser(description="CQC Boundary Validator")
    parser.add_argument("--allowed-paths", type=str, help="Comma-separated allowed root paths")
    parser.add_argument("--check-path", type=str, help="Path to validate against boundary")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--dry-run", action="store_true", help="Simulate boundary check without side effects")

    args = parser.parse_args()

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
        "allowed_paths": allowed_paths,
        "dry_run": args.dry_run
    }

    print(json.dumps(res, indent=2))
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
