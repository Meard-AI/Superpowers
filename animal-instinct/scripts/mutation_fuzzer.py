#!/usr/bin/env python3
"""
mutation_fuzzer.py - Animal-Instinct Mutation Fuzzer

Mutates seed inputs, runs them against a target, and reports reproducible findings.

Three properties this fuzzer guarantees, because a fuzzer without them is not useful:
  1. REPRODUCIBLE — the RNG seed is chosen (or given), reported, and replaying the
     same --random-seed regenerates the identical mutation sequence.
  2. PAYLOAD-RECORDING — every finding carries the exact payload that produced it,
     so a crash can be replayed by hand.
  3. NO SHELL — the target is executed via an argv list with shell=False. Building
     a shell string around fuzz payloads means the fuzzer executes its own payloads;
     that is command injection into the host, not a test of the target.

A non-zero exit code is NOT automatically a crash. A CLI that rejects garbage with
exit 1 is behaving correctly. Only signals, unhandled tracebacks, and timeouts are
counted toward the risk score.

This is a blackbox random fuzzer. It has no coverage feedback and no test-case
minimization; for deeper work use a coverage-guided engine (Atheris) or a
property-based tester (Hypothesis).
"""

import sys
import os
import json
import argparse
import random
import shlex
import subprocess
import copy
from pathlib import Path
from typing import Any, Dict, List, Tuple

DEFAULT_SEEDS = [
    {"name": "test_input", "value": 42, "enabled": True, "tags": ["unit", "test"]},
    "Standard string payload for testing",
    100,
    [1, 2, 3, 4, 5],
]

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
    "../../../../etc/passwd",
]

MUTATIONS_NUMBERS = [
    0, -1, 2147483647, -2147483648, 9223372036854775807,
    1e308, -1e308, float("nan"), float("inf"), -float("inf"),
]

OUTCOME_OK = "ok"
OUTCOME_REJECTED = "rejected"
OUTCOME_CRASH = "crash"
OUTCOME_TIMEOUT = "timeout"
OUTCOME_HARNESS_ERROR = "harness_error"
OUTCOME_UNENCODABLE = "unencodable"


def load_seeds(seed_input_arg: str) -> List[Any]:
    if not seed_input_arg:
        return copy.deepcopy(DEFAULT_SEEDS)

    path = Path(seed_input_arg).expanduser()
    if path.exists():
        if path.is_dir():
            seeds = []
            for file_path in sorted(path.glob("*")):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        try:
                            seeds.append(json.loads(content))
                        except Exception:
                            seeds.append(content)
                    except Exception:
                        pass
            return seeds if seeds else copy.deepcopy(DEFAULT_SEEDS)
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                try:
                    parsed = json.loads(content)
                    return parsed if isinstance(parsed, list) else [parsed]
                except Exception:
                    return [content]
            except Exception:
                return copy.deepcopy(DEFAULT_SEEDS)

    try:
        parsed = json.loads(seed_input_arg)
        return parsed if isinstance(parsed, list) else [parsed]
    except Exception:
        return [seed_input_arg]


def mutate_val(val: Any, rng: random.Random) -> Tuple[Any, str]:
    """Apply one mutation, derived from `val` wherever the mutation class allows."""
    mutation_type = rng.choice([
        "type_flip", "boundary_value", "null_injection",
        "structure_alteration", "extreme_string", "splice",
    ])

    if mutation_type == "type_flip":
        if isinstance(val, bool):
            return (not val), "TypeFlip [BoolNegate]"
        if isinstance(val, (int, float)):
            return str(val), "TypeFlip [NumberToString]"
        if isinstance(val, str):
            return 999999, "TypeFlip [StringToInt]"
        if isinstance(val, list):
            return {"mutated_dict": True}, "TypeFlip [ArrayToDict]"
        if isinstance(val, dict):
            return ["mutated_array"], "TypeFlip [DictToArray]"
        return None, "TypeFlip [ToNull]"

    if mutation_type == "boundary_value":
        num_mut = rng.choice(MUTATIONS_NUMBERS)
        # NaN/Inf are not representable in strict JSON; carry them as strings so
        # the serialized payload stays valid and replayable.
        if isinstance(num_mut, float) and (num_mut != num_mut or abs(num_mut) == float("inf")):
            return str(num_mut), f"BoundaryValue [{num_mut}]"
        return num_mut, f"BoundaryValue [{num_mut}]"

    if mutation_type == "null_injection":
        return "\x00", "NullByteInjection"

    if mutation_type == "extreme_string":
        st_mut = rng.choice(MUTATIONS_STRINGS)
        return st_mut, f"ExtremeString [{st_mut[:15]!r}]"

    if mutation_type == "splice":
        # Genuinely derived from the input: splice an extreme string into it.
        inject = rng.choice(MUTATIONS_STRINGS)
        if isinstance(val, str) and val:
            cut = rng.randrange(len(val) + 1)
            return val[:cut] + inject + val[cut:], f"Splice [at {cut}]"
        if isinstance(val, list) and val:
            spliced = copy.deepcopy(val)
            spliced.insert(rng.randrange(len(spliced) + 1), inject)
            return spliced, "Splice [ListInsert]"
        if isinstance(val, dict) and val:
            spliced = copy.deepcopy(val)
            spliced[rng.choice(list(spliced.keys()))] = inject
            return spliced, "Splice [DictValue]"
        return inject, "Splice [Replace]"

    if isinstance(val, dict) and val:
        mut_dict = copy.deepcopy(val)
        action = rng.choice(["delete_key", "add_key", "mutate_key"])
        if action == "delete_key":
            key = rng.choice(list(mut_dict.keys()))
            del mut_dict[key]
            return mut_dict, f"StructureAlteration [DeletedKey:{key}]"
        if action == "add_key":
            mut_dict["__unexpected_fuzz_key__"] = "\x00" * 100
            return mut_dict, "StructureAlteration [AddedUnexpectedKey]"
        key = rng.choice(list(mut_dict.keys()))
        mut_dict[key], sub = mutate_val(mut_dict[key], rng)
        return mut_dict, f"StructureAlteration [ModKey:{key}:{sub}]"

    if isinstance(val, list) and val:
        mut_list = copy.deepcopy(val)
        mut_list.append("\x00" * 50)
        return mut_list, "StructureAlteration [ArrayOverflow]"

    return None, "StructureAlteration [NullPayload]"


def build_argv(target: str, payload_str: str) -> List[str]:
    """Build an argv list. No shell, so payloads can never become commands."""
    target_path = Path(target).expanduser()
    if target.endswith(".py") and target_path.exists():
        return [sys.executable, str(target_path), payload_str]
    return shlex.split(target) + [payload_str]


def classify(returncode: int, stderr: str) -> str:
    """Distinguish a real crash from a correct rejection.

    Graceful rejection of malformed input (exit 1/2 with no traceback) is the
    target working as intended and must not inflate the risk score.
    """
    if returncode < 0:
        return OUTCOME_CRASH  # killed by a signal (SIGSEGV, SIGABRT, ...)
    if "Traceback (most recent call last)" in stderr:
        return OUTCOME_CRASH  # unhandled exception
    if returncode == 0:
        return OUTCOME_OK
    if returncode in (1, 2):
        return OUTCOME_REJECTED
    return OUTCOME_CRASH


def run_target(argv: List[str], timeout: float) -> Dict[str, Any]:
    # POSIX argv strings are NUL-terminated, so a payload containing \x00 cannot be
    # delivered this way at all. That is a harness limitation, not a target defect —
    # give it its own outcome so it never inflates or masks the risk score.
    if any("\x00" in a for a in argv):
        return {"outcome": OUTCOME_UNENCODABLE, "returncode": None,
                "detail": "Payload contains a NUL byte and cannot be passed via argv"}
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, shell=False)
    except subprocess.TimeoutExpired:
        return {"outcome": OUTCOME_TIMEOUT, "returncode": None,
                "detail": f"Execution exceeded {timeout}s"}
    except FileNotFoundError as e:
        return {"outcome": OUTCOME_HARNESS_ERROR, "returncode": None,
                "detail": f"Target not executable: {e}"}
    except Exception as e:
        return {"outcome": OUTCOME_HARNESS_ERROR, "returncode": None,
                "detail": f"Harness error: {e}"}

    outcome = classify(proc.returncode, proc.stderr or "")
    detail = (proc.stderr or "").strip().splitlines()
    return {
        "outcome": outcome,
        "returncode": proc.returncode,
        "detail": detail[-1] if detail else (f"exit {proc.returncode}"),
    }


def serialize_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError):
        return repr(payload)


def run_fuzzer(target: str, num_mutations: int, seed_input_arg: str,
               random_seed: int, timeout: float, dry_run: bool,
               max_findings: int) -> Dict[str, Any]:
    seeds = load_seeds(seed_input_arg)
    rng = random.Random(random_seed)

    report: Dict[str, Any] = {
        "status": "SUCCESS",
        "target": target,
        "random_seed": random_seed,
        "replay_hint": f"--random-seed {random_seed} --mutations {num_mutations}",
        "total_mutations": num_mutations,
        "seed_count": len(seeds),
        "timeout_seconds": timeout,
    }

    if dry_run:
        preview = []
        for i in range(num_mutations):
            base = rng.choice(seeds)
            mutated, desc = mutate_val(base, rng)
            preview.append({"index": i + 1, "mutation": desc,
                            "payload": serialize_payload(mutated)[:200]})
        report.update({"dry_run": True, "executed": False, "mutations": preview,
                       "crashes_found": 0, "risk_score": 0.0})
        return report

    counts = {OUTCOME_OK: 0, OUTCOME_REJECTED: 0, OUTCOME_CRASH: 0,
              OUTCOME_TIMEOUT: 0, OUTCOME_HARNESS_ERROR: 0, OUTCOME_UNENCODABLE: 0}
    findings: List[Dict[str, Any]] = []
    truncated = 0

    for i in range(num_mutations):
        base = rng.choice(seeds)
        mutated, desc = mutate_val(base, rng)
        payload_str = serialize_payload(mutated)
        result = run_target(build_argv(target, payload_str), timeout)
        counts[result["outcome"]] += 1

        if result["outcome"] in (OUTCOME_CRASH, OUTCOME_TIMEOUT, OUTCOME_HARNESS_ERROR,
                                 OUTCOME_UNENCODABLE):
            if len(findings) < max_findings:
                findings.append({
                    "index": i + 1,
                    "outcome": result["outcome"],
                    "mutation": desc,
                    "payload": payload_str[:2000],
                    "payload_truncated": len(payload_str) > 2000,
                    "returncode": result["returncode"],
                    "detail": result["detail"],
                })
            else:
                truncated += 1

    # Payloads that could not be delivered were never a test of the target, so they
    # are excluded from the denominator rather than diluting the risk score.
    executed = num_mutations - counts[OUTCOME_UNENCODABLE]
    crashes = counts[OUTCOME_CRASH] + counts[OUTCOME_TIMEOUT]
    report.update({
        "dry_run": False,
        "executed": True,
        "executed_count": executed,
        "outcomes": counts,
        "crashes_found": crashes,
        "findings": findings,
        "findings_truncated": truncated,
        "risk_score": round(crashes / executed, 3) if executed else 0.0,
        "risk_note": "risk_score counts only signals, unhandled tracebacks, and "
                     "timeouts. Graceful rejections (exit 1/2) are correct behaviour "
                     "and are excluded.",
    })
    if counts[OUTCOME_HARNESS_ERROR] == executed and executed > 0:
        report["status"] = "ERROR"
        report["error"] = "Every execution failed at the harness level; check the --target path."
    return report


def main():
    parser = argparse.ArgumentParser(description="Animal-Instinct Mutation Fuzzer")
    parser.add_argument("--target", "--target-script", type=str, dest="target", default="",
                        help="Target script path or executable command to fuzz (REQUIRED)")
    parser.add_argument("--mutations", type=int, default=20,
                        help="Number of mutation iterations (default: 20)")
    parser.add_argument("--seed-inputs", "--corpus", type=str, dest="seed_inputs", default="",
                        help="Directory, JSON file, or raw JSON string of seed inputs")
    parser.add_argument("--random-seed", type=int, default=None,
                        help="RNG seed for reproducible runs (default: random, always reported)")
    parser.add_argument("--timeout", type=float, default=5.0,
                        help="Per-execution timeout in seconds (default: 5)")
    parser.add_argument("--max-findings", type=int, default=25,
                        help="Maximum findings recorded (default: 25)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON report")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate and print mutations without executing the target")

    args = parser.parse_args()

    # A fuzzer with no target used to fabricate 'Simulated crash' findings in the
    # same shape as a real report. Refuse instead.
    if not args.target and not args.dry_run:
        err = {"status": "ERROR",
               "error": "--target is required. Refusing to emit a report without executing anything."}
        print(json.dumps(err, indent=2) if args.json else f"Error: {err['error']}",
              file=None if args.json else sys.stderr)
        sys.exit(2)

    random_seed = args.random_seed if args.random_seed is not None \
        else random.SystemRandom().randrange(2**31)

    report = run_fuzzer(args.target, args.mutations, args.seed_inputs,
                        random_seed, args.timeout, args.dry_run, args.max_findings)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"[{report['status']}] target={report['target'] or '(none)'} "
              f"seed={report['random_seed']} mutations={report['total_mutations']}")
        print(f"Replay with: --random-seed {report['random_seed']}")
        if report.get("dry_run"):
            for m in report["mutations"]:
                print(f"  #{m['index']} {m['mutation']}: {m['payload'][:100]}")
        else:
            print(f"Outcomes: {report['outcomes']}")
            print(f"Risk score: {report['risk_score']} ({report['crashes_found']} crash/timeout)")
            for f in report["findings"]:
                print(f"  #{f['index']} [{f['outcome']}] {f['mutation']} rc={f['returncode']}")
                print(f"      payload: {f['payload'][:120]!r}")
                print(f"      detail : {f['detail']}")
            if report["findings_truncated"]:
                print(f"  ... {report['findings_truncated']} further finding(s) not recorded "
                      f"(raise --max-findings)")

    sys.exit(1 if report.get("crashes_found") else 0)


if __name__ == "__main__":
    main()
