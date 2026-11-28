"""Tests for v0.7, graduating rules: `findings --stats`, the rubric tables'
Graduates column, and the `graduate_after` setting.

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
AGENTS_DIR = os.path.join(PLUGIN_ROOT, "agents")
FINDINGS = os.path.join(SKILL_DIR, "findings")
GATE = os.path.join(SKILL_DIR, "gate")
FIXTURES = os.path.join(HERE, "fixtures")
SCRIPTS = ("findings", "gate", "record", "converge", "pause", "summary")

PROPOSAL_RE = re.compile(r"^graduate (?P<n>\d+): (?P<rule>[a-z0-9.-]+) \((?P<level>blocker|nit)\): seen in (?P<specs>\d+) specs "
                         r"\((?P<slugs>[^)]*)\), (?P<findings>\d+) findings?; enforce in (?P<where>.+)$")
ROW_RE = re.compile(r"^(?P<rule>[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9-]+) +(?P<level>blocker|nit) +(?P<graduates>[a-z_]+) +"
                    r"(?P<findings>\d+) +(?P<specs>\d+)$")
LAST_RE = re.compile(r"^stats: (?P<records>\d+) records? counted \((?P<passes>\d+) pass(?:es)?, (?P<findings>\d+) findings?\), "
                     r"(?P<invalid>\d+) not counted; (?P<proposals>\d+) proposals? \(graduate_after (?P<threshold>\d+)\)$")


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


def run(*args, **kwargs):
    return subprocess.run([sys.executable, FINDINGS] + list(args), capture_output=True, text=True, **kwargs)


def fixture(case):
    return os.path.join(FIXTURES, case)


def stats(root, *extra):
    return run("--stats", "--repo", root, *extra)


def rows(stdout):
    return dict((m.group("rule"), m.groupdict()) for m in map(ROW_RE.match, stdout.splitlines()) if m)


def proposals(stdout):
    return [m.groupdict() for m in map(PROPOSAL_RE.match, stdout.splitlines()) if m]


def last(stdout):
    m = LAST_RE.match(stdout.splitlines()[-1])
    return m.groupdict() if m else None


class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def copy(self, case):
        root = os.path.join(self.tmp, case)
        shutil.copytree(fixture(case), root)
        return root

    def settings(self, root, text):
        os.makedirs(os.path.join(root, ".orca-kit"), exist_ok=True)
        with open(os.path.join(root, ".orca-kit", "spec-review.yml"), "w", encoding="utf-8") as f:
            f.write(text)


# ---------------------------------------------------------------------------
# The fixtures, and the v0.7 done criterion
# ---------------------------------------------------------------------------

class Fixtures(unittest.TestCase):
    EXPECTED = {  # case -> (exit code, proposals, records counted, records not counted)
        "stats-graduate": (0, ["ambiguity.weasel-word"], 3, 0),
        "stats-judgement": (0, [], 4, 0),
        "stats-below": (0, [], 2, 0),
        "stats-one-spec": (0, [], 1, 0),
        "stats-invalid": (2, [], 2, 2),
    }

    def test_every_stats_fixture_has_an_expectation(self):
        self.assertEqual(sorted(d for d in os.listdir(FIXTURES) if d.startswith("stats-")), sorted(self.EXPECTED))

    def test_fixtures(self):
        for case, (code, rules, counted, invalid) in self.EXPECTED.items():
            with self.subTest(case=case):
                result = stats(fixture(case))
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertEqual([p["rule"] for p in proposals(result.stdout)], rules)
                summary = last(result.stdout)
                self.assertIsNotNone(summary, result.stdout)
                self.assertEqual((int(summary["records"]), int(summary["invalid"]), int(summary["proposals"])),
                                 (counted, invalid, len(rules)))
                self.assertEqual(result.stderr, "")

    def test_every_output_line_is_known(self):
        known = (ROW_RE, PROPOSAL_RE, LAST_RE, re.compile(r"^rule +level +graduates +findings +specs$"),
                 re.compile(r"^  (example|draft[a-z ]*): .+$"), re.compile(r"^specs/reviews/[a-z0-9-]+\.json(:\d+: error \[[a-z.-]+\] .+\. Fix: .+\.|: .+)$"))
        for case in self.EXPECTED:
            for line in stats(fixture(case)).stdout.splitlines():
                with self.subTest(case=case, line=line):
                    self.assertTrue(any(r.match(line) for r in known), line)


class DoneCriterion(TempCase):
    """Seeded review files with a repeated rule produce a graduation proposal, and a judgement-call rule is never proposed."""

    def test_repeated_candidate_rule_is_proposed(self):
        out = stats(fixture("stats-graduate")).stdout
        [p] = proposals(out)
        self.assertEqual((p["n"], p["rule"], p["level"], p["specs"], p["findings"]),
                         ("1", "ambiguity.weasel-word", "blocker", "3", "6"))
        self.assertEqual(p["slugs"], "archive-todos, export-todos, import-todos")
        self.assertIn("the spec checker (orca-kit skills/spec/check)", p["where"])

    def test_proposal_has_one_example_per_spec_with_its_evidence(self):
        out = stats(fixture("stats-graduate")).stdout
        examples = [l for l in out.splitlines() if l.startswith("  example: ")]
        self.assertEqual(examples, [
            '  example: specs/reviews/archive-todos.json pass 1, ambiguity-1, Behavior & Edge Cases line 31 AC-1: "then the command responds quickly"',
            '  example: specs/reviews/export-todos.json pass 1, ambiguity-1, Behavior & Edge Cases line 40 AC-3: "then the export fails gracefully"',
            '  example: specs/reviews/import-todos.json pass 1, ambiguity-1, Behavior & Edge Cases line 33 AC-2: "then a bad file is handled gracefully"',
        ])

    def test_literal_pattern_gives_a_draft_regex(self):
        out = stats(fixture("stats-graduate")).stdout
        self.assertIn('  draft terms: "gracefully" (3 specs), "quickly" (3 specs)', out)
        m = re.search(r"(?m)^  draft regex: '(.*)'$", out)
        self.assertEqual(m.group(1), r"(?i)\b(?:gracefully|quickly)\b")
        self.assertIn("  draft rule: a checker error when an AC, edge-case row or New: contract matches the regex", out)
        regex = re.compile(m.group(1))
        with open(os.path.join(fixture("stats-graduate"), "specs", "reviews", "import-todos.json"), encoding="utf-8") as f:
            evidence = [x["evidence"] for x in json.load(f)["passes"][0]["findings"] if x["rule"] == "ambiguity.weasel-word"]
        for text in evidence:
            self.assertRegex(text, regex)
        self.assertNotRegex("then the export exits 1 within 2 seconds", regex)

    def test_judgement_call_rules_are_never_proposed(self):
        root = self.copy("stats-judgement")
        for threshold in ("", "graduate_after: 2\n"):
            with self.subTest(threshold=threshold):
                self.settings(root, threshold or "\n")
                result = stats(root)
                found = rows(result.stdout)
                self.assertEqual(found["ambiguity.two-readings"]["specs"], "4")
                self.assertEqual(found["ambiguity.two-readings"]["graduates"], "no")
                self.assertEqual(proposals(result.stdout), [])
                self.assertNotIn("draft", result.stdout)

    def test_two_readings_is_never_a_candidate(self):
        table = load("spec_review_findings_stats", FINDINGS).read_rule_rows()
        self.assertEqual(table["ambiguity.two-readings"], ("blocker", "no"))
        self.assertEqual(table["ambiguity.weasel-word"], ("blocker", "check"))

    def test_below_the_threshold_gives_none(self):
        result = stats(fixture("stats-below"))
        self.assertEqual(rows(result.stdout)["ambiguity.weasel-word"]["specs"], "2")
        self.assertEqual(proposals(result.stdout), [])
        self.assertEqual(last(result.stdout)["threshold"], "3")

    def test_the_threshold_is_the_setting(self):
        root = self.copy("stats-below")
        self.settings(root, "graduate_after: 2\n")
        result = stats(root)
        self.assertEqual([p["rule"] for p in proposals(result.stdout)], ["ambiguity.weasel-word"])
        self.assertIn('  draft terms: "gracefully" (2 specs)', result.stdout)
        self.assertEqual(last(result.stdout)["threshold"], "2")
        root = self.copy("stats-graduate")
        self.settings(root, "graduate_after: 4\n")
        self.assertEqual(proposals(stats(root).stdout), [])

    def test_one_spec_reviewed_many_times_is_one_spec(self):
        root = self.copy("stats-one-spec")
        for threshold in ("\n", "graduate_after: 2\n"):
            with self.subTest(threshold=threshold):
                self.settings(root, threshold)
                result = stats(root)
                row = rows(result.stdout)["ambiguity.weasel-word"]
                self.assertEqual((row["findings"], row["specs"]), ("6", "1"))
                self.assertEqual(last(result.stdout)["passes"], "3")
                self.assertEqual(proposals(result.stdout), [])

    def test_every_pass_is_counted(self):
        # export-todos has the rule in pass 1 and pass 2; the last pass alone would give 5, not 6.
        self.assertEqual(rows(stats(fixture("stats-graduate")).stdout)["ambiguity.weasel-word"]["findings"], "6")


class InvalidRecords(TempCase):
    def test_reported_not_counted(self):
        result = stats(fixture("stats-invalid"))
        out = result.stdout
        self.assertEqual(result.returncode, 2)
        self.assertIn("specs/reviews/export-todos.json:2: error [parse] file: not JSON", out)
        self.assertIn("specs/reviews/import-todos.json:9: error [record.passes] passes[1].open_blockers: open_blockers is 0", out)
        self.assertIn("specs/reviews/import-todos.json: not counted: the record isn't valid", out)
        self.assertIn("specs/reviews/export-todos.json: not counted: the record isn't valid", out)
        # Counted, the invalid records would make 4 specs and a proposal.
        self.assertEqual(rows(out)["ambiguity.weasel-word"]["specs"], "2")
        self.assertEqual(proposals(out), [])
        self.assertNotIn(self.tmp, out)
        self.assertNotIn(FIXTURES, out)

    def test_a_rule_failure_alone_exits_1(self):
        root = self.copy("stats-invalid")
        os.remove(os.path.join(root, "specs", "reviews", "export-todos.json"))
        result = stats(root)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(last(result.stdout)["invalid"], "1")

    def test_no_records_is_an_empty_count(self):
        result = stats(self.tmp)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), [
            "rule  level    graduates        findings  specs",
            "stats: 0 records counted (0 passes, 0 findings), 0 not counted; 0 proposals (graduate_after 3)"])

    def test_a_record_without_passes_counts_with_no_findings(self):
        result = stats(fixture("risk-signed"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(last(result.stdout)["records"], "1")
        self.assertEqual(last(result.stdout)["findings"], "0")


class Determinism(TempCase):
    def test_same_records_same_output(self):
        for case in Fixtures.EXPECTED:
            with self.subTest(case=case):
                first = stats(fixture(case))
                self.assertEqual((first.returncode, first.stdout), (stats(fixture(case)).returncode, stats(fixture(case)).stdout))

    def test_output_doesnt_depend_on_where_or_in_what_order_the_files_were_written(self):
        src = os.path.join(fixture("stats-graduate"), "specs", "reviews")
        root = os.path.join(self.tmp, "elsewhere")
        os.makedirs(os.path.join(root, "specs", "reviews"))
        shutil.copytree(os.path.join(fixture("stats-graduate"), ".orca-kit"), os.path.join(root, ".orca-kit"))
        for name in sorted(os.listdir(src), reverse=True):
            shutil.copy(os.path.join(src, name), os.path.join(root, "specs", "reviews", name))
        self.assertEqual(stats(root).stdout, stats(fixture("stats-graduate")).stdout)

    def test_report_function_ignores_record_order(self):
        m = load("spec_review_findings_det", FINDINGS)
        gate = load("spec_review_gate_det", GATE)
        _, _, records = m.read_records(fixture("stats-graduate"))
        config, _ = gate.load_config(fixture("stats-graduate"))
        forward = m.stats_report(records, m.read_rule_rows(), 3, config, gate)
        backward = m.stats_report(list(reversed(records)), m.read_rule_rows(), 3, config, gate)
        self.assertEqual(forward, backward)

    def test_default_repo_is_found_from_the_current_directory(self):
        result = run("--stats", cwd=os.path.join(fixture("stats-graduate"), "specs", "reviews"))
        self.assertEqual(result.stdout, stats(fixture("stats-graduate")).stdout)


# ---------------------------------------------------------------------------
# Nothing is written
# ---------------------------------------------------------------------------

class WritesNothing(TempCase):
    def snapshot(self, root):
        out = {}
        for d, _, files in os.walk(root):
            for f in files:
                p = os.path.join(d, f)
                with open(p, "rb") as fh:
                    out[p] = fh.read()
        return out

    def test_stats_writes_nothing(self):
        for case in Fixtures.EXPECTED:
            self.copy(case)
        before = self.snapshot(self.tmp)
        for case in Fixtures.EXPECTED:
            stats(os.path.join(self.tmp, case))
            run("--stats", cwd=os.path.join(self.tmp, case))
        self.assertEqual(self.snapshot(self.tmp), before)

    def test_no_script_writes_files(self):
        writes = re.compile(r"open\([^)]*['\"][wax]b?\+?['\"]|\.write_text\(|\.write_bytes\(|json\.dump\(|"
                            r"os\.(rename|replace|remove|unlink|makedirs|mkdir|rmdir)\(|shutil\.")
        for name in SCRIPTS:
            with open(os.path.join(SKILL_DIR, name), encoding="utf-8") as f:
                text = f.read()
            with self.subTest(script=name):
                self.assertIsNone(writes.search(text))

    def test_findings_runs_no_other_program(self):
        # --stats reads records and settings only; it never runs the checker or anything that could change it.
        with open(FINDINGS, encoding="utf-8") as f:
            self.assertNotIn("subprocess", f.read())


# ---------------------------------------------------------------------------
# The Graduates column
# ---------------------------------------------------------------------------

class GraduatesColumn(TempCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("spec_review_findings_cols", FINDINGS)

    def write_agent(self, name, rubric):
        with open(os.path.join(self.tmp, "spec-review-%s.md" % name), "w", encoding="utf-8") as f:
            f.write("---\nname: spec-review-%s\n---\n\n## Rubric\n\n%s\n## Output\n" % (name, rubric))

    def test_every_agent_table_has_the_column(self):
        for path in sorted(os.listdir(AGENTS_DIR)):
            if path.startswith("spec-review-"):
                with open(os.path.join(AGENTS_DIR, path), encoding="utf-8") as f:
                    with self.subTest(agent=path):
                        self.assertIn("| Rule | Level | Graduates | Report when |\n|---|---|---|---|\n", f.read())

    def test_every_rule_has_a_value(self):
        table = self.m.read_rule_rows()
        self.assertEqual(set(table), set(self.m.read_rule_table()))
        for rule, (_, target) in table.items():
            self.assertIn(target, self.m.GRADUATES, rule)

    def test_candidates_are_the_string_checkable_rules(self):
        # Only a rule whose detection could be a string, pattern or structure check is marked.
        candidates = sorted(r for r, (_, t) in self.m.read_rule_rows().items() if t != "no")
        self.assertEqual(candidates, ["ambiguity.vague-prose", "ambiguity.weasel-word"])

    def test_old_table_parses_with_no_candidates(self):
        self.write_agent("x", "| Rule | Level | Report when |\n|---|---|---|\n| `x.a` | nit | when |\n")
        self.assertEqual(self.m.read_rule_rows(self.tmp), {"x.a": ("nit", "no")})
        self.assertEqual(self.m.read_rule_table(self.tmp), {"x.a": "nit"})

    def test_new_table(self):
        self.write_agent("x", "| Rule | Level | Graduates | Report when |\n|---|---|---|---|\n"
                              "| `x.a` | nit | check | when |\n| `x.b` | blocker | no | when |\n| `x.c` | blocker | risk_terms | when |\n")
        self.assertEqual(self.m.read_rule_rows(self.tmp), {"x.a": ("nit", "check"), "x.b": ("blocker", "no"),
                                                           "x.c": ("blocker", "risk_terms")})

    def test_a_broken_column_is_an_error(self):
        header = "| Rule | Level | Graduates | Report when |\n|---|---|---|---|\n"
        for name, rubric in {"bad value": header + "| `x.a` | nit | maybe | when |\n",
                             "missing cell": header + "| `x.a` | nit | when |\n",
                             "yes isn't a value": header + "| `x.a` | nit | yes | when |\n"}.items():
            with self.subTest(case=name):
                self.write_agent("x", rubric)
                with self.assertRaises(self.m.RuleTableError):
                    self.m.read_rule_rows(self.tmp)

    def test_rules_lists_the_candidates(self):
        out = run("--rules").stdout
        part = out[out.index("graduation candidates"):]
        self.assertRegex(part, r"(?m)^  ambiguity\.weasel-word +check$")
        self.assertNotIn("two-readings", part)


# ---------------------------------------------------------------------------
# Config targets (no shipped rule uses them yet; checked on a made-up table)
# ---------------------------------------------------------------------------

class ConfigTargets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("spec_review_findings_targets", FINDINGS)
        cls.gate = load("spec_review_gate_targets", GATE)
        cls.config, _ = cls.gate.load_config(tempfile.gettempdir() + "/no-such-repo-for-stats")

    def records(self, risk=None):
        out = []
        for n, (slug, text) in enumerate((("a", "runs the reindex nightly"), ("b", "a reindex of old rows"),
                                          ("c", "the reindex job"))):
            f = {"id": "ambiguity-1", "reviewer": "ambiguity", "severity": "blocker", "kind": "fix", "rule": "ambiguity.weasel-word",
                 "location": {"section": "Behavior & Edge Cases", "line": 10 + n, "ref": None}, "evidence": text,
                 "concrete_question": "What?", "suggested_fix": "Say.", "risk": risk}
            out.append(("specs/reviews/%s.json" % slug, {"spec": slug, "passes": [{"findings": [f]}]}))
        return out

    def report(self, target, risk=None):
        rows = {"ambiguity.weasel-word": ("blocker", target)}
        return self.m.stats_report(self.records(risk), rows, 3, self.config, self.gate)[1]

    def test_risk_terms_keep_the_defaults(self):
        lines = self.report("risk_terms", risk="migration")
        self.assertIn("the gate config (.orca-kit/spec-review.yml), risk_terms", lines[0])
        defaults = self.gate.DEFAULT_RISK_TERMS["migration"]
        self.assertEqual(lines[-1], "      migration: [%s]" % ", ".join("'%s'" % t for t in list(defaults) + ["reindex"]))
        # The draft is valid settings.
        data = self.gate.parse_yaml("\n".join(l[4:] for l in lines[-2:]) + "\n")
        self.gate.risk_map(data["risk_terms"], "risk_terms", self.gate.check_term)

    def test_risk_terms_already_matched_give_no_draft(self):
        recs = self.records(risk="migration")
        for (_, data), text in zip(recs, ("a backfill", "the backfill", "backfill")):
            data["passes"][0]["findings"][0]["evidence"] = text
        lines = self.m.stats_report(recs, {"ambiguity.weasel-word": ("blocker", "risk_terms")}, 3, self.config, self.gate)[1]
        self.assertEqual(lines[-1], "  draft config: none; risk_terms.migration already matches every term")

    def test_risk_terms_need_a_risk(self):
        self.assertIn("no finding names a risk", self.report("risk_terms")[-1])

    def test_secret_patterns(self):
        lines = self.report("secret_patterns")
        self.assertEqual(lines[-2:], ["    secret_patterns:", r"      - '\b(?:reindex)\b'"])

    def test_no_literal_pattern_no_draft(self):
        recs = self.records()
        for (_, data), text in zip(recs, ("alpha", "beta", "gamma")):
            data["passes"][0]["findings"][0]["evidence"] = text
        lines = self.m.stats_report(recs, {"ambiguity.weasel-word": ("blocker", "check")}, 3, self.config, self.gate)[1]
        self.assertTrue(lines[-1].startswith("  draft: none;"), lines)


class DraftTerms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("spec_review_findings_terms", FINDINGS)

    def test_common_words_and_digits_are_not_terms(self):
        by_spec = {"a": ["then the AC-1 run is 2x fast"], "b": ["when the AC-1 run is fast"], "c": ["the AC-1 run: fast"]}
        self.assertEqual(self.m.draft_terms(by_spec, 3), [("fast", 3), ("run", 3)])

    def test_a_phrase_containing_a_term_is_dropped(self):
        by_spec = {"a": ["fails gracefully"], "b": ["fails gracefully"], "c": ["ends gracefully"]}
        self.assertEqual(self.m.draft_terms(by_spec, 2), [("gracefully", 3), ("fails", 2)])
        self.assertEqual(self.m.draft_terms({"a": ["as appropriate"], "b": ["as appropriate"]}, 2), [("appropriate", 2)])

    def test_a_spec_counts_once(self):
        self.assertEqual(self.m.draft_terms({"a": ["fast", "fast", "fast"], "b": ["slow"]}, 2), [])

    def test_multi_word_regex(self):
        self.assertEqual(self.m.term_regex(["if needed", "fast"]), r"(?i)\b(?:if\s+needed|fast)\b")


# ---------------------------------------------------------------------------
# The graduate_after setting, and usage
# ---------------------------------------------------------------------------

class Setting(TempCase):
    def test_default(self):
        gate = load("spec_review_gate_setting", GATE)
        self.assertEqual(gate.DEFAULTS["graduate_after"], 3)
        with open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8") as f:
            skill = f.read()
        for text in (skill, gate.__doc__, load("spec_review_findings_setting", FINDINGS).__doc__):
            self.assertIn("graduate_after", text)
        self.assertIn("graduate_after: %d" % gate.DEFAULTS["graduate_after"], skill)

    def test_invalid_values_are_config_errors(self):
        root = self.copy("stats-below")
        for value in ("1", "0", "-3", "'3'", "true", "2.5", "[3]"):
            with self.subTest(value=value):
                self.settings(root, "graduate_after: %s\n" % value)
                result = stats(root)
                self.assertEqual(result.returncode, 2)
                self.assertIn("error [config] settings: graduate_after must be a whole number of at least 2", result.stdout)
                spec = os.path.join(fixture("risk-low"), "specs", "add-due-dates.md")
                self.assertEqual(subprocess.run([sys.executable, GATE, "--repo", root, spec], capture_output=True).returncode, 2)

    def test_gate_accepts_the_key(self):
        root = self.copy("risk-low")
        self.settings(root, "graduate_after: 5\n")
        spec = os.path.join(root, "specs", "add-due-dates.md")
        self.assertEqual(subprocess.run([sys.executable, GATE, spec], capture_output=True).returncode,
                         subprocess.run([sys.executable, GATE, os.path.join(fixture("risk-low"), "specs", "add-due-dates.md")],
                                        capture_output=True).returncode)


class Usage(TempCase):
    def test_usage_errors(self):
        for args in (["--stats", "x.json"], ["--repo", self.tmp, "x.json"], ["--stats", "--merge"],
                     ["--stats", "--repo"], ["--stats", "--repo", os.path.join(self.tmp, "nope")]):
            with self.subTest(args=args):
                result = run(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("usage: findings", result.stderr)

    def test_repo_equals_form(self):
        self.assertEqual(run("--stats", "--repo=" + fixture("stats-below")).stdout, stats(fixture("stats-below")).stdout)

    def test_help_documents_stats(self):
        out = run("--help").stdout
        self.assertIn("findings --stats [--repo ROOT]", out)
        self.assertIn("graduate_after", out)


class Docs(unittest.TestCase):
    def read(self, *parts):
        with open(os.path.join(*parts), encoding="utf-8") as f:
            return f.read()

    def test_skill_documents_stats_and_the_separate_change(self):
        skill = self.read(SKILL_DIR, "SKILL.md")
        self.assertIn("findings --stats", skill)
        self.assertNotIn("not yet available", skill)
        self.assertIn("separate change", skill)

    def test_roadmap_v07_is_done(self):
        roadmap = self.read(PLUGIN_ROOT, "docs", "spec-review", "ROADMAP.md")
        part = roadmap[roadmap.index("### v0.7"):roadmap.index("## Decision log")]
        self.assertIn("### v0.7: Graduating rules ✅", part)
        self.assertNotIn("- [ ]", part)

    def test_plugin_version(self):
        self.assertEqual(json.loads(self.read(PLUGIN_ROOT, ".claude-plugin", "plugin.json"))["version"], "0.15.0")


if __name__ == "__main__":
    unittest.main()
