# Animal-Instinct Genetic Fuzzing & Mutation Guide

## 1. Overview
The Animal-Instinct Skill introduces genetic fuzzing and automated mutation testing to evaluate code robustness under extreme, malformed, or hostile input conditions. It probes edge cases, unhandled exceptions, type-mismatch vulnerabilities, and crash conditions, outputting a structured risk score.

---

## 2. Fuzzing Mechanics & Mutation Matrix

### 2.1 Genetic Mutation Strategies
1. **Type Flipping**: Switches primitive data types (e.g. integer → string, string → dict, array → null).
2. **Boundary Values**: Injects integer minimums/maximums (`2^31 - 1`, `2^63 - 1`), negative limits, `NaN`, `Infinity`, extreme floats (`1e308`).
3. **Null & Buffer Injection**: Injects null bytes `\x00`, oversized buffer strings (10,000+ chars), path traversal strings, injection syntax.
4. **Structural Alterations**: Deletes required JSON keys, injects unexpected extra keys, or corrupts nested list structures.

---

## 3. CLI Helper: `mutation_fuzzer.py`

### 3.1 CLI Arguments
- `--target <path_or_cmd>`: Target Python script or shell command to fuzz (Required).
- `--mutations <int>`: Total number of genetic mutations to test (Default: 20).
- `--seed-inputs <dir_or_json>`: Seed input directory, JSON file, or raw JSON string (Default: Standard seed primitives).

### 3.2 Command Line Usage Examples

#### Run default fuzzing pass on target script:
```bash
python3 scripts/mutation_fuzzer.py --target "src/parser.py" --mutations 50
```

#### Run fuzzing with custom seed directory:
```bash
python3 scripts/mutation_fuzzer.py --target "src/api_handler.py" --mutations 100 --seed-inputs "tests/seeds/"
```

#### Run fuzzing with inline seed JSON:
```bash
python3 scripts/mutation_fuzzer.py --target "src/cli.py" --mutations 20 --seed-inputs '{"user_id": 1, "role": "admin"}'
```

---

## 4. Output Schema & Risk Scoring

### 4.1 JSON Output Schema
```json
{
  "total_mutations": 20,
  "crashes_found": 2,
  "failed_seeds": [
    "Mutant #4 [TypeFlip [NumberToString]]: Non-zero exit code: 1",
    "Mutant #12 [NullByteInjection]: Execution timed out (>5s)"
  ],
  "risk_score": 0.15
}
```

### 4.2 Risk Score Calculation
$$\text{Risk Score} = \min\left(1.0, \frac{\text{Crashes Found}}{\text{Total Mutations}} \times 1.5\right)$$

- **0.00 – 0.09**: Low Risk (High stability and error resilience).
- **0.10 – 0.29**: Moderate Risk (Identified unhandled edge cases; patching recommended).
- **0.30 – 1.00**: High Risk (Frequent crash conditions; mandatory input sanitization & exception handling required).
