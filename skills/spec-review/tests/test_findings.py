"""Tests for skills/spec-review/findings.

Run from the repo root:

    python3 -m unittest discover -s skills/spec-review/tests -v
"""

import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
FINDINGS = os.path.join(SKILL_DIR, "findings")
SCHEMA = os.path.join(SKILL_DIR, "findings.schema.json")
FIXTURES = os.path.join(HERE, "fixtures")
NAME = "findings.json"

PROBLEM_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+): error \[(?P<rule>[a-z.-]+)\] (?P<where>[^:]+): .+\. Fix: .+\.$")
SUMMARY_RE = re.compile(r"^(?P<file>.+?): (?:ok, (?P<n>\d+) findings?|(?P<rejected>\d+) rejected, (?P<kept>\d+) kept): "
                        r"(?P<blocker>\d+) blocker \((?P<decision>\d+) decision\), (?P<nit>\d+) nit$")


def run(*args):
    return subprocess.run([sys.executable, FINDINGS] + list(args), capture_output=True, text=True)


def fixture(case):
    return os.path.join(FIXTURES, case, NAME)


def problems(stdout):
    return [m.groupdict() for m in map(PROBLEM_RE.match, stdout.splitlines()) if m]


def summary(stdout):
    m = SUMMARY_RE.match(stdout.splitlines()[-1])
    return m.groupdict() if m else None


def load_module():
    loader = importlib.machinery.SourceFileLoader("spec_review_findings", FINDINGS)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("spec_review_findings", loader))
    loader.exec_module(module)
    return module


# fixture directory -> (exit code, {(rule, where), ...} it must report, and nothing else)
FIXTURE_EXPECTATIONS = {
    "valid": (0, set()),
    "valid-empty": (0, set()),
    # The v0.1 done criterion: bad severity, no location, no concrete question.
    "bad-severity": (1, {("finding.severity", "finding #1 (ambiguity-3)")}),
    "missing-location": (1, {("finding.location", "finding #1 (ambiguity-3)")}),
    "missing-concrete-question": (1, {("finding.concrete-question", "finding #1 (ambiguity-3)")}),
    # The rest of the format.
    "bad-kind": (1, {("finding.kind", "finding #2 (security-1)")}),
    "bad-risk": (1, {("finding.risk", "finding #3 (blast-radius-2)")}),
    "missing-risk": (1, {("finding.risk", "finding #1 (ambiguity-3)")}),
    "location-no-section": (1, {("finding.location", "finding #1 (ambiguity-3)")}),
    "location-bad-line": (1, {("finding.location", "finding #1 (ambiguity-3)")}),
    "empty-concrete-question": (1, {("finding.concrete-question", "finding #1 (ambiguity-3)")}),
    "question-not-a-question": (1, {("finding.concrete-question", "finding #1 (ambiguity-3)")}),
    "empty-suggested-fix": (1, {("finding.suggested-fix", "finding #1 (ambiguity-3)")}),
    "empty-evidence": (1, {("finding.evidence", "finding #1 (ambiguity-3)")}),
    "unknown-field": (1, {("finding.fields", "finding #1 (ambiguity-3)")}),
    "bad-rule": (1, {("finding.rule", "finding #1 (ambiguity-3)")}),
    "rule-wrong-reviewer": (1, {("finding.rule", "finding #1 (ambiguity-3)")}),
    "bad-id": (1, {("finding.id", "finding #1")}),
    "duplicate-id": (1, {("finding.id", "finding #4 (ambiguity-3)")}),
    "finding-not-object": (1, {("finding.object", "finding #2")}),
    "two-rejected": (1, {("finding.severity", "finding #1 (ambiguity-3)"), ("finding.location", "finding #4 (slicer-1)")}),
    # Severity is two levels, fixed by the rule (v0.5).
    "severity-warning": (1, {("finding.severity", "finding #1 (ambiguity-3)")}),
    "severity-not-the-rules": (1, {("finding.severity", "finding #1 (ambiguity-3)")}),
    "rule-not-in-table": (1, {("finding.rule", "finding #1 (ambiguity-3)")}),
    # Not a findings file at all.
    "not-json": (2, {("parse", "file")}),
    "not-array": (2, {("parse", "file")}),
}


class Fixtures(unittest.TestCase):
    def test_every_fixture_has_an_expectation(self):
        found = sorted(d for d in os.listdir(FIXTURES) if not d.startswith(("gate-", "risk-", "loop-", "pause-", "stats-", "handson-")))  # gate-*: test_gate.py; risk-*: test_risk.py; loop-*: test_loop.py; pause-*: test_pause.py; stats-*: test_stats.py; handson-*: test_handson.py
        self.assertEqual(found, sorted(FIXTURE_EXPECTATIONS))

    def test_fixtures(self):
        for case, (code, expected) in sorted(FIXTURE_EXPECTATIONS.items()):
            with self.subTest(case=case):
                result = run(fixture(case))
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                found = {(p["rule"], p["where"]) for p in problems(result.stdout)}
                self.assertEqual(found, expected, result.stdout)

    def test_every_output_line_is_a_problem_or_summary(self):
        for case in sorted(FIXTURE_EXPECTATIONS):
            with self.subTest(case=case):
                lines = run(fixture(case)).stdout.splitlines()
                self.assertTrue(lines)
                for line in lines:
                    self.assertTrue(PROBLEM_RE.match(line) or SUMMARY_RE.match(line), line)

    def test_problem_lines_point_at_the_offending_field(self):
        result = run(fixture("bad-severity"))
        line = int(problems(result.stdout)[0]["line"])
        with open(fixture("bad-severity"), encoding="utf-8") as f:
            self.assertIn('"severity": "high"', f.read().splitlines()[line - 1])


class DoneCriterion(unittest.TestCase):
    """v0.1: malformed findings are rejected with the reason."""

    def assert_rejected(self, case, reason):
        result = run(fixture(case))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(reason, result.stdout)
        s = summary(result.stdout)
        self.assertEqual((s["rejected"], s["kept"]), ("1", "3"))

    def test_bad_severity(self):
        self.assert_rejected("bad-severity", 'severity is "high", not one of blocker, nit')

    def test_no_location(self):
        self.assert_rejected("missing-location", "location is missing")

    def test_no_concrete_question(self):
        self.assert_rejected("missing-concrete-question", "concrete_question is missing")


class RuleFixedSeverity(unittest.TestCase):
    """v0.5: severity is blocker | nit, and the rule table fixes it."""

    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def test_warning_is_rejected_with_the_fix(self):
        out = run(fixture("severity-warning")).stdout
        self.assertIn('severity is "warning", not one of blocker, nit. Fix: Use blocker or nit, as the rule decides; '
                      'warning is no longer a severity.', out)

    def test_severity_must_be_the_rules_level(self):
        out = run(fixture("severity-not-the-rules")).stdout
        self.assertIn('severity is "nit", but ambiguity.weasel-word is a blocker rule. Fix: Set severity to blocker', out)

    def test_rule_must_be_in_the_table(self):
        out = run(fixture("rule-not-in-table")).stdout
        self.assertIn('rule "ambiguity.wishy-washy" isn\'t in the rule table. Fix: Use one of ambiguity.', out)

    def test_table_is_read_from_the_agents(self):
        table = self.m.read_rule_table()
        self.assertEqual(set(table.values()), set(self.m.SEVERITIES))
        self.assertEqual(table["ambiguity.weasel-word"], "blocker")
        self.assertEqual(table["ambiguity.vague-prose"], "nit")
        self.assertEqual(sorted({r.split(".")[0] for r in table}),
                         ["ambiguity", "architecture", "blast-radius", "security", "slicer"])

    def write_agent(self, tmp, name, rubric):
        with open(os.path.join(tmp, "spec-review-%s.md" % name), "w", encoding="utf-8") as f:
            f.write("---\nname: spec-review-%s\n---\n\n## Rubric\n\n%s\n## Output\n" % (name, rubric))

    def test_a_broken_table_is_an_error(self):
        header = "| Rule | Level | Report when |\n|---|---|---|\n"
        cases = {
            "no table": "Just prose.\n",
            "old two-column table": "| Rule | Report when |\n|---|---|\n| `x.a` | when |\n",
            "level not blocker or nit": header + "| `x.a` | warning | when |\n",
            "wrong prefix": header + "| `y.a` | nit | when |\n",
            "listed twice": header + "| `x.a` | nit | when |\n| `x.a` | blocker | when |\n",
            "empty table": header,
        }
        for name, rubric in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                self.write_agent(tmp, "x", rubric)
                with self.assertRaises(self.m.RuleTableError):
                    self.m.read_rule_table(tmp)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(self.m.RuleTableError):
                self.m.read_rule_table(tmp)
            self.write_agent(tmp, "x", header + "| `x.a` | nit | when |\n| `x.b` | blocker | when |\n")
            self.assertEqual(self.m.read_rule_table(tmp), {"x.a": "nit", "x.b": "blocker"})

    def test_rules_lists_the_table(self):
        out = run("--rules").stdout
        self.assertRegex(out, r"(?m)^  ambiguity\.weasel-word +blocker$")
        self.assertRegex(out, r"(?m)^  slicer\.independent-parts +nit$")


class Summary(unittest.TestCase):
    def test_valid_file_counts_by_severity(self):
        result = run(fixture("valid"))
        self.assertEqual(result.stdout.strip(), "%s: ok, 4 findings: 2 blocker (1 decision), 2 nit" % fixture("valid"))

    def test_empty_file_is_valid(self):
        self.assertEqual(summary(run(fixture("valid-empty")).stdout)["n"], "0")

    def test_rejected_findings_are_dropped_from_the_counts(self):
        s = summary(run(fixture("two-rejected")).stdout)
        self.assertEqual((s["rejected"], s["kept"], s["blocker"], s["nit"]), ("2", "2", "1", "1"))


class SchemaAgrees(unittest.TestCase):
    """The hand-written validator and findings.schema.json state the same format."""

    @classmethod
    def setUpClass(cls):
        cls.m = load_module()
        with open(SCHEMA, encoding="utf-8") as f:
            cls.schema = json.load(f)
        cls.finding = cls.schema["$defs"]["finding"]

    def test_schema_is_an_array_of_findings(self):
        self.assertEqual(self.schema["type"], "array")
        self.assertEqual(self.schema["items"], {"$ref": "#/$defs/finding"})

    def test_fields(self):
        self.assertEqual(self.finding["required"], list(self.m.FIELDS))
        self.assertEqual(sorted(self.finding["properties"]), sorted(self.m.FIELDS))
        self.assertIs(self.finding["additionalProperties"], False)
        loc = self.finding["properties"]["location"]
        self.assertEqual(loc["required"], list(self.m.LOCATION_FIELDS))
        self.assertIs(loc["additionalProperties"], False)

    def test_enums(self):
        props = self.finding["properties"]
        self.assertEqual(props["severity"]["enum"], list(self.m.SEVERITIES))
        self.assertEqual(props["kind"]["enum"], list(self.m.KINDS))
        self.assertEqual(props["risk"]["enum"], [None] + list(self.m.RISKS))

    def test_patterns(self):
        props = self.finding["properties"]
        self.assertEqual(props["id"]["pattern"], self.m.ID_RE.pattern)
        self.assertEqual(props["reviewer"]["pattern"], self.m.REVIEWER_RE.pattern)
        self.assertEqual(props["rule"]["pattern"], self.m.RULE_RE.pattern)

    def test_roadmap_example_is_valid(self):
        with open(os.path.join(SKILL_DIR, "..", "..", "docs", "spec-review", "ROADMAP.md"), encoding="utf-8") as f:
            text = f.read()
        block = re.search(r"## Findings format\n.*?```json\n(.*?)```", text, re.S).group(1)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, NAME)
            with open(path, "w", encoding="utf-8") as f:
                f.write("[%s]" % block)
            result = run(path)
        self.assertEqual(result.returncode, 0, result.stdout)


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def check(self, finding):
        text = json.dumps([finding])
        (value, start, end), = self.m.elements(text)
        return {p[1] for p in self.m.check_finding(value, text, start, end)}

    def valid(self, **changes):
        with open(fixture("valid"), encoding="utf-8") as f:
            finding = json.load(f)[0]
        finding.update(changes)
        return finding

    def test_every_rule_has_text(self):
        with open(FINDINGS, encoding="utf-8") as f:
            used = set(re.findall(r'"(finding\.[a-z-]+)"', f.read()))
        used |= {self.m.rule_of(f) for f in self.m.FIELDS}
        self.assertEqual(used, set(self.m.RULE_TEXT))

    def test_valid_finding(self):
        self.assertEqual(self.check(self.valid()), set())

    def test_every_risk_is_accepted(self):
        for risk in (None,) + self.m.RISKS:
            with self.subTest(risk=risk):
                self.assertEqual(self.check(self.valid(risk=risk)), set())

    def test_booleans_are_not_line_numbers(self):
        self.assertEqual(self.check(self.valid(location={"section": "Goal", "line": True, "ref": None})), {"finding.location"})

    def test_location_must_be_an_object(self):
        self.assertEqual(self.check(self.valid(location="Behavior & Edge Cases")), {"finding.location"})

    def test_location_extra_field(self):
        loc = {"section": "Goal", "line": 1, "ref": None, "column": 3}
        self.assertEqual(self.check(self.valid(location=loc)), {"finding.location"})

    def test_enum_values_are_case_sensitive(self):
        self.assertEqual(self.check(self.valid(severity="Blocker", kind="Fix")), {"finding.severity", "finding.kind"})

    def test_non_string_text_fields(self):
        self.assertEqual(self.check(self.valid(evidence=None, suggested_fix=3)), {"finding.evidence", "finding.suggested-fix"})

    def test_every_missing_field_has_its_own_rule(self):
        for name in self.m.FIELDS:
            with self.subTest(field=name):
                finding = self.valid()
                del finding[name]
                self.assertIn(self.m.rule_of(name), self.check(finding))


class ExitCodes(unittest.TestCase):
    def test_no_arguments_is_a_usage_error(self):
        result = run()
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)

    def test_unknown_option_is_a_usage_error(self):
        self.assertEqual(run("--stats", fixture("valid")).returncode, 2)

    def test_missing_file_is_a_usage_error(self):
        result = run(os.path.join(FIXTURES, "no-such", NAME))
        self.assertEqual(result.returncode, 2)
        self.assertIn("[usage]", result.stdout)

    def test_rejection_and_pass_together_exit_1(self):
        result = run(fixture("valid"), fixture("bad-severity"))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(result.stdout.splitlines()), 3)

    def test_parse_error_wins_over_rejection(self):
        self.assertEqual(run(fixture("bad-severity"), fixture("not-json")).returncode, 2)

    def test_help_and_rules_exit_0(self):
        for arg in ("--help", "--rules"):
            with self.subTest(arg=arg):
                result = run(arg)
                self.assertEqual(result.returncode, 0)
                self.assertTrue(result.stdout)


if __name__ == "__main__":
    unittest.main()
