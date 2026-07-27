# Animal Instinct — Mutation Fuzzing Guide

## 1. Overview
Animal Instinct mutates seed inputs and feeds them to a target CLI or script, looking
for inputs the target does not survive.

It is a **blackbox random fuzzer**. It knows nothing about the target's internals and
receives no coverage feedback. That makes it cheap and dependency-free, and it is why
Section 6 tells you when to reach for a real fuzzing engine instead.

---

## 2. The Three Non-Negotiables

A fuzzer missing any of these produces findings you cannot act on.

### 2.1 Reproducibility
The RNG is seeded from `--random-seed`, or from `SystemRandom` and then **reported**.
Every report carries `random_seed` and a `replay_hint`. Same seed plus same mutation
count regenerates the identical sequence.

An unseeded fuzzer that finds a crash it cannot reproduce has found nothing.

### 2.2 Payload recording
Every finding stores the exact `payload` that produced it (truncated at 2000 chars,
with `payload_truncated` flagging when that happened). A mutation *description* alone
is not enough to reproduce a failure by hand.

### 2.3 No shell
The target is executed with an **argv list and `shell=False`**.

This matters more than it sounds. Building a shell string around fuzz payloads means
the fuzzer executes its own payloads. The built-in corpus contains
`'; DROP TABLE users; --` — under `shell=True` that unbalances the quoting and either
executes arbitrary commands on the host or produces a shell syntax error that gets
misreported as a crash *in the target*. Both were real v1 behaviours.

---

## 3. Outcome Classification

**A non-zero exit code is not a crash.** A CLI that rejects malformed input with exit 1
is behaving correctly; counting that as a crash makes the risk score meaningless
against any well-behaved tool.

| Outcome | Detection rule | Risk |
|---|---|---|
| `crash` | `returncode < 0` (signal), `Traceback (most recent call last)` in stderr, or `returncode >= 3` | **yes** |
| `timeout` | Exceeded `--timeout` | **yes** |
| `rejected` | `returncode` 1 or 2, no traceback | no |
| `ok` | `returncode == 0` | no |
| `harness_error` | Target not found or not executable | no |
| `unencodable` | Payload contains a NUL byte | no |

`risk_score = (crash + timeout) / executed_count`, where `executed_count` excludes
`unencodable` payloads — those were never delivered to the target, so counting them
would dilute the score with work that never happened.

### 3.1 The NUL-byte limitation
POSIX argv strings are NUL-terminated, so a payload containing `\x00` cannot be passed
as a command-line argument at all. The `null_injection` and `extreme_string` primitives
both generate such payloads. They are reported as `unencodable` rather than silently
counted as a pass, a crash, or a harness error.

To actually exercise NUL handling, fuzz through stdin or a file with a wrapper script
as `--target`.

---

## 4. Mutation Primitives

| Type | Derived from input? | Effect |
|---|---|---|
| `type_flip` | yes | int↔str, list↔dict, bool negation |
| `boundary_value` | no | Extremes: 0, ±2³¹, ±2⁶³, ±1e308, NaN, ±Inf |
| `null_injection` | no | Bare NUL byte |
| `extreme_string` | no | Empty, 10k chars, NULs, SQL/XSS/format-string payloads, CJK, traversal |
| `splice` | **yes** | Injects an extreme string *into* the seed at a random offset |
| `structure_alteration` | yes | Delete/add/mutate dict keys, overflow lists |

`splice` and `type_flip` derive from the seed; the others are constant injections.
A corpus that resembles real input makes the derived mutations far more productive —
supply one with `--seed-inputs`.

### 4.1 NaN / Infinity handling
These are not representable in strict JSON, so they are carried as strings. The
serialized payload therefore stays valid and replayable.

---

## 5. Seed Corpus

`--seed-inputs` (alias `--corpus`) accepts:

| Form | Behaviour |
|---|---|
| Directory | Every file loaded; JSON parsed, otherwise raw text |
| JSON file | A list becomes the corpus; a scalar becomes a single seed |
| Raw JSON string | Parsed inline |
| Anything else | Used as one literal string seed |

> **Naming note:** `--seed-inputs` is the *corpus*. The RNG seed is `--random-seed`.
> They are separate flags and confusing them is the most common mistake here.

---

## 6. When to Use Something Else

| Need | Tool |
|---|---|
| Coverage-guided exploration | **Atheris** (libFuzzer for Python) — mutates the best-performing input rather than sampling randomly |
| Minimal reproducer | **Hypothesis** — shrinks a failure to the smallest input that still fails |
| Invariant testing | **Hypothesis** — asserts properties across a structured domain |
| Native memory bugs | **AFL++** / libFuzzer against a C/C++ harness |

Animal Instinct fits where those do not: zero dependencies, fuzzing an opaque CLI
through its argv interface, and quick robustness smoke-checks in CI.

---

## 7. Worked Example

```bash
# Explore
python3 scripts/mutation_fuzzer.py --target "src/cli.py" --mutations 200 \
  --seed-inputs '{"user_id": 1, "role": "admin"}' --json > report.json

# Reproduce finding #47
python3 scripts/mutation_fuzzer.py --target "src/cli.py" --mutations 200 \
  --random-seed "$(python3 -c "import json;print(json.load(open('report.json'))['random_seed'])")" --json
```

Exit code `1` from the first command is a usable CI gate: it fires on crashes and
timeouts, and stays `0` when the target merely rejects bad input.

---

## 8. Interface Assumption
Payloads are delivered as a **single positional argument**. A target reading from
stdin, or taking its input via a named flag, needs a small wrapper script as
`--target`. Fuzzing `src/cli.py` directly only exercises `argv[1]`.
