"""Tests for the v0.5 revision loop: `converge`, the `max_growth` setting, and the
review record's per-pass `words` and `gates`.

Run from the repo root:

    python3 -m unittest discover -s skills/spec-review/tests -v
"""

import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
PLUGIN_ROOT = os.path.dirname(os.path.dirname(SKILL_DIR))
CONVERGE = os.path.join(SKILL_DIR, "converge")
GATE = os.path.join(SKILL_DIR, "gate")
RECORD = os.path.join(SKILL_DIR, "record")
FIXTURES = os.path.join(HERE, "fixtures")
SLUG = "archive-completed-todos"

# case: (exit code, verdict after "<spec>: ")
EXPECTED = {
    "loop-continue-1": (3, "continue to pass 2: hand 2 fix blockers to the author"),
    "loop-continue-2": (3, "continue to pass 3: hand 1 fix blocker to the author"),
    "loop-converge-2": (0, "converged at pass 2"),
    "loop-converge-3": (0, "converged at pass 3"),
    "loop-oscillation": (1, "stop at pass 2: oscillation"),
    "loop-oscillation-fewer": (1, "stop at pass 2: oscillation"),
    "loop-flat": (1, "stop at pass 2: no-progress"),
    "loop-cap": (1, "stop at pass 3: cap"),
    "loop-bloat-ceiling": (1, "stop at pass 2: bloat-ceiling"),
    "loop-bloat-growth": (1, "stop at pass 2: bloat-growth"),
    "loop-growth-setting": (1, "stop at pass 2: bloat-growth"),
    "loop-gate-fails": (1, "stop at pass 2: gate"),
    "loop-decision": (1, "stop at pass 1: decision"),
}

LINE_RE = re.compile(r"^.+:\d+: error \[loop\.[a-z-]+\] [^:]+: .+\. Fix: [A-Z].+\.$")
STATUS_RE = re.compile(r"^.+: pass [1-3] of 3: \d+ open blockers? \(\d+ fix, \d+ decision\)(, was \d+, \d+ new)?; "
                       r"\d+ words?(, was \d+ \([+-]\d+\.\d%\))?; gates (ok|failed)$")
VERDICT_RE = re.compile(r"^.+: (converged at pass [1-3]|continue to pass [23]: hand \d+ fix blockers? to the author|"
                        r"stop at pass [1-3]: (bloat-ceiling|bloat-growth|gate|oscillation|no-progress|decision|cap))$")


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


def run(script, *args, **kwargs):
    return subprocess.run([sys.executable, script] + list(args), capture_output=True, text=True, **kwargs)


def spec_of(root):
    return os.path.join(root, "specs", SLUG + ".md")


def prev_of(root):
    """The spec as it was before the revision, saved under its own name as the loop saves it."""
    return os.path.join(root, "previous", SLUG + ".md")


def converge(root, *extra):
    args = list(extra)
    if os.path.exists(prev_of(root)):
        args += ["--previous", prev_of(root)]
    return run(CONVERGE, *(args + [spec_of(root)]))


def fixture(case):
    return os.path.join(FIXTURES, case)


def verdict(result):
    return result.stdout.strip().split("\n")[-1].split(": ", 1)[1]


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data, indent=2))
    return path


class TempCase(unittest.TestCase):
    def copy(self, case):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        root = os.path.join(tmp, case)
        shutil.copytree(fixture(case), root)
        return root

    def record_of(self, root):
        return os.path.join(root, "specs", "reviews", SLUG + ".json")


# ---------------------------------------------------------------------------
# The verdicts
# ---------------------------------------------------------------------------

class Verdicts(unittest.TestCase):
    def test_every_loop_fixture_has_an_expectation(self):
        found = sorted(d for d in os.listdir(FIXTURES) if d.startswith("loop-"))
        self.assertEqual(found, sorted(EXPECTED))

    def test_fixtures(self):
        for case, (code, text) in EXPECTED.items():
            with self.subTest(case=case):
                result = converge(fixture(case))
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertEqual(verdict(result), text, result.stdout)

    def test_fixture_records_are_valid(self):
        for case in EXPECTED:
            with self.subTest(case=case):
                self.assertEqual(run(RECORD, os.path.join(fixture(case), "specs", "reviews", SLUG + ".json")).returncode, 0)

    def test_every_output_line_is_a_problem_status_or_verdict(self):
        for case in EXPECTED:
            lines = converge(fixture(case)).stdout.strip().split("\n")
            with self.subTest(case=case):
                for line in lines[:-2]:
                    self.assertRegex(line, LINE_RE)
                self.assertRegex(lines[-2], STATUS_RE)
                self.assertRegex(lines[-1], VERDICT_RE)

    def test_a_stop_names_its_reason_in_problem_lines(self):
        for case, (code, text) in EXPECTED.items():
            if code != 1:
                continue
            reason = text.rsplit(": ", 1)[1]
            with self.subTest(case=case):
                self.assertIn("error [loop.%s]" % reason, converge(fixture(case)).stdout)

    def test_continue_and_converged_print_no_problems(self):
        for case, (code, _) in EXPECTED.items():
            if code != 1:
                with self.subTest(case=case):
                    self.assertNotIn("error [", converge(fixture(case)).stdout)


class Convergence(TempCase):
    def test_converges_in_two_passes(self):
        out = converge(fixture("loop-converge-2")).stdout
        self.assertIn("pass 2 of 3: 0 open blockers (0 fix, 0 decision), was 2, 0 new", out)

    def test_converges_in_three_passes(self):
        out = converge(fixture("loop-converge-3")).stdout
        self.assertIn("pass 3 of 3: 0 open blockers (0 fix, 0 decision), was 1, 0 new", out)

    def test_each_pass_of_a_converging_loop_continues(self):
        # The converge-3 record cut back to pass 1 and pass 2: each one continues.
        root = self.copy("loop-converge-3")
        rec = read_json(self.record_of(root))
        passes = rec["passes"]
        os.remove(prev_of(root))
        rec["passes"] = passes[:1]
        del rec["passes"][0]["words"], rec["passes"][0]["gates"]
        write(self.record_of(root), rec)
        result = converge(root)
        self.assertEqual(result.returncode, 3, result.stdout)
        self.assertEqual(verdict(result), "continue to pass 2: hand 3 fix blockers to the author")

    def test_oscillation_stops_at_the_pass_where_blockers_rose(self):
        # Pass 1 alone continues; pass 2, where the count rose from 2 to 3, stops.
        root = self.copy("loop-oscillation")
        rec = read_json(self.record_of(root))
        full = json.loads(json.dumps(rec))
        rec["passes"] = rec["passes"][:1]
        del rec["passes"][0]["words"], rec["passes"][0]["gates"]
        write(self.record_of(root), rec)
        os.rename(prev_of(root), os.path.join(root, "prev.md"))
        self.assertEqual(converge(root).returncode, 3)
        write(self.record_of(root), full)
        os.rename(os.path.join(root, "prev.md"), prev_of(root))
        result = converge(root)
        self.assertEqual(verdict(result), "stop at pass 2: oscillation")
        self.assertIn("3 open blockers (3 fix, 0 decision), was 2, 2 new", result.stdout)

    def test_new_blockers_stop_even_when_the_count_falls(self):
        result = converge(fixture("loop-oscillation-fewer"))
        self.assertIn("was 3, 1 new", result.stdout)
        self.assertIn("architecture.adr-conflict (architecture-1, fix) is new in pass 2", result.stdout)

    def test_a_flat_count_stops(self):
        self.assertIn("pass 2 has 2 open blockers, not fewer than pass 1's 2", converge(fixture("loop-flat")).stdout)

    def test_the_cap_is_three_passes(self):
        result = converge(fixture("loop-cap"))
        self.assertIn("pass 3 of 3 still has 1 open blocker", result.stdout)
        self.assertNotIn("continue", result.stdout)

    def test_a_record_cant_hold_a_fourth_pass(self):
        root = self.copy("loop-cap")
        rec = read_json(self.record_of(root))
        rec["passes"].append({"findings": [], "open_blockers": 0})
        write(self.record_of(root), rec)
        result = converge(root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("[record.passes]", result.stdout)

    def test_bloat_by_ceiling(self):
        out = converge(fixture("loop-bloat-ceiling")).stdout
        self.assertIn("the revision made the spec 711 words, over the ceiling of 680 (it was 655)", out)

    def test_bloat_by_growth_share(self):
        out = converge(fixture("loop-bloat-growth")).stdout
        self.assertIn("grew the spec from 655 to 872 words, more than max_growth 0.25 of 655", out)

    def test_growth_share_comes_from_the_settings(self):
        # 655 -> 711 words is +8.5%: over max_growth 0.05 and 0.08, within 0.09 and the default 0.25.
        root = self.copy("loop-growth-setting")
        cfg = os.path.join(root, ".orca-kit", "spec-review.yml")
        for setting, code in (("max_growth: 0.05\n", 1), ("max_growth: 0.08\n", 1), ("max_growth: 0.09\n", 0), ("", 0)):
            with self.subTest(setting=setting):
                write(cfg, setting)
                self.assertEqual(converge(root).returncode, code)

    def test_growth_exactly_at_the_share_is_allowed(self):
        # 655 -> 711 is a growth of 56 words; max_growth 56/655 allows exactly that.
        root = self.copy("loop-growth-setting")
        write(os.path.join(root, ".orca-kit", "spec-review.yml"), "max_growth: %r\n" % (56 / 655.0 + 1e-12))
        self.assertEqual(converge(root).returncode, 0)

    def test_a_shrinking_revision_is_never_bloat(self):
        root = self.copy("loop-converge-2")
        write(os.path.join(root, ".orca-kit", "spec-review.yml"), "max_growth: 0\n")
        # previous (655 words) -> current (664) would be growth; swap them, dropping the record's words.
        rec = read_json(self.record_of(root))
        for p in rec["passes"]:
            p.pop("words", None)
        write(self.record_of(root), rec)
        cur, prev = spec_of(root), prev_of(root)
        with open(cur) as a, open(prev) as b:
            cur_text, prev_text = a.read(), b.read()
        write(cur, prev_text)
        write(prev, cur_text)
        self.assertEqual(converge(root).returncode, 0)

    def test_a_gate_failing_after_a_revision_stops(self):
        result = converge(fixture("loop-gate-fails"))
        self.assertIn("a hard gate fails (check (1); passed: secrets, blocks, trace, length)", result.stdout)
        self.assertIn("gates failed", result.stdout)
        self.assertEqual(run(GATE, spec_of(fixture("loop-gate-fails"))).returncode, 1)
        self.assertEqual(run(GATE, prev_of(fixture("loop-gate-fails"))).returncode, 0)

    def test_decision_blockers_never_loop(self):
        result = converge(fixture("loop-decision"))
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("continue", result.stdout)
        self.assertIn("ambiguity.two-readings (ambiguity-4) is a decision for the user", result.stdout)
        # The same pass without the decision blocker would continue with its one fix blocker.
        root = self.copy("loop-decision")
        rec = read_json(self.record_of(root))
        rec["passes"][0]["findings"] = [f for f in rec["passes"][0]["findings"] if f["kind"] != "decision" or f["severity"] != "blocker"]
        rec["passes"][0]["open_blockers"] = 1
        write(self.record_of(root), rec)
        self.assertEqual(verdict(converge(root)), "continue to pass 2: hand 1 fix blocker to the author")

    def test_warnings_and_nits_never_count(self):
        # converge-2's last pass holds a nit and converges; continue-1 holds a warning and hands back only the 2 blockers.
        self.assertEqual(converge(fixture("loop-converge-2")).returncode, 0)
        self.assertIn("hand 2 fix blockers", converge(fixture("loop-continue-1")).stdout)


class SameBlocker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("spec_review_converge", CONVERGE)

    def blocker(self, rule="ambiguity.weasel-word", section="Behavior & Edge Cases", line=10, ref="AC-1", id_="a-1"):
        return {"id": id_, "rule": rule, "severity": "blocker", "kind": "fix",
                "location": {"section": section, "line": line, "ref": ref}}

    def test_line_ref_and_section_case_are_ignored(self):
        a = self.blocker()
        b = self.blocker(section="behavior &   edge cases", line=48, ref=None, id_="b-7")
        self.assertEqual(self.m.blocker_key(a), self.m.blocker_key(b))
        self.assertEqual(self.m.new_blockers([b], [a]), [])

    def test_rule_or_section_change_is_a_new_blocker(self):
        a = self.blocker()
        for other in (self.blocker(rule="ambiguity.untestable-ac"), self.blocker(section="Goal & Non-Goals")):
            self.assertEqual(self.m.new_blockers([other], [a]), [other])

    def test_counted_as_a_multiset(self):
        a1, a2 = self.blocker(id_="a-1"), self.blocker(id_="a-2", line=20)
        self.assertEqual(self.m.new_blockers([a1, a2], [a1]), [a2])
        self.assertEqual(self.m.new_blockers([a1], [a1, a2]), [])

    def test_the_flat_fixture_matches_moved_blockers(self):
        out = converge(fixture("loop-flat")).stdout
        self.assertIn("was 2, 0 new", out)


class Deterministic(unittest.TestCase):
    def test_same_input_same_output(self):
        for case in EXPECTED:
            with self.subTest(case=case):
                a, b = converge(fixture(case)), converge(fixture(case))
                self.assertEqual((a.returncode, a.stdout), (b.returncode, b.stdout))

    def test_output_does_not_depend_on_the_environment(self):
        env = dict(os.environ, LANG="C", TZ="Pacific/Auckland", PYTHONHASHSEED="123")
        for case in ("loop-oscillation", "loop-cap", "loop-bloat-growth"):
            with self.subTest(case=case):
                a = converge(fixture(case))
                b = run(CONVERGE, "--previous", prev_of(fixture(case)), spec_of(fixture(case)),
                        env=env, cwd=tempfile.gettempdir())
                self.assertEqual((a.returncode, a.stdout), (b.returncode, b.stdout))

    def test_reads_files_only(self):
        with open(CONVERGE, encoding="utf-8") as f:
            text = f.read()
        self.assertIsNone(re.search(r"open\([^)]*['\"][wax]\+?['\"]|\.write_text\(|json\.dump\(|os\.(rename|replace|remove)\(", text))

    def test_writes_nothing(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        for case in EXPECTED:
            shutil.copytree(fixture(case), os.path.join(tmp, case))

        def snapshot():
            out = {}
            for d, _, files in os.walk(tmp):
                for name in files:
                    with open(os.path.join(d, name), "rb") as fh:
                        out[os.path.join(d, name)] = fh.read()
            return out

        before = snapshot()
        for case in EXPECTED:
            converge(os.path.join(tmp, case))
        self.assertEqual(snapshot(), before)


class Inputs(TempCase):
    def test_pass_two_needs_previous(self):
        result = run(CONVERGE, spec_of(fixture("loop-flat")))
        self.assertEqual(result.returncode, 2)
        self.assertIn("pass 2 needs --previous", result.stdout)

    def test_pass_one_takes_no_previous(self):
        result = run(CONVERGE, "--previous", prev_of(fixture("loop-flat")), spec_of(fixture("loop-continue-1")))
        self.assertEqual(result.returncode, 2)

    def test_no_record(self):
        root = self.copy("loop-continue-1")
        os.remove(self.record_of(root))
        result = converge(root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("[loop.record]", result.stdout)

    def test_no_passes(self):
        root = self.copy("loop-continue-1")
        rec = read_json(self.record_of(root))
        del rec["passes"]
        write(self.record_of(root), rec)
        self.assertEqual(converge(root).returncode, 2)

    def test_invalid_record(self):
        root = self.copy("loop-continue-1")
        write(self.record_of(root), "{")
        self.assertEqual(converge(root).returncode, 2)

    def test_record_words_must_match_the_specs(self):
        for index, what in ((-1, "current"), (-2, "previous")):
            with self.subTest(pass_=what):
                root = self.copy("loop-continue-2")
                rec = read_json(self.record_of(root))
                rec["passes"][index]["words"] += 1
                write(self.record_of(root), rec)
                result = converge(root)
                self.assertEqual(result.returncode, 2)
                self.assertIn("records", result.stdout)

    def test_record_gates_must_match_the_spec(self):
        root = self.copy("loop-gate-fails")
        rec = read_json(self.record_of(root))
        rec["passes"][-1]["gates"] = "passed"
        write(self.record_of(root), rec)
        self.assertEqual(converge(root).returncode, 2)

    def test_record_option(self):
        root = self.copy("loop-continue-1")
        moved = os.path.join(root, "elsewhere.json")
        os.rename(self.record_of(root), moved)
        self.assertEqual(converge(root, "--record", moved).returncode, 2)  # named after the slug, so record rejects the name
        os.rename(moved, os.path.join(root, SLUG + ".json"))
        self.assertEqual(converge(root, "--record", os.path.join(root, SLUG + ".json")).returncode, 3)

    def test_invalid_settings(self):
        root = self.copy("loop-continue-1")
        write(os.path.join(root, ".orca-kit", "spec-review.yml"), "max_growth: lots\n")
        result = converge(root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("error [config] settings: max_growth", result.stdout)

    def test_usage(self):
        self.assertEqual(run(CONVERGE).returncode, 2)
        self.assertEqual(run(CONVERGE, "--bogus", "x.md").returncode, 2)
        self.assertEqual(run(CONVERGE, "a.md", "b.md").returncode, 2)
        self.assertEqual(run(CONVERGE, "--previous").returncode, 2)
        self.assertEqual(run(CONVERGE, os.path.join(FIXTURES, "nope.md")).returncode, 2)

    def test_rules_and_help(self):
        out = run(CONVERGE, "--rules").stdout
        m = load("spec_review_converge", CONVERGE)
        for reason in m.REASONS:
            self.assertIn("loop.%s" % reason, out)
        self.assertEqual(run(CONVERGE, "--help").returncode, 0)


# ---------------------------------------------------------------------------
# Settings and the record
# ---------------------------------------------------------------------------

class GrowthSetting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("spec_review_gate", GATE)

    def load_text(self, text):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        os.makedirs(os.path.join(tmp, ".orca-kit"))
        write(os.path.join(tmp, ".orca-kit", "spec-review.yml"), text)
        return self.m.load_config(tmp)[0]

    def test_default(self):
        self.assertEqual(self.m.DEFAULTS["max_growth"], 0.25)
        self.assertEqual(self.load_text("max_words: 900\n")["max_growth"], 0.25)

    def test_accepted(self):
        for text, value in (("max_growth: 0.1\n", 0.1), ("max_growth: 1\n", 1), ("max_growth: 0\n", 0), ("max_growth: .5\n", 0.5)):
            with self.subTest(text=text):
                self.assertEqual(self.load_text(text)["max_growth"], value)

    def test_rejected(self):
        for text in ("max_growth: -0.1\n", "max_growth: '0.2'\n", "max_growth: true\n", "max_growth: .inf\n",
                     "max_growth: .nan\n", "max_growth: [0.2]\n", "max_growh: 0.2\n"):
            with self.subTest(text=text):
                with self.assertRaises(self.m.ConfigError):
                    self.load_text(text)

    def test_gate_output_is_unchanged_by_the_setting(self):
        spec = spec_of(fixture("loop-continue-1"))
        a = run(GATE, spec)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        root = os.path.join(tmp, "r")
        shutil.copytree(fixture("loop-continue-1"), root)
        write(os.path.join(root, ".orca-kit", "spec-review.yml"), "max_growth: 0.01\n")
        b = run(GATE, spec_of(root))
        self.assertEqual(a.returncode, b.returncode)
        self.assertEqual(a.stdout.replace(fixture("loop-continue-1"), "R"), b.stdout.replace(root, "R"))


class RecordPassFields(TempCase):
    def check(self, root):
        return run(RECORD, self.record_of(root))

    def test_words_and_gates_are_optional(self):
        self.assertEqual(self.check(fixture("loop-continue-1")).returncode, 0)  # neither
        self.assertEqual(self.check(fixture("loop-continue-2")).returncode, 0)  # both

    def test_bad_values_are_rejected(self):
        for field, value in (("words", -1), ("words", 1.5), ("words", True), ("words", "600"),
                             ("gates", "ok"), ("gates", None), ("gates", True)):
            with self.subTest(field=field, value=value):
                root = self.copy("loop-continue-2")
                rec = read_json(self.record_of(root))
                rec["passes"][0][field] = value
                write(self.record_of(root), rec)
                result = self.check(root)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(sorted(set(re.findall(r"error \[([a-z.-]+)\]", result.stdout))), ["record.passes"])

    def test_other_pass_fields_are_still_rejected(self):
        root = self.copy("loop-continue-2")
        rec = read_json(self.record_of(root))
        rec["passes"][0]["verdict"] = "continue"
        write(self.record_of(root), rec)
        self.assertEqual(self.check(root).returncode, 1)


class Docs(unittest.TestCase):
    def read(self, *parts):
        with open(os.path.join(*parts), encoding="utf-8") as f:
            return f.read()

    def test_skill_and_loop_name_the_script_and_every_reason(self):
        m = load("spec_review_converge", CONVERGE)
        skill = self.read(SKILL_DIR, "SKILL.md")
        loop = self.read(SKILL_DIR, "loop.md")
        self.assertIn("loop.md", skill)
        self.assertIn("converge", skill)
        for reason in m.REASONS:
            self.assertIn("`%s`" % reason, loop)

    def test_documented_max_growth_matches_the_default(self):
        gate = load("spec_review_gate", GATE)
        for text in (self.read(SKILL_DIR, "SKILL.md"), self.read(SKILL_DIR, "loop.md"), gate.__doc__):
            self.assertIn("max_growth: %g" % gate.DEFAULTS["max_growth"], text)


if __name__ == "__main__":
    unittest.main()
