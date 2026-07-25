#!/usr/bin/env python3
"""
mutation_fuzzer.py - Animal-Instinct Genetic Fuzzer & Mutation Tester

Executes mutation fuzzing routines on target scripts or inputs,
identifying edge-case failures, crash conditions, and computing heuristic risk scores.
"""

import sys
import os
import json
import argparse
import random
import subprocess
import copy
from pathlib import Path
from typing import List, Dict, Any, Tuple


# Default seed primitives if none provided
DEFAULT_SEEDS = [
    {"name": "test_input", "value": 42, "enabled": True, "tags": ["unit", "test"]},
    "Standard string payload for testing",
    100,
    [1, 2, 3, 4, 5]
]

# Mutation Primitives
MUTATIONS_STRINGS = [
    "",
    "\x00",
    "\x00" * 10,
    "A" * 10000,
    "'; DROP TABLE users; --",
    "<script>alert(1)</script>",
    "%s%d%n%x",
    "ñöℵ𝄢CJK_こんにちは_123",
    "   \t\r\n   ",
    "../../../../etc/passwd"
]

MUTATIONS_NUMBERS = [
    0,
    -1,
    2147483647,
    -2147483648,
    9223372036854775807,
    1e308,
    -1e308,
    float('nan'),
    float('inf'),
    -float('inf')
]


def load_seeds(seed_input_arg: str) -> List[Any]:
    """Loads seeds from a directory, JSON file, or raw JSON string."""
    if not seed_input_arg:
        return DEFAULT_SEEDS

    path = Path(seed_input_arg)
    if path.exists():
        if path.is_dir():
            seeds = []
            for file_path in path.glob("*"):
                if file_path.is_file():
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            try:
                                seeds.append(json.loads(content))
                            except Exception:
                                seeds.append(content)
                    except Exception:
                        pass
            return seeds if seeds else DEFAULT_SEEDS
        elif path.is_file():
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    try:
                        parsed = json.loads(content)
                        return parsed if isinstance(parsed, list) else [parsed]
                    except Exception:
                        return [content]
            except Exception:
                return DEFAULT_SEEDS

    try:
        parsed = json.loads(seed_input_arg)
        return parsed if isinstance(parsed, list) else [parsed]
    except Exception:
        return [seed_input_arg]


def mutate_val(val: Any) -> Tuple[Any, str]:
    """Applies a random genetic mutation to a given value and returns (mutated_val, mutation_desc)."""
    mutation_type = random.choice([
        "type_flip",
        "boundary_value",
        "null_injection",
        "structure_alteration",
        "extreme_string"
    ])

    if mutation_type == "type_flip":
        if isinstance(val, (int, float)):
            return str(val), "TypeFlip [NumberToString]"
        elif isinstance(val, str):
            return 999999, "TypeFlip [StringToInt]"
        elif isinstance(val, list):
            return {"mutated_dict": True}, "TypeFlip [ArrayToDict]"
        elif isinstance(val, dict):
            return ["mutated_array"], "TypeFlip [DictToArray]"
        else:
            return None, "TypeFlip [ToNull]"

    elif mutation_type == "boundary_value":
        num_mut = random.choice(MUTATIONS_NUMBERS)
        if isinstance(num_mut, float) and (num_mut != num_mut or abs(num_mut) == float('inf')):
            num_str = str(num_mut)
            return num_str, f"BoundaryValue [{num_str}]"
        return num_mut, f"BoundaryValue [{num_mut}]"

    elif mutation_type == "null_injection":
        return "\x00", "NullByteInjection"

    elif mutation_type == "extreme_string":
        st_mut = random.choice(MUTATIONS_STRINGS)
        return st_mut, f"ExtremeString [{repr(st_mut[:15])}]"

    else:
        if isinstance(val, dict) and val:
            mut_dict = copy.deepcopy(val)
            action = random.choice(["delete_key", "add_key", "mutate_key"])
            if action == "delete_key":
                key_to_del = random.choice(list(mut_dict.keys()))
                del mut_dict[key_to_del]
                return mut_dict, f"StructureAlteration [DeletedKey:{key_to_del}]"
            elif action == "add_key":
                mut_dict["__unexpected_fuzz_key__"] = "\x00" * 100
                return mut_dict, "StructureAlteration [AddedUnexpectedKey]"
            else:
                key_to_mod = random.choice(list(mut_dict.keys()))
                mut_dict[key_to_mod], sub_desc = mutate_val(mut_dict[key_to_mod])
                return mut_dict, f"StructureAlteration [ModKey:{key_to_mod}:{sub_desc}]"
        elif isinstance(val, list) and val:
            mut_list = copy.deepcopy(val)
            mut_list.append("\x00" * 50)
            return mut_list, "StructureAlteration [ArrayOverflow]"
        else:
            return None, "StructureAlteration [NullPayload]"


def run_target(target: str, payload: Any) -> Tuple[bool, str]:
    """Runs the target against payload. Returns (is_crash, error_description)."""
    if not target:
        if payload is None or payload == "\x00":
            return True, "Simulated crash on null payload"
        return False, "Target executed successfully"

    payload_str = json.dumps(payload) if not isinstance(payload, str) else payload

    if target.endswith(".py") and os.path.exists(target):
        cmd = [sys.executable, target, payload_str]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc.returncode != 0:
                err_msg = proc.stderr.strip() or f"Non-zero exit code: {proc.returncode}"
                return True, err_msg
            return False, proc.stdout
        except subprocess.TimeoutExpired:
            return True, "Execution timed out (>5s)"
        except Exception as e:
            return True, f"Subprocess invocation exception: {str(e)}"
    else:
        cmd_str = f"{target} '{payload_str}'"
        try:
            proc = subprocess.run(
                cmd_str,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc.returncode != 0:
                err_msg = proc.stderr.strip() or f"Non-zero exit code: {proc.returncode}"
                return True, err_msg
            return False, proc.stdout
        except subprocess.TimeoutExpired:
            return True, "Execution timed out (>5s)"
        except Exception as e:
            return True, f"Shell execution error: {str(e)}"


def run_fuzzer(target: str, num_mutations: int, seed_input_arg: str, dry_run: bool = False) -> dict:
    """Executes the fuzzing loop."""
    seeds = load_seeds(seed_input_arg)
    crashes_found = 0
    failed_seeds = []

    if dry_run:
        return {
            "total_mutations": num_mutations,
            "crashes_found": 0,
            "failed_seeds": ["[DRY-RUN] Fuzzing simulation initialized"],
            "risk_score": 0.0
        }

    for i in range(num_mutations):
        base_seed = random.choice(seeds)
        mutated_payload, mutation_desc = mutate_val(base_seed)
        
        is_crash, err_desc = run_target(target, mutated_payload)
        if is_crash:
            crashes_found += 1
            failure_entry = f"Mutant #{i+1} [{mutation_desc}]: {err_desc.splitlines()[0] if err_desc else 'Unknown crash'}"
            if len(failed_seeds) < 10:
                failed_seeds.append(failure_entry)

    risk_score = round(min(1.0, (crashes_found / max(1, num_mutations)) * 1.5), 2)

    return {
        "total_mutations": num_mutations,
        "crashes_found": crashes_found,
        "failed_seeds": failed_seeds,
        "risk_score": risk_score
    }


def main():
    parser = argparse.ArgumentParser(
        description="Animal-Instinct Genetic Fuzzer & Mutation Tester"
    )
    parser.add_argument(
        "--target", "--target-script",
        type=str,
        dest="target",
        default="",
        help="Target script path or execution command to fuzz"
    )
    parser.add_argument(
        "--mutations",
        type=int,
        default=20,
        help="Total number of genetic mutation iterations (default: 20)"
    )
    parser.add_argument(
        "--seed-inputs", "--seed",
        type=str,
        dest="seed_inputs",
        default="",
        help="Directory path, JSON file path, or raw JSON string of seed inputs"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON report"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview generated mutations without executing target script"
    )

    args = parser.parse_args()

    result = run_fuzzer(args.target, args.mutations, args.seed_inputs, args.dry_run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
