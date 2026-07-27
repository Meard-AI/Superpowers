#!/usr/bin/env python3
"""
Regression suite for the Agent Superpowers skills.

Every test here corresponds to a defect found in the v1 audit. The point is not
coverage for its own sake — it is that each of these behaviours was once wrong in a
way that silently produced a confident, incorrect answer.

Stdlib only. Run with:
    python3 -m unittest discover -s tests -v
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

ROUTER = REPO / "ultra-instinct" / "scripts" / "reflex_router.py"
CLONER = REPO / "copy-ability" / "scripts" / "trajectory_cloner.py"
ENFORCER = REPO / "invisible-attacks" / "scripts" / "sandbox_enforcer.py"
ADAPTER = REPO / "mastery" / "scripts" / "context_adapter.py"
ANTI_STALL = REPO / "heat-mode" / "scripts" / "anti_stall.py"
CQC_EXEC = REPO / "cqc" / "scripts" / "cqc_executor.py"
VALIDATOR = REPO / "cqc" / "scripts" / "boundary_validator.py"

ALL_SCRIPTS = [ROUTER, CLONER, ENFORCER, ADAPTER, ANTI_STALL, CQC_EXEC, VALIDATOR]
SKILL_DIRS = ["ultra-instinct", "copy-ability", "invisible-attacks", "mastery",
              "heat-mode", "cqc", "animal-instinct"]
FUZZER = REPO / "animal-instinct" / "scripts" / "mutation_fuzzer.py"


class SkillTestCase(unittest.TestCase):
    """Base: isolated temp dir and isolated skill state per test."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="superpowers-test-"))
        self.state = self.tmp / "state"
        self.env = {**os.environ, "AGENT_SUPERPOWERS_STATE": str(self.state)}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_script(self, script, *args, expect=None, stdin_data=None):
        proc = subprocess.run(
            [sys.executable, str(script), *[str(a) for a in args]],
            capture_output=True, text=True, cwd=str(self.tmp), env=self.env, timeout=60,
            # Never inherit the runner's stdin. Inheriting it made the suite's own
            # result depend on how it was launched: from a terminal stdin is a tty
            # and scripts skip it, but under an agent harness it is an open pipe and
            # every stdin-reading script blocked forever.
            input=stdin_data if stdin_data is not None else "",
        )
        if expect is not None:
            self.assertEqual(proc.returncode, expect,
                             f"{script.name} exit {proc.returncode} != {expect}\n"
                             f"stdout: {proc.stdout}\nstderr: {proc.stderr}")
        return proc

    def json_out(self, proc):
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"Expected JSON, got:\n{proc.stdout}\n{proc.stderr}")


# ---------------------------------------------------------------- ultra-instinct

class TestReflexRouter(SkillTestCase):

    def classify(self, query, cache=None):
        args = ["--query", query, "--json"]
        if cache:
            args += ["--cache-file", str(cache)]
        return self.json_out(self.run_script(ROUTER, *args, expect=0))

    def test_reasoning_intent_vetoes_route_match(self):
        """'explain why our eslint config is failing' must not run a linter."""
        result = self.classify("explain why our eslint config is failing and refactor it")
        self.assertEqual(result["tier"], "reasoning")
        self.assertIsNone(result["matched_command"])

    def test_reasoning_keywords_each_veto(self):
        for word in ["design", "why", "refactor", "compare", "review", "investigate"]:
            with self.subTest(word=word):
                self.assertEqual(self.classify(f"{word} the lint setup")["tier"], "reasoning")

    def test_compound_command_vetoes(self):
        self.assertEqual(self.classify("git status && npm test")["tier"], "reasoning")

    def test_npm_test_does_not_route_to_python(self):
        result = self.classify("npm test")
        self.assertEqual(result["tier"], "reflex")
        self.assertEqual(result["matched_command"], "npm test")

    def test_git_diff_does_not_route_to_git_status(self):
        result = self.classify("git diff")
        self.assertEqual(result["tier"], "reflex")
        self.assertIn("diff", result["matched_command"])

    def test_reflex_verdict_always_carries_a_command(self):
        """A reflex tier with no command would tell the agent to execute nothing."""
        for query in ["status", "check", "info", "list", "npm test", "git diff", "pytest"]:
            with self.subTest(query=query):
                result = self.classify(query)
                if result["tier"] == "reflex":
                    self.assertTrue(result["matched_command"])

    def test_invalid_regex_rejected_at_add_time(self):
        cache = self.tmp / "routes.json"
        cache.write_text("[]")
        proc = self.run_script(ROUTER, "--cache-file", cache, "--add-route", "(unclosed",
                               "--command", "echo hi", "--json", expect=1)
        self.assertEqual(self.json_out(proc)["status"], "ERROR")

    def test_corrupt_route_does_not_break_classification(self):
        """A bad pattern reaching the file must be skipped, never raised."""
        cache = self.tmp / "routes.json"
        cache.write_text(json.dumps([
            {"pattern": "(broken", "command": "x", "confidence": 0.9},
            {"pattern": r"(?i)^\s*git\s+diff\s*$", "command": "git diff --stat", "confidence": 0.95},
        ]))
        result = self.classify("git diff", cache=cache)
        self.assertEqual(result["matched_command"], "git diff --stat")

    def test_verify_reports_unusable_routes(self):
        cache = self.tmp / "routes.json"
        cache.write_text(json.dumps([
            {"pattern": "(broken", "command": "x", "confidence": 0.9},
            {"pattern": "^ok$", "command": "", "confidence": 0.9},
        ]))
        proc = self.run_script(ROUTER, "--cache-file", cache, "--verify", "--json", expect=1)
        data = self.json_out(proc)
        self.assertEqual(data["status"], "INVALID")
        self.assertEqual(len(data["problems"]), 2)

    def test_shipped_routes_are_all_valid(self):
        proc = self.run_script(ROUTER, "--verify", "--json", expect=0)
        self.assertEqual(self.json_out(proc)["status"], "SUCCESS")

    def test_shipped_routes_have_no_placeholder_commands(self):
        routes = json.loads((REPO / "ultra-instinct" / "references" / "reflex_routes.json").read_text())
        for route in routes:
            with self.subTest(pattern=route["pattern"]):
                self.assertNotIn(route["command"], ("sys_info", "TODO", ""))

    def test_shipped_routes_are_anchored(self):
        """Unanchored .*x.* patterns are the primary mis-routing source."""
        routes = json.loads((REPO / "ultra-instinct" / "references" / "reflex_routes.json").read_text())
        for route in routes:
            with self.subTest(pattern=route["pattern"]):
                self.assertIn("^", route["pattern"])
                self.assertIn("$", route["pattern"])


# ---------------------------------------------------------------------- heat-mode

class TestAntiStall(SkillTestCase):

    def test_documented_invocation_detects_stall(self):
        """The exact command in SKILL.md used to return 'nominal' with no actions."""
        proc = self.run_script(ANTI_STALL, "--error-log", "tool failed: connection refused",
                               "--consecutive-failures", "2", "--recommend", "--json", expect=0)
        data = self.json_out(proc)
        self.assertTrue(data["stall_detected"])
        self.assertTrue(data["suggested_actions"])

    def test_caller_reported_count_is_not_the_threshold(self):
        data = self.json_out(self.run_script(
            ANTI_STALL, "--consecutive-failures", "5", "--threshold", "2", "--json", expect=0))
        self.assertEqual(data["signals"]["caller_reported"], 5)
        self.assertEqual(data["threshold"], 2)
        self.assertTrue(data["stall_detected"])

    def test_below_threshold_is_nominal(self):
        data = self.json_out(self.run_script(
            ANTI_STALL, "--consecutive-failures", "1", "--threshold", "3", "--json", expect=0))
        self.assertFalse(data["stall_detected"])
        self.assertEqual(data["suggested_actions"], [])

    def test_recommend_forces_actions_below_threshold(self):
        data = self.json_out(self.run_script(
            ANTI_STALL, "--consecutive-failures", "1", "--threshold", "9",
            "--recommend", "--json", expect=0))
        self.assertFalse(data["stall_detected"])
        self.assertTrue(data["suggested_actions"])
        self.assertIn("note", data)

    def test_record_failure_persists_and_reset_clears(self):
        for _ in range(3):
            self.run_script(ANTI_STALL, "--record-failure", "--json", expect=0)
        data = self.json_out(self.run_script(ANTI_STALL, "--json", expect=0))
        self.assertEqual(data["signals"]["persisted"], 3)

        self.run_script(ANTI_STALL, "--reset", "--json", expect=0)
        data = self.json_out(self.run_script(ANTI_STALL, "--json", expect=0))
        self.assertEqual(data["signals"]["persisted"], 0)

    def test_state_lives_outside_the_skill_package(self):
        self.run_script(ANTI_STALL, "--record-failure", "--json", expect=0)
        self.assertTrue((self.state / "heat-mode.json").exists())
        self.assertFalse((REPO / "heat-mode" / ".agents").exists())

    def test_missing_log_path_is_an_error_not_phantom_text(self):
        proc = self.run_script(ANTI_STALL, "--log", "/no/such/file.log", "--json", expect=1)
        self.assertEqual(self.json_out(proc)["status"], "ERROR")

    def test_trailing_streak_stops_at_success(self):
        """A run of errors followed by a success is not a stall."""
        log = "error one\nerror two\nerror three\nall good now\n"
        data = self.json_out(self.run_script(ANTI_STALL, "--log", log, "--threshold", "2", "--json", expect=0))
        self.assertEqual(data["signals"]["log_streak"], 0)
        self.assertEqual(data["total_error_lines"], 3)

    def test_failure_classification(self):
        cases = [("JSONDecodeError while parsing schema", "json_format"),
                 ("permission denied waiting on prompt", "permission_timeout"),
                 ("deadlock: process stuck", "deadlock")]
        for log, expected in cases:
            with self.subTest(log=log):
                data = self.json_out(self.run_script(
                    ANTI_STALL, "--log", log, "--consecutive-failures", "3", "--json", expect=0))
                self.assertEqual(data["failure_class"], expected)


# --------------------------------------------------------------------------- cqc

class TestBoundary(SkillTestCase):

    def setUp(self):
        super().setUp()
        self.perimeter = self.tmp / "sib" / "app"
        self.sibling = self.tmp / "sib" / "app-secrets"
        self.faraway = self.tmp / "faraway"
        for d in (self.perimeter, self.sibling, self.faraway):
            d.mkdir(parents=True, exist_ok=True)
        (self.sibling / "creds.txt").write_text("secret")

    def test_sibling_prefix_is_not_inside_perimeter(self):
        """'/x/app-secrets'.startswith('/x/app') is True — containment must be component-wise."""
        proc = self.run_script(VALIDATOR, "--allowed-paths", self.perimeter,
                               "--check-path", self.sibling / "creds.txt", "--json", expect=1)
        self.assertEqual(self.json_out(proc)["status"], "BLOCKED")

    def test_command_referencing_sibling_is_blocked(self):
        proc = self.run_script(VALIDATOR, "--check-command", f"cat {self.sibling}/creds.txt",
                               "--perimeter-dir", self.perimeter, "--json", expect=1)
        self.assertEqual(self.json_out(proc)["status"], "BLOCKED")

    def test_quoted_path_is_detected(self):
        """A whitespace regex misses '> \"/abs/path\"'; shlex tokenization does not."""
        target = self.faraway / "escaped.txt"
        proc = self.run_script(CQC_EXEC, "--perimeter-dir", self.perimeter,
                               "--command", f'echo pwned > "{target}"', "--json", expect=2)
        data = self.json_out(proc)
        self.assertEqual(data["status"], "blocked")
        self.assertFalse(data["executed"])
        self.assertFalse(target.exists(), "blocked command must not have run")

    def test_escape_is_refused_by_default(self):
        target = self.faraway / "escaped2.txt"
        self.run_script(CQC_EXEC, "--perimeter-dir", self.perimeter,
                        "--command", f"echo x > {target}", "--json", expect=2)
        self.assertFalse(target.exists())

    def test_warn_only_permits_the_escape_explicitly(self):
        target = self.faraway / "escaped3.txt"
        self.run_script(CQC_EXEC, "--perimeter-dir", self.perimeter, "--warn-only",
                        "--command", f"echo x > {target}", "--json")
        self.assertTrue(target.exists(), "--warn-only should allow the override")

    def test_tilde_expansion_marked_undecidable(self):
        proc = self.run_script(CQC_EXEC, "--perimeter-dir", self.perimeter,
                               "--command", "cat ~/.ssh/config", "--dry-run", "--json")
        self.assertTrue(self.json_out(proc)["static_analysis"]["undecidable"])

    def test_dynamic_constructs_flagged(self):
        for cmd in ["echo $HOME", "echo $(whoami)", "eval ls", "cat `pwd`/x"]:
            with self.subTest(cmd=cmd):
                proc = self.run_script(CQC_EXEC, "--perimeter-dir", self.perimeter,
                                       "--command", cmd, "--dry-run", "--json")
                self.assertTrue(self.json_out(proc)["static_analysis"]["undecidable"])

    def test_in_perimeter_command_runs_clean(self):
        proc = self.run_script(CQC_EXEC, "--perimeter-dir", self.perimeter,
                               "--command", "echo hello > inside.txt", "--json", expect=0)
        data = self.json_out(proc)
        self.assertEqual(data["status"], "passed")
        self.assertTrue((self.perimeter / "inside.txt").exists())

    def test_watch_scope_is_disclosed(self):
        """Undetected regions must be stated, not implied clean."""
        proc = self.run_script(CQC_EXEC, "--perimeter-dir", self.perimeter,
                               "--command", "true", "--json", expect=0)
        data = self.json_out(proc)
        self.assertIn("watch_scope", data)
        self.assertIn("NOT monitored", data["watch_scope_note"])

    def test_child_exit_code_is_propagated(self):
        proc = self.run_script(CQC_EXEC, "--perimeter-dir", self.perimeter,
                               "--command", "exit 42", "--json")
        self.assertEqual(proc.returncode, 42)


# ------------------------------------------------------------- invisible-attacks

class TestSandboxEnforcer(SkillTestCase):

    def test_path_inside_root_allowed(self):
        (self.tmp / "ok.txt").write_text("x")
        self.run_script(ENFORCER, "--path", self.tmp / "ok.txt",
                        "--allowed-root", self.tmp, "--json", expect=0)

    def test_path_outside_root_denied(self):
        proc = self.run_script(ENFORCER, "--path", "/etc/passwd",
                               "--allowed-root", self.tmp, "--json", expect=1)
        self.assertFalse(self.json_out(proc)["allowed"])

    def test_sibling_prefix_denied(self):
        root = self.tmp / "app"
        root.mkdir()
        (self.tmp / "app-secrets").mkdir()
        proc = self.run_script(ENFORCER, "--path", self.tmp / "app-secrets" / "f.txt",
                               "--allowed-root", root, "--json", expect=1)
        self.assertFalse(self.json_out(proc)["allowed"])

    def test_queue_actually_executes(self):
        """v1 could enqueue and list but nothing ever ran a queued task."""
        marker = self.tmp / "ran.txt"
        self.run_script(ENFORCER, "--queue-speculative", f"touch {marker}",
                        "--allowed-root", self.tmp, "--json", expect=0)
        self.run_script(ENFORCER, "--run-queue", "--json", expect=0)
        for _ in range(50):
            if marker.exists():
                break
            time.sleep(0.1)
        self.assertTrue(marker.exists(), "queued task never executed")

    def test_check_leak_detects_a_live_process(self):
        """v1 returned a hardcoded SECURE and could never report a leak."""
        self.run_script(ENFORCER, "--queue-speculative", "sleep 5",
                        "--allowed-root", self.tmp, "--json", expect=0)
        self.run_script(ENFORCER, "--run-queue", "--json", expect=0)
        proc = self.run_script(ENFORCER, "--check-leak", "--json", expect=1)
        data = self.json_out(proc)
        self.assertTrue(data["leaks_detected"])
        self.assertEqual(data["status"], "LEAKS_DETECTED")

    def test_check_leak_clean_when_nothing_running(self):
        proc = self.run_script(ENFORCER, "--check-leak", "--json", expect=0)
        self.assertFalse(self.json_out(proc)["leaks_detected"])

    def test_check_leak_discloses_its_scope(self):
        proc = self.run_script(ENFORCER, "--check-leak", "--json", expect=0)
        self.assertIn("scope_note", self.json_out(proc))

    def test_task_ids_do_not_collide_after_clear(self):
        self.run_script(ENFORCER, "--queue-speculative", "true", "--json", expect=0)
        self.run_script(ENFORCER, "--clear-queue", "--json", expect=0)
        proc = self.run_script(ENFORCER, "--queue-speculative", "true", "--json", expect=0)
        self.assertEqual(self.json_out(proc)["task_id"], "spec-001")

    def test_state_outside_the_package(self):
        self.run_script(ENFORCER, "--queue-speculative", "true", "--json", expect=0)
        self.assertTrue((self.state / "speculative_queue.json").exists())
        self.assertFalse((REPO / "invisible-attacks" / ".agents").exists())

    def test_run_cmd_declares_it_is_not_isolation(self):
        proc = self.run_script(ENFORCER, "--run-cmd", "echo hi",
                               "--allowed-root", self.tmp, "--json", expect=0)
        self.assertIn("none", self.json_out(proc)["isolation"])


# -------------------------------------------------------------- animal-instinct

class TestMutationFuzzer(SkillTestCase):

    def _write(self, name, body):
        path = self.tmp / name
        path.write_text(textwrap.dedent(body))
        return path

    def test_missing_target_refuses_instead_of_fabricating(self):
        """v1 emitted 'Simulated crash' findings shaped exactly like real ones."""
        proc = self.run_script(FUZZER, "--mutations", "5", "--json", expect=2)
        self.assertEqual(self.json_out(proc)["status"], "ERROR")

    def test_graceful_rejection_is_not_a_crash(self):
        target = self._write("graceful.py", """
            import sys
            try:
                int(sys.argv[1]); print("ok")
            except Exception:
                sys.stderr.write("bad input\\n"); sys.exit(1)
        """)
        proc = self.run_script(FUZZER, "--target", target, "--mutations", "20",
                               "--random-seed", "7", "--json", expect=0)
        data = self.json_out(proc)
        self.assertEqual(data["outcomes"]["crash"], 0)
        self.assertEqual(data["risk_score"], 0.0)
        self.assertGreater(data["outcomes"]["rejected"], 0)

    def test_real_crash_is_detected_with_payload(self):
        target = self._write("crashy.py", """
            import sys
            print(len(sys.argv[1]) / 0)
        """)
        proc = self.run_script(FUZZER, "--target", target, "--mutations", "5",
                               "--random-seed", "7", "--json", expect=1)
        data = self.json_out(proc)
        self.assertGreater(data["outcomes"]["crash"], 0)
        finding = data["findings"][0]
        self.assertEqual(finding["outcome"], "crash")
        self.assertIn("payload", finding)
        self.assertIn("ZeroDivisionError", finding["detail"])

    def test_same_seed_is_reproducible(self):
        a = self.run_script(FUZZER, "--dry-run", "--mutations", "8", "--random-seed", "42", "--json")
        b = self.run_script(FUZZER, "--dry-run", "--mutations", "8", "--random-seed", "42", "--json")
        self.assertEqual(self.json_out(a)["mutations"], self.json_out(b)["mutations"])

    def test_seed_is_reported_when_not_supplied(self):
        proc = self.run_script(FUZZER, "--dry-run", "--mutations", "3", "--json", expect=0)
        self.assertIsInstance(self.json_out(proc)["random_seed"], int)

    def test_dry_run_lists_actual_mutations(self):
        proc = self.run_script(FUZZER, "--dry-run", "--mutations", "4",
                               "--random-seed", "1", "--json", expect=0)
        data = self.json_out(proc)
        self.assertEqual(len(data["mutations"]), 4)
        self.assertFalse(data["executed"])

    def test_payload_cannot_become_a_shell_command(self):
        """The built-in corpus contains "'; DROP TABLE users; --"."""
        marker = self.tmp / "PWNED.txt"
        corpus = json.dumps([f"'; touch {marker}; echo '"])
        self.run_script(FUZZER, "--target", "echo", "--mutations", "15",
                        "--random-seed", "3", "--seed-inputs", corpus, "--json")
        self.assertFalse(marker.exists(), "fuzz payload executed as a shell command")

    def test_timeout_counts_as_a_finding(self):
        target = self._write("hang.py", """
            import time
            time.sleep(30)
        """)
        proc = self.run_script(FUZZER, "--target", target, "--mutations", "4",
                               "--random-seed", "1", "--timeout", "1", "--json", expect=1)
        self.assertGreater(self.json_out(proc)["outcomes"]["timeout"], 0)

    def test_nul_payload_is_unencodable_not_a_crash(self):
        """POSIX argv cannot carry a NUL byte; that is a harness limit, not a defect."""
        target = self._write("echoer.py", """
            import sys
            print(sys.argv[1][:10])
        """)
        proc = self.run_script(FUZZER, "--target", target, "--mutations", "30",
                               "--random-seed", "5", "--json")
        data = self.json_out(proc)
        self.assertGreater(data["outcomes"]["unencodable"], 0)
        self.assertEqual(data["outcomes"]["crash"], 0)
        self.assertEqual(data["risk_score"], 0.0)


# ----------------------------------------------------------------- copy-ability

class TestTrajectoryCloner(SkillTestCase):

    def _log(self):
        path = self.tmp / "sess.log"
        path.write_text("$ git status\n modified: a.txt\n modified: b.txt\n"
                        "$ npm build\nbuilt ok\n$ npm build\nbuilt ok\n")
        return path

    def test_output_lines_are_not_merged_into_commands(self):
        """v1 joined every following line onto the command, making one mega-step."""
        proc = self.run_script(CLONER, "--log", self._log(), "--name", "t",
                               "--output-dir", self.tmp / "out", "--json", expect=0)
        steps = self.json_out(proc)["extracted_steps"]
        self.assertEqual(steps, ["git status", "npm build"])

    def test_repeated_commands_collapse(self):
        proc = self.run_script(CLONER, "--log", self._log(), "--name", "t",
                               "--output-dir", self.tmp / "out2", "--json", expect=0)
        self.assertEqual(self.json_out(proc)["extracted_steps"].count("npm build"), 1)

    def test_description_cannot_inject_frontmatter(self):
        out = self.tmp / "out3"
        self.run_script(CLONER, "--log", self._log(), "--name", "t", "--output-dir", out,
                        "--description", "benign\nallowed-tools:\n  - EXECUTE_ANYTHING",
                        "--json", expect=0)
        content = (out / "SKILL.md").read_text()
        frontmatter = content.split("---")[1]
        self.assertNotIn("EXECUTE_ANYTHING\n", frontmatter.replace("\\n", "\n").split("description:")[0])
        # The payload must survive only as an escaped scalar on the description line.
        desc_line = [l for l in frontmatter.splitlines() if l.startswith("description:")][0]
        self.assertIn("\\n", desc_line)

    def test_refuses_to_overwrite(self):
        out = self.tmp / "out4"
        out.mkdir()
        (out / "SKILL.md").write_text("PRECIOUS")
        self.run_script(CLONER, "--log", self._log(), "--name", "t",
                        "--output-dir", out, "--json", expect=3)
        self.assertEqual((out / "SKILL.md").read_text(), "PRECIOUS")

    def test_force_permits_overwrite(self):
        out = self.tmp / "out5"
        out.mkdir()
        (out / "SKILL.md").write_text("PRECIOUS")
        self.run_script(CLONER, "--log", self._log(), "--name", "t",
                        "--output-dir", out, "--force", "--json", expect=0)
        self.assertNotIn("PRECIOUS", (out / "SKILL.md").read_text())

    def test_allowed_root_constrains_output(self):
        proc = self.run_script(CLONER, "--log", self._log(), "--output-dir", "/etc",
                               "--allowed-root", self.tmp, "--json", expect=1)
        self.assertIn("outside allowed root", self.json_out(proc)["error"])

    def test_empty_extraction_warns_rather_than_inventing(self):
        log = self.tmp / "plain.log"
        log.write_text("just some prose\nno commands here\n")
        proc = self.run_script(CLONER, "--log", log, "--name", "t",
                               "--output-dir", self.tmp / "out6", "--json", expect=0)
        self.assertIn("warning", self.json_out(proc))

    def test_generated_skill_has_valid_frontmatter(self):
        out = self.tmp / "out7"
        self.run_script(CLONER, "--log", self._log(), "--name", "My Skill!",
                        "--output-dir", out, "--json", expect=0)
        content = (out / "SKILL.md").read_text()
        self.assertTrue(content.startswith("---\n"))
        self.assertIn("name: my-skill", content)


# ---------------------------------------------------------------------- mastery

class TestContextAdapter(SkillTestCase):

    def test_standard_vocabulary_is_default(self):
        data = self.json_out(self.run_script(ADAPTER, "--stage", "build", "--json", expect=0))
        self.assertEqual(data["allowed_tools"], ["Read", "Edit", "Write", "Bash"])

    def test_antigravity_vocabulary(self):
        data = self.json_out(self.run_script(ADAPTER, "--stage", "build",
                                             "--tool-vocabulary", "antigravity", "--json", expect=0))
        self.assertIn("replace_file_content", data["allowed_tools"])

    def test_all_stage_aliases_resolve(self):
        for alias, canonical in [("plan", "planning"), ("build", "building"),
                                 ("audit", "auditing"), ("format", "refactoring"),
                                 ("planning", "planning"), ("refactoring", "refactoring")]:
            with self.subTest(alias=alias):
                data = self.json_out(self.run_script(ADAPTER, "--stage", alias, "--json", expect=0))
                self.assertEqual(data["canonical_stage"], canonical)

    def test_unknown_stage_errors(self):
        proc = self.run_script(ADAPTER, "--stage", "nonsense", "--json", expect=1)
        self.assertEqual(self.json_out(proc)["status"], "ERROR")

    def test_advisory_nature_is_declared(self):
        data = self.json_out(self.run_script(ADAPTER, "--stage", "plan", "--json", expect=0))
        self.assertIn("advisory", data["enforcement"])


# ---------------------------------------------------- adversarial / robustness

class TestAdversarial(SkillTestCase):
    """Attacks and malformed inputs, not happy paths.

    Everything here was found by trying to break the fixed code, not by
    confirming it worked.
    """

    # --- ReDoS -------------------------------------------------------------

    def test_catastrophic_regex_is_bounded(self):
        """A nested-quantifier route pinned the CPU for 24s before the budget."""
        cache = self.tmp / "redos.json"
        cache.write_text(json.dumps([
            {"pattern": "^(a+)+$", "command": "echo x", "confidence": 0.9}]))
        started = time.monotonic()
        proc = self.run_script(ROUTER, "--cache-file", cache,
                               "--query", "a" * 40 + "!", "--json", expect=0)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 10, "route matching was not bounded")
        data = self.json_out(proc)
        self.assertEqual(data["tier"], "reasoning")
        self.assertEqual(data.get("timed_out_pattern"), "^(a+)+$")

    def test_nested_quantifier_rejected_at_add_time(self):
        cache = self.tmp / "r.json"
        cache.write_text("[]")
        proc = self.run_script(ROUTER, "--cache-file", cache, "--add-route", "^(x+)+$",
                               "--command", "ls", "--json", expect=1)
        self.assertIn("nested quantifier", self.json_out(proc)["error"])

    def test_verify_flags_nested_quantifier_on_disk(self):
        cache = self.tmp / "r.json"
        cache.write_text(json.dumps([
            {"pattern": "^(a+)+$", "command": "ls", "confidence": 0.9}]))
        proc = self.run_script(ROUTER, "--cache-file", cache, "--verify", "--json", expect=1)
        self.assertIn("nested quantifier", self.json_out(proc)["problems"][0]["issue"])

    def test_enormous_query_is_capped(self):
        started = time.monotonic()
        self.run_script(ROUTER, "--query", "a" * 200000, "--json", expect=0)
        self.assertLess(time.monotonic() - started, 10)

    # --- symlink writes ----------------------------------------------------

    def test_cloner_refuses_to_write_through_a_symlink(self):
        """--force followed a symlink and clobbered a file outside --output-dir."""
        secret = self.tmp / "secret.txt"
        secret.write_text("SECRET")
        out = self.tmp / "out"
        out.mkdir()
        os.symlink(secret, out / "SKILL.md")
        log = self.tmp / "s.log"
        log.write_text("$ ls\n")

        proc = self.run_script(CLONER, "--log", log, "--name", "v",
                               "--output-dir", out, "--force", "--json", expect=4)
        self.assertIn("symlink", self.json_out(proc)["error"])
        self.assertEqual(secret.read_text(), "SECRET")

    def test_cloner_rejects_symlinked_dir_escaping_allowed_root(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        root = self.tmp / "root"
        root.mkdir()
        link = self.tmp / "link"
        os.symlink(outside, link)
        log = self.tmp / "s.log"
        log.write_text("$ ls\n")
        self.run_script(CLONER, "--log", log, "--output-dir", link,
                        "--allowed-root", root, "--json", expect=1)

    def test_cloner_neutralizes_traversal_in_name(self):
        log = self.tmp / "s.log"
        log.write_text("$ ls\n")
        proc = self.run_script(CLONER, "--log", log, "--name", "../../etc/evil",
                               "--output-dir", self.tmp / "o", "--json", expect=0)
        slug = self.json_out(proc)["skill_name"]
        self.assertNotIn("/", slug)
        self.assertNotIn("..", slug)

    # --- corrupt state -----------------------------------------------------

    CORRUPT = ['not json', 'null', '[]', '{}', '"a string"', '123']

    def test_heat_mode_survives_corrupt_state(self):
        self.state.mkdir(parents=True, exist_ok=True)
        shapes = self.CORRUPT + ['{"recorded_failures":"NaN"}', '{"recorded_failures":-5}',
                                 '{"recorded_failures":[1,2]}', '{"recorded_failures":1.9}']
        for blob in shapes:
            with self.subTest(blob=blob):
                (self.state / "heat-mode.json").write_text(blob)
                proc = self.run_script(ANTI_STALL, "--json", expect=0)
                self.assertGreaterEqual(self.json_out(proc)["signals"]["persisted"], 0)

    def test_queue_survives_corrupt_state(self):
        self.state.mkdir(parents=True, exist_ok=True)
        shapes = self.CORRUPT + ['{"tasks":"x"}', '[{"task_id":"a"}]',
                                 '{"next_id":"x","tasks":[1,2,"a"]}',
                                 '{"tasks":[{"pid":"abc","task_id":"t","command":"c"}]}']
        for blob in shapes:
            with self.subTest(blob=blob):
                (self.state / "speculative_queue.json").write_text(blob)
                self.run_script(ENFORCER, "--status", "--json", expect=0)
                self.run_script(ENFORCER, "--check-leak", "--json")

    def test_corrupt_route_file_shapes(self):
        for blob in ['not json', 'null', '{"a":1}', '[]', '[{"pattern":"^x$"}]', '[1,2,3]']:
            with self.subTest(blob=blob):
                cache = self.tmp / "r.json"
                cache.write_text(blob)
                self.run_script(ROUTER, "--cache-file", cache, "--query", "hello",
                                "--json", expect=0)

    # --- perimeter escapes -------------------------------------------------

    def test_cqc_blocks_every_escape_shape(self):
        perim = self.tmp / "perim"
        (perim / "sub").mkdir(parents=True)
        outside = self.tmp / "outside"
        outside.mkdir()
        secret = outside / "creds.txt"
        secret.write_text("SECRET")
        sibling = self.tmp / "perim-evil"
        sibling.mkdir()

        escapes = [
            f"cat {secret}",
            "cat ../outside/creds.txt",
            f"cat '{secret}'",
            f'cat "{secret}"',
            f"cat {sibling}/x",
            f"rm -f {secret}",
        ]
        for cmd in escapes:
            with self.subTest(cmd=cmd):
                proc = self.run_script(CQC_EXEC, "--perimeter-dir", perim,
                                       "--command", cmd, "--json", expect=2)
                data = self.json_out(proc)
                self.assertEqual(data["status"], "blocked")
                self.assertFalse(data["executed"])
        self.assertEqual(secret.read_text(), "SECRET")

    def test_path_validator_denies_traversal_and_symlinks(self):
        root = self.tmp / "root"
        root.mkdir()
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "creds.txt").write_text("x")
        os.symlink(outside, root / "escape")

        for path in [self.tmp / "outside" / "creds.txt",
                     root / "escape" / "creds.txt",
                     root / ".." / "outside" / "x",
                     self.tmp / "root-evil" / "x"]:
            with self.subTest(path=str(path)):
                self.run_script(ENFORCER, "--path", path,
                                "--allowed-root", root, "--json", expect=1)

    # --- concurrency -------------------------------------------------------

    def _parallel(self, script, *args, n=12):
        procs = [subprocess.Popen(
            [sys.executable, str(script), *[str(a) for a in args], "--json"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, cwd=str(self.tmp), env=self.env) for _ in range(n)]
        for p in procs:
            p.wait(timeout=60)

    def test_concurrent_failure_records_are_not_lost(self):
        """Unlocked read-modify-write lost most increments under parallelism."""
        self._parallel(ANTI_STALL, "--record-failure", n=12)
        data = self.json_out(self.run_script(ANTI_STALL, "--json", expect=0))
        self.assertEqual(data["signals"]["persisted"], 12)

    def test_concurrent_enqueues_are_not_lost(self):
        self._parallel(ENFORCER, "--queue-speculative", "true", n=12)
        data = self.json_out(self.run_script(ENFORCER, "--status", "--json", expect=0))
        self.assertEqual(data["queue_length"], 12)
        ids = [t["task_id"] for t in data["speculative_queue"]]
        self.assertEqual(len(ids), len(set(ids)), "duplicate task ids")

    def test_state_writes_leave_no_temp_files(self):
        self._parallel(ANTI_STALL, "--record-failure", n=6)
        self._parallel(ENFORCER, "--queue-speculative", "true", n=6)
        leftovers = [p.name for p in self.state.glob("*.tmp.*")]
        self.assertEqual(leftovers, [], f"atomic write left temp files: {leftovers}")

    # --- fuzzer injection --------------------------------------------------

    def test_no_payload_shape_reaches_a_shell(self):
        shapes = ["'; touch P1; echo '", "$(touch P2)", "`touch P3`", "&& touch P4",
                  "| touch P5", "; touch P6", '"; touch P7; "']
        for i, payload in enumerate(shapes, 1):
            self.run_script(FUZZER, "--target", "echo", "--mutations", "6",
                            "--random-seed", "2", "--seed-inputs", json.dumps([payload]),
                            "--json")
        created = sorted(p.name for p in self.tmp.glob("P?"))
        self.assertEqual(created, [], f"shell injection produced {created}")

    def test_target_string_is_not_shell_interpreted(self):
        self.run_script(FUZZER, "--target", "echo hi; touch OWNED", "--mutations", "2",
                        "--random-seed", "1", "--json")
        self.assertFalse((self.tmp / "OWNED").exists())


# ------------------------------------------------------------ suite-wide contracts

class TestSuiteContracts(SkillTestCase):

    def test_no_script_blocks_on_an_idle_stdin_pipe(self):
        """An open pipe nobody writes to is how agent harnesses invoke these.

        isatty() is False for such a pipe, so a bare sys.stdin.read() never
        returns and the calling agent stalls with no error.
        """
        for script in ALL_SCRIPTS + [FUZZER]:
            with self.subTest(script=script.name):
                read_fd, write_fd = os.pipe()
                try:
                    proc = subprocess.Popen(
                        [sys.executable, str(script), "--json"], stdin=read_fd,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        cwd=str(self.tmp), env=self.env)
                    try:
                        proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                        self.fail(f"{script.name} blocked on an idle stdin pipe")
                finally:
                    os.close(read_fd)
                    os.close(write_fd)

    def test_stdin_piping_still_works(self):
        """The non-blocking read must not break genuine piped input."""
        proc = self.run_script(ROUTER, "--json", stdin_data="git diff")
        self.assertEqual(self.json_out(proc)["matched_command"], "git diff --stat")

        log = self.tmp / "t.log"
        proc = self.run_script(CLONER, "--name", "piped", "--output-dir", self.tmp / "pipe-out",
                               "--json", stdin_data="$ echo hello\noutput\n")
        self.assertEqual(self.json_out(proc)["extracted_steps"], ["echo hello"])

        proc = self.run_script(ANTI_STALL, "--threshold", "2", "--json",
                               stdin_data="error one\nerror two\n")
        self.assertTrue(self.json_out(proc)["stall_detected"])

    def test_every_script_has_help(self):
        for script in ALL_SCRIPTS + [FUZZER]:
            with self.subTest(script=script.name):
                self.run_script(script, "--help", expect=0)

    def test_every_script_supports_json(self):
        for script in ALL_SCRIPTS + [FUZZER]:
            with self.subTest(script=script.name):
                self.assertIn("--json", self.run_script(script, "--help").stdout)

    def test_no_script_imports_third_party_modules(self):
        """Zero-dependency is the core portability promise of this suite."""
        allowed = {
            "sys", "os", "json", "argparse", "re", "subprocess", "random", "copy",
            "shlex", "select", "signal", "fcntl", "contextlib", "pathlib", "typing",
            "time", "datetime", "shutil", "tempfile", "collections", "itertools",
            "functools", "textwrap", "hashlib", "unittest",
        }
        for script in ALL_SCRIPTS + [FUZZER]:
            with self.subTest(script=script.name):
                for line in script.read_text().splitlines():
                    m = re.match(r"^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)", line)
                    if m and m.group(1) not in allowed:
                        # boundary_validator is imported by cqc_executor as a sibling
                        if m.group(1) == "boundary_validator":
                            continue
                        self.fail(f"{script.name} imports non-stdlib module '{m.group(1)}'")

    def test_every_skill_has_the_expected_layout(self):
        for skill in SKILL_DIRS:
            with self.subTest(skill=skill):
                base = REPO / skill
                slug = skill.replace("-", "_")
                self.assertTrue((base / "SKILL.md").is_file())
                self.assertTrue((base / "scripts").is_dir())
                self.assertTrue((base / "references" / f"{slug}_guide.md").is_file())
                self.assertTrue((base / "references" / f"{slug}_runbook.md").is_file())

    def test_skill_frontmatter_is_well_formed(self):
        for skill in SKILL_DIRS:
            with self.subTest(skill=skill):
                text = (REPO / skill / "SKILL.md").read_text()
                m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
                self.assertIsNotNone(m, f"{skill}: missing frontmatter")
                fm = m.group(1)
                name = re.search(r"^name:\s*(.+)$", fm, re.M)
                desc = re.search(r"^description:\s*(.+)$", fm, re.M)
                self.assertIsNotNone(name)
                self.assertIsNotNone(desc)
                self.assertEqual(name.group(1).strip(), skill,
                                 "frontmatter name must match folder name")
                self.assertGreater(len(desc.group(1).strip()), 40,
                                   "description is the activation matcher; make it specific")

    def test_no_collapsed_template_placeholders(self):
        for skill in SKILL_DIRS:
            with self.subTest(skill=skill):
                text = (REPO / skill / "SKILL.md").read_text()
                self.assertNotIn("()", text, "collapsed {placeholder} substitution")
                self.assertNotRegex(text, r"\|\s+\|\s+\|", "empty table cells")

    def test_no_absolute_author_paths_leak(self):
        for path in REPO.rglob("*.md"):
            if ".git" in path.parts or path.name == "CLAUDE.md":
                continue
            with self.subTest(path=str(path.relative_to(REPO))):
                self.assertNotIn("/Users/", path.read_text())

    def test_skill_docs_reference_only_real_flags(self):
        """Docs drifting from the CLI is how the v1 playbooks became inert."""
        for skill in SKILL_DIRS:
            base = REPO / skill
            helps = {}
            for script in (base / "scripts").glob("*.py"):
                # stdin=DEVNULL for the same reason the scripts poll stdin: never
                # inherit the runner's. And verify the help text actually arrived —
                # without this check an empty result fails every flag assertion
                # below at once, turning one transient hiccup into ~200 confusing
                # subtest failures instead of a single clear one.
                proc = subprocess.run(
                    [sys.executable, str(script), "--help"],
                    capture_output=True, text=True, timeout=30,
                    stdin=subprocess.DEVNULL)
                self.assertEqual(proc.returncode, 0,
                                 f"{script.name} --help exited {proc.returncode}: {proc.stderr}")
                self.assertTrue(proc.stdout.strip(),
                                f"{script.name} --help produced no output")
                helps[script.name] = proc.stdout

            for doc in [base / "SKILL.md", *(base / "references").glob("*.md")]:
                text = doc.read_text()
                for script_name, flags in re.findall(
                        r"(\w+\.py)((?:\s+--?[\w-]+(?:\s+[^\s\\]+)?)*)", text):
                    if script_name not in helps:
                        continue
                    for flag in re.findall(r"\s(--[\w-]+)", flags):
                        with self.subTest(doc=doc.name, script=script_name, flag=flag):
                            self.assertIn(flag, helps[script_name],
                                          f"{doc.name} documents {flag} which "
                                          f"{script_name} does not accept")


if __name__ == "__main__":
    unittest.main(verbosity=2)
