"""Tests for `gate --risk` (risk tiering and sign-off) and skills/spec-review/record.

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
GATE = os.path.join(SKILL_DIR, "gate")
RECORD = os.path.join(SKILL_DIR, "record")
FINDINGS = os.path.join(SKILL_DIR, "findings")
FIXTURES = os.path.join(HERE, "fixtures")

PROBLEM_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+): (?P<sev>error|warning) \[(?P<rule>[a-z0-9.-]+)\] "
                        r"(?P<section>[^:]+): .+\. Fix: .+\.$")
GATES_RESULT_RE = re.compile(r"^.+?: gates (ok|failed): .+$")
RISK_RESULT_RE = re.compile(r"^(?P<file>.+?): risk (?:low|high: (?P<risks>[a-z, -]+); "
                            r"(?P<state>sign-off needed|sign-off stale \(signed for [a-z, -]+\)|signed off by .+ on \d{4}-\d{2}-\d{2}))$")


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


def run(script, *args, **kwargs):
    return subprocess.run([sys.executable, script] + list(args), capture_output=True, text=True, **kwargs)


def spec_of(case):
    d = os.path.join(FIXTURES, case, "specs")
    return os.path.join(d, [f for f in sorted(os.listdir(d)) if f.endswith(".md")][0])


def risk_fixture(case, *extra):
    findings = os.path.join(FIXTURES, case, "findings.json")
    args = ["--risk", "--repo", os.path.join(FIXTURES, case)]
    if os.path.isfile(findings):
        args += ["--findings", findings]
    return run(GATE, *(args + list(extra) + [spec_of(case)]))


def problems(stdout):
    return [m.groupdict() for m in map(PROBLEM_RE.match, stdout.splitlines()) if m]


def risk_result(stdout):
    m = RISK_RESULT_RE.match(stdout.splitlines()[-1])
    return m.groupdict() if m else None


# fixture -> (exit code, risks or None for low/not computed, {(severity, rule)} of the risk step's lines)
FIXTURE_EXPECTATIONS = {
    # The v0.3 done criterion: a migration spec can't pass without a recorded sign-off...
    "risk-migration": (1, "migration", {("warning", "risk.migration"), ("error", "risk.sign-off")}),
    # ...and passes with a sign-off whose risks match.
    "risk-signed": (0, "migration", {("warning", "risk.migration")}),
    # A sign-off for other risks is stale; a record with no sign-off isn't one.
    "risk-stale": (1, "migration", {("warning", "risk.migration"), ("error", "risk.sign-off")}),
    "risk-unsigned": (1, "migration", {("warning", "risk.migration"), ("error", "risk.sign-off")}),
    # A broken record is an input error, never read as a sign-off.
    "risk-record-invalid": (2, None, {("warning", "risk.migration"), ("error", "record.sign-off"), ("error", "risk.record")}),
    # A low-risk spec needs no sign-off and no record.
    "risk-low": (0, None, set()),
    # An advisory finding's risk alone puts the spec in the high tier.
    "risk-finding": (1, "public-api", {("warning", "risk.public-api"), ("error", "risk.sign-off")}),
    # A findings file that fails the validator stops the tier being computed.
    "risk-findings-invalid": (2, None, {("error", "finding.risk"), ("error", "risk.findings")}),
    # Settings replace an area's defaults.
    "risk-config": (1, "data-model", {("warning", "risk.data-model"), ("error", "risk.sign-off")}),
    "risk-config-bad": (2, None, {("error", "config")}),
}


class Fixtures(unittest.TestCase):
    def test_every_risk_fixture_has_an_expectation(self):
        found = sorted(d for d in os.listdir(FIXTURES) if d.startswith("risk-"))
        self.assertEqual(found, sorted(FIXTURE_EXPECTATIONS))

    def test_fixtures(self):
        for case, (code, risks, expected) in sorted(FIXTURE_EXPECTATIONS.items()):
            with self.subTest(case=case):
                result = risk_fixture(case)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                found = {(p["sev"], p["rule"]) for p in problems(result.stdout)}
                found = {f for f in found if not f[1].startswith("check.")}  # the checker's own warnings
                self.assertEqual(found, expected, result.stdout)
                summary = risk_result(result.stdout)
                if risks is not None:
                    self.assertIsNotNone(summary, result.stdout)
                    self.assertEqual(summary["risks"], risks)
                elif code == 0:
                    self.assertEqual(result.stdout.splitlines()[-1], "%s: risk low" % spec_of(case))

    def test_fixture_specs_pass_the_gates(self):
        for case in sorted(FIXTURE_EXPECTATIONS):
            if case == "risk-config-bad":
                continue
            with self.subTest(case=case):
                result = run(GATE, "--repo", os.path.join(FIXTURES, case), spec_of(case))
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_every_output_line_has_a_known_shape(self):
        for case in sorted(FIXTURE_EXPECTATIONS):
            with self.subTest(case=case):
                for line in risk_fixture(case).stdout.splitlines():
                    ok = (PROBLEM_RE.match(line) or GATES_RESULT_RE.match(line) or RISK_RESULT_RE.match(line)
                          or re.match(r"^.+: risk low$", line) or re.match(r"^.+\.json: (\d+ problems?|\d+ rejected, .+)$", line))
                    self.assertTrue(ok, line)

    def test_gate_result_comes_before_risk(self):
        lines = risk_fixture("risk-migration").stdout.splitlines()
        gates = next(i for i, l in enumerate(lines) if GATES_RESULT_RE.match(l))
        self.assertTrue(all("[risk." not in l for l in lines[:gates]))
        self.assertTrue(RISK_RESULT_RE.match(lines[-1]))

    def test_stale_sign_off_names_both_risk_sets(self):
        out = risk_fixture("risk-stale").stdout
        self.assertIn("covers data-model, but the risks are now migration", out)
        self.assertTrue(out.splitlines()[-1].endswith("sign-off stale (signed for data-model)"))

    def test_signed_names_who_and_when(self):
        self.assertTrue(risk_fixture("risk-signed").stdout.splitlines()[-1].endswith(
            "risk high: migration; signed off by Sam Rivera on 2026-11-27"))

    def test_finding_reason_names_the_finding(self):
        out = risk_fixture("risk-finding").stdout
        self.assertIn(":44: warning [risk.public-api] Interfaces & Data Contracts: finding blast-radius-1", out)

    def test_finding_raises_risk_whatever_its_severity(self):
        # risk-finding's risky finding is a warning, not a blocker.
        with open(os.path.join(FIXTURES, "risk-finding", "findings.json"), encoding="utf-8") as f:
            risky = [x for x in json.load(f) if x["risk"]]
        self.assertEqual([x["severity"] for x in risky], ["warning"])

    def test_same_spec_is_low_without_its_findings(self):
        result = run(GATE, "--risk", "--repo", os.path.join(FIXTURES, "risk-finding"), spec_of("risk-finding"))
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.splitlines()[-1].endswith(": risk low"))


class Determinism(unittest.TestCase):
    def test_same_input_same_output(self):
        for case in sorted(FIXTURE_EXPECTATIONS):
            with self.subTest(case=case):
                runs = [risk_fixture(case) for _ in range(3)]
                self.assertEqual(len({(r.returncode, r.stdout, r.stderr) for r in runs}), 1)

    def test_output_does_not_depend_on_the_environment(self):
        env = dict(os.environ, TZ="Pacific/Kiritimati", LANG="C", PYTHONHASHSEED="54321")
        for case in ("risk-migration", "risk-signed", "risk-finding"):
            with self.subTest(case=case):
                a = risk_fixture(case)
                findings = os.path.join(FIXTURES, case, "findings.json")
                extra = ["--findings", findings] if os.path.isfile(findings) else []
                b = run(GATE, *(["--risk", "--repo", os.path.join(FIXTURES, case)] + extra + [spec_of(case)]), env=env)
                self.assertEqual((a.returncode, a.stdout), (b.returncode, b.stdout))

    def test_without_risk_the_gate_output_is_unchanged(self):
        result = run(GATE, "--repo", os.path.join(FIXTURES, "risk-migration"), spec_of("risk-migration"))
        self.assertNotIn("risk", "\n".join(l for l in result.stdout.splitlines() if "[check." not in l and "migrat" not in l))
        self.assertTrue(GATES_RESULT_RE.match(result.stdout.splitlines()[-1]))


class NeverWritesASignOff(unittest.TestCase):
    """v0.3 done criterion: the skill never records a sign-off itself; no script writes one."""

    def snapshot(self, root):
        out = {}
        for d, _, files in os.walk(root):
            for f in files:
                p = os.path.join(d, f)
                with open(p, "rb") as fh:
                    out[p] = fh.read()
        return out

    def test_gate_and_record_write_nothing(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        for case in ("risk-migration", "risk-unsigned", "risk-stale"):
            shutil.copytree(os.path.join(FIXTURES, case), os.path.join(tmp, case))
        before = self.snapshot(tmp)
        for case in ("risk-migration", "risk-unsigned", "risk-stale"):
            spec = os.path.join(tmp, case, "specs", "add-due-dates.md")
            self.assertEqual(run(GATE, "--risk", "--repo", os.path.join(tmp, case), spec).returncode, 1)
            rec = os.path.join(tmp, case, "specs", "reviews", "add-due-dates.json")
            if os.path.exists(rec):
                run(RECORD, rec)
        self.assertEqual(self.snapshot(tmp), before)
        self.assertFalse(os.path.exists(os.path.join(tmp, "risk-migration", "specs", "reviews")))

    def test_scripts_have_no_file_writes(self):
        for script in (GATE, RECORD):
            with open(script, encoding="utf-8") as f:
                text = f.read()
            with self.subTest(script=os.path.basename(script)):
                self.assertIsNone(re.search(r"open\([^)]*['\"][wax]\+?['\"]|\.write_text\(|json\.dump\(|os\.(rename|replace|remove)\(", text))


class Classifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("spec_review_gate", GATE)

    def config(self, terms=None, paths=None):
        res, globs = self.m.risk_tables(terms or {}, paths or {})
        return {"risk_res": res, "risk_globs": globs}

    def risks(self, body, **kw):
        return sorted({r.risk for r in self.m.classify(self.m.Doc(body + "\n"), self.config(**kw))})

    def test_each_area_by_term_and_path(self):
        cases = {
            "Users sign in with OAuth.": "auth",
            "Check permissions in `src/auth/guard.ts`.": "auth",
            "The webhook crosses a trust boundary.": "security-boundary",
            "Secrets move to `src/crypto/keys.ts`.": "security-boundary",
            "Add a foreign key to todos.": "data-model",
            "Edit `prisma/schema.prisma`.": "data-model",
            "A backfill sets every row.": "migration",
            "New file `db/migrate/0007_due.rb`.": "migration",
            "Refunds go back to the card.": "billing",
            "Change `services/billing/plan.ts`.": "billing",
            "Add a REST endpoint for todos.": "public-api",
            "Edit `api/openapi.yaml`.": "public-api",
            "This is a breaking change for v1 users.": "breaking-change",
            "The `--all` flag is deprecated.": "breaking-change",
        }
        for body, area in cases.items():
            with self.subTest(body=body):
                self.assertIn(area, self.risks(body))

    def test_ordinary_text_is_low(self):
        for body in ("Design input comes from the store.", "Authors write the spec.", "The table lists each AC.",
                     "Permissions errors print to stderr.", "Run `git checkout main`.", "See `src/models.ts`? No.",
                     "A decision table, not prose.", "Billable hours are out of scope."):
            with self.subTest(body=body):
                self.assertEqual(self.risks(body), [])

    def test_words_join_by_space_dash_underscore_or_nothing(self):
        for body in ("sign in", "sign-in", "sign_in", "signin", "Sign In"):
            with self.subTest(body=body):
                self.assertEqual(self.risks(body), ["auth"])

    def test_frontmatter_is_not_classified(self):
        self.assertEqual(self.risks("---\ntitle: Migrate billing\n---\n\n## Goal\n\nNothing risky."), [])

    def test_one_reason_per_risk_and_pattern(self):
        body = "## A\n\nmigration one\nmigration two\n`db/migrations/1.sql`\n"
        reasons = self.m.classify(self.m.Doc(body), self.config())
        self.assertEqual([(r.risk, r.line) for r in reasons], [("migration", 3), ("migration", 5)])
        self.assertIn("(and on 1 more line)", reasons[0].message)

    def test_configured_area_replaces_its_defaults_only(self):
        self.assertEqual(self.risks("A flyway script and a refund.", terms={"migration": ["flyway"]}), ["billing", "migration"])
        self.assertEqual(self.risks("A backfill.", terms={"migration": ["flyway"]}), [])
        self.assertEqual(self.risks("`ops/jobs/x.py`", paths={"migration": ["*/jobs/*"]}), ["migration"])


class RiskConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("spec_review_gate", GATE)

    def load_config(self, text):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        os.makedirs(os.path.join(tmp, ".orca-kit"))
        with open(os.path.join(tmp, ".orca-kit", "spec-review.yml"), "w", encoding="utf-8") as f:
            f.write(text)
        return self.m.load_config(tmp)[0]

    def test_accepted(self):
        config = self.load_config("risk_terms:\n  billing: ['plan change*']\n  auth: []\nrisk_paths:\n  migration:\n    - 'ops/*'\n")
        self.assertEqual([t for t, _ in config["risk_res"]["billing"]], ["plan change*"])
        self.assertEqual(config["risk_res"]["auth"], [])
        self.assertEqual(config["risk_globs"]["migration"], ["ops/*"])
        self.assertEqual(config["risk_globs"]["billing"], self.m.DEFAULT_RISK_PATHS["billing"])

    def test_rejected(self):
        for text in ("risk_terms: ['a']\n", "risk_terms:\n  payments: ['a']\n", "risk_terms:\n  billing: 'a'\n",
                     "risk_terms:\n  billing: ['Plan']\n", "risk_terms:\n  billing: ['a.b']\n", "risk_terms:\n  billing: ['']\n",
                     "risk_paths:\n  billing: [3]\n", "risk_paths:\n  billing: ['  ']\n", "risk_tier: high\n"):
            with self.subTest(text=text):
                with self.assertRaises(self.m.ConfigError):
                    self.load_config(text)

    def test_risks_agree_with_the_findings_format(self):
        findings = load("spec_review_findings", FINDINGS)
        record = load("spec_review_record", RECORD)
        with open(os.path.join(SKILL_DIR, "findings.schema.json"), encoding="utf-8") as f:
            schema = json.load(f)
        schema_risks = [r for r in schema["$defs"]["finding"]["properties"]["risk"]["enum"] if r is not None]
        self.assertEqual(tuple(self.m.RISKS), tuple(findings.RISKS))
        self.assertEqual(tuple(record.RISKS), tuple(findings.RISKS))
        self.assertEqual(sorted(schema_risks), sorted(findings.RISKS))
        self.assertEqual(sorted(self.m.DEFAULT_RISK_TERMS), sorted(findings.RISKS))
        self.assertEqual(sorted(self.m.DEFAULT_RISK_PATHS), sorted(findings.RISKS))

    def test_defaults_are_valid_settings(self):
        for area, terms in self.m.DEFAULT_RISK_TERMS.items():
            for t in terms:
                self.m.check_term(t, area)

    def test_defaults_are_documented(self):
        with open(os.path.join(SKILL_DIR, "risk.md"), encoding="utf-8") as f:
            text = f.read()
        rows = dict((m.group(1), (m.group(2), m.group(3)))
                    for m in re.finditer(r"^\| `([a-z-]+)` \| (.*?) \| (.*?) \|$", text, re.M))
        self.assertEqual(sorted(rows), sorted(self.m.RISKS))
        for area in self.m.RISKS:
            with self.subTest(area=area):
                terms, paths = rows[area]
                self.assertEqual(re.findall(r"`([^`]+)`", terms), self.m.DEFAULT_RISK_TERMS[area])
                self.assertEqual(re.findall(r"`([^`]+)`", paths), self.m.DEFAULT_RISK_PATHS[area])

    def test_documented_settings_example_is_valid(self):
        with open(os.path.join(SKILL_DIR, "risk.md"), encoding="utf-8") as f:
            example = re.search(r"```yaml\n(.*?)```", f.read(), re.S).group(1)
        config = self.load_config(example)
        self.assertTrue(config["risk_terms"] or config["risk_paths"])


class Usage(unittest.TestCase):
    def test_findings_needs_risk(self):
        self.assertEqual(run(GATE, "--findings", os.path.join(FIXTURES, "valid", "findings.json"), spec_of("risk-low")).returncode, 2)

    def test_findings_needs_one_spec(self):
        result = run(GATE, "--risk", "--findings", os.path.join(FIXTURES, "valid", "findings.json"),
                     spec_of("risk-low"), spec_of("risk-signed"))
        self.assertEqual(result.returncode, 2)

    def test_several_specs_with_risk(self):
        result = run(GATE, "--risk", spec_of("risk-low"), spec_of("risk-migration"))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(sum(1 for l in result.stdout.splitlines() if RISK_RESULT_RE.match(l) or l.endswith(": risk low")), 2)

    def test_gates_lists_the_risk_rules(self):
        m = load("spec_review_gate", GATE)
        out = run(GATE, "--gates").stdout
        for rule_id in m.RISK_RULE_TEXT:
            self.assertIn(rule_id, out)


# ---------------------------------------------------------------------------
# The record validator
# ---------------------------------------------------------------------------

VALID = {
    "spec": "add-due-dates",
    "risk": {"tier": "high", "risks": ["migration"], "reasons": ["specs/add-due-dates.md:37: warning [risk.migration] ..."]},
    "sign_off": {"signed_off_by": "Sam Rivera", "signed_off_on": "2026-11-27", "risks": ["migration"]},
}


class Record(unittest.TestCase):
    def check(self, data, name="add-due-dates.json", raw=None):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else json.dumps(data, indent=2))
        return run(RECORD, path)

    def variant(self, **changes):
        data = json.loads(json.dumps(VALID))
        for dotted, value in changes.items():
            target = data
            parts = dotted.split("__")
            for p in parts[:-1]:
                target = target[p]
            if value is KeyError:
                del target[parts[-1]]
            else:
                target[parts[-1]] = value
        return data

    def rules(self, result):
        return sorted({p["rule"] for p in problems(result.stdout)})

    def test_valid(self):
        result = self.check(VALID)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(result.stdout.strip().endswith("ok, risk high (migration), signed off by Sam Rivera on 2026-11-27"))

    def test_valid_low_without_sign_off(self):
        data = self.variant(risk={"tier": "low", "risks": [], "reasons": []}, sign_off=None)
        result = self.check(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(result.stdout.strip().endswith("ok, risk low, no sign-off"))

    def test_fixture_records(self):
        for case in ("risk-signed", "risk-stale", "risk-unsigned"):
            with self.subTest(case=case):
                self.assertEqual(run(RECORD, os.path.join(FIXTURES, case, "specs", "reviews", "add-due-dates.json")).returncode, 0)

    def test_rejected(self):
        cases = [
            ({"spec": KeyError}, "record.fields"),
            ({"gates": []}, "record.fields"),
            ({"spec": "other-spec"}, "record.spec"),
            ({"spec": "Add Due"}, "record.spec"),
            ({"risk": "high"}, "record.risk"),
            ({"risk__tier": "medium"}, "record.risk"),
            ({"risk__tier": "low"}, "record.risk"),
            ({"risk__risks": ["perf"]}, "record.risk"),
            ({"risk__risks": ["migration", "migration"]}, "record.risk"),
            ({"risk__reasons": []}, "record.risk"),
            ({"risk__reasons": [""]}, "record.risk"),
            ({"risk__extra": 1}, "record.risk"),
            ({"sign_off": "yes"}, "record.sign-off"),
            ({"sign_off__signed_off_by": ""}, "record.sign-off"),
            ({"sign_off__signed_off_by": KeyError}, "record.sign-off"),
            ({"sign_off__signed_off_on": "2026-02-30"}, "record.sign-off"),
            ({"sign_off__signed_off_on": "27/11/2026"}, "record.sign-off"),
            ({"sign_off__risks": []}, "record.sign-off"),
            ({"sign_off__risks": ["billing", "billing"]}, "record.sign-off"),
            ({"sign_off__approved": True}, "record.sign-off"),
        ]
        for changes, rule in cases:
            with self.subTest(changes=changes):
                result = self.check(self.variant(**changes))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(self.rules(result), [rule], result.stdout)

    def test_not_an_object(self):
        for raw in ("[]", "{not json", ""):
            with self.subTest(raw=raw):
                self.assertEqual(self.check(None, raw=raw).returncode, 2)

    def test_problem_line_points_at_the_field(self):
        result = self.check(self.variant(sign_off__signed_off_on="2026-13-01"))
        self.assertEqual([p["line"] for p in problems(result.stdout)], ["14"])

    def test_rules_lists_every_rule(self):
        m = load("spec_review_record", RECORD)
        out = run(RECORD, "--rules").stdout
        for rule_id in m.RULE_TEXT:
            self.assertIn(rule_id, out)

    def test_documented_example_is_valid(self):
        with open(os.path.join(SKILL_DIR, "risk.md"), encoding="utf-8") as f:
            example = re.search(r"```json\n(.*?)```", f.read(), re.S).group(1)
        result = self.check(None, name="add-due-dates.json", raw=example)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_usage(self):
        self.assertEqual(run(RECORD).returncode, 2)
        self.assertEqual(run(RECORD, "--nope", "x.json").returncode, 2)


if __name__ == "__main__":
    unittest.main()
