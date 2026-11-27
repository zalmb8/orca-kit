"""Tests for the v0.4 reviewers: the agent files, the seeded examples, `findings --merge`,
the review record's `passes`, and `gate --counts`.

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
EXAMPLES = os.path.join(SKILL_DIR, "examples")
EXAMPLE_REPO = os.path.join(EXAMPLES, "repo")
GATE = os.path.join(SKILL_DIR, "gate")
FINDINGS = os.path.join(SKILL_DIR, "findings")
RECORD = os.path.join(SKILL_DIR, "record")
FIXTURES = os.path.join(HERE, "fixtures")

REVIEWERS = ("ambiguity", "architecture", "security", "blast-radius", "slicer")
READ_ONLY_TOOLS = {"Read", "Grep", "Glob"}
RULE_KEY_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\.[a-z0-9]+(-[a-z0-9]+)*$")
# A rubric row: | `<reviewer>.<key>` | <when> |
RUBRIC_ROW_RE = re.compile(r"^\| `([^`]+)` \| .+ \|$", re.M)


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


def run(script, *args, **kwargs):
    return subprocess.run([sys.executable, script] + list(args), capture_output=True, text=True, **kwargs)


def agent_path(reviewer):
    return os.path.join(AGENTS_DIR, "spec-review-%s.md" % reviewer)


def parse_agent(path):
    """(frontmatter dict, body). The frontmatter is flat `key: value` lines, as Claude Code reads them."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise ValueError("%s has no frontmatter" % path)
    front = {}
    for line in m.group(1).split("\n"):
        key, sep, value = line.partition(":")
        if not sep or not re.match(r"^[a-z][a-z-]*$", key):
            raise ValueError("%s: bad frontmatter line %r" % (path, line))
        if key in front:
            raise ValueError("%s: %s twice" % (path, key))
        front[key] = value.strip()
    return front, m.group(2)


def rubric_rules(body):
    """The rule keys in the agent's rubric table, in order."""
    section = re.search(r"^## Rubric\n(.*?)^## ", body, re.S | re.M).group(1)
    return RUBRIC_ROW_RE.findall(section)


def all_rules():
    return dict((r, rubric_rules(parse_agent(agent_path(r))[1])) for r in REVIEWERS)


def write(tmp, name, data):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data, indent=2))
    return path


def finding(reviewer="ambiguity", key="weasel-word", n=1, severity="warning", kind="fix",
            section="Behavior & Edge Cases", line=10, ref="AC-1", risk=None):
    return {
        "id": "%s-%d" % (reviewer, n), "reviewer": reviewer, "severity": severity, "kind": kind,
        "rule": "%s.%s" % (reviewer, key),
        "location": {"section": section, "line": line, "ref": ref},
        "evidence": "some text", "concrete_question": "What exactly?", "suggested_fix": "Say exactly.", "risk": risk,
    }


# ---------------------------------------------------------------------------
# The agent files
# ---------------------------------------------------------------------------

class Agents(unittest.TestCase):
    def test_exactly_the_five_reviewers(self):
        found = sorted(f for f in os.listdir(AGENTS_DIR) if f.startswith("spec-review-"))
        self.assertEqual(found, sorted("spec-review-%s.md" % r for r in REVIEWERS))

    def test_frontmatter(self):
        for reviewer in REVIEWERS:
            with self.subTest(reviewer=reviewer):
                front, body = parse_agent(agent_path(reviewer))
                self.assertEqual(sorted(front), ["description", "name", "tools"])
                self.assertEqual(front["name"], "spec-review-" + reviewer)
                self.assertGreater(len(front["description"]), 80)
                self.assertIn("never the author's reasoning", front["description"])
                self.assertTrue(body.strip())

    def test_tools_are_read_only(self):
        for reviewer in REVIEWERS:
            with self.subTest(reviewer=reviewer):
                tools = [t.strip() for t in parse_agent(agent_path(reviewer))[0]["tools"].split(",")]
                self.assertTrue(tools)
                self.assertLessEqual(set(tools), READ_ONLY_TOOLS)
                self.assertIn("Read", tools)

    def test_spec_only_reviewers_cant_search(self):
        # The roadmap gives ambiguity and slicer the spec only.
        for reviewer in ("ambiguity", "slicer"):
            with self.subTest(reviewer=reviewer):
                self.assertEqual(parse_agent(agent_path(reviewer))[0]["tools"], "Read")

    def test_sections(self):
        for reviewer in REVIEWERS:
            with self.subTest(reviewer=reviewer):
                body = parse_agent(agent_path(reviewer))[1]
                headings = re.findall(r"^## (.+)$", body, re.M)
                self.assertEqual(headings, ["Input", "Context you may read", "Rubric", "Severity, kind and risk", "Output"])

    def test_rule_keys_are_well_formed_and_namespaced(self):
        for reviewer, rules in all_rules().items():
            with self.subTest(reviewer=reviewer):
                self.assertGreaterEqual(len(rules), 2)
                for rule in rules:
                    self.assertRegex(rule, RULE_KEY_RE)
                    self.assertTrue(rule.startswith(reviewer + "."), rule)

    def test_rule_keys_are_unique(self):
        every = [r for rules in all_rules().values() for r in rules]
        self.assertEqual(len(every), len(set(every)))

    def test_every_rule_named_in_the_body_is_in_the_rubric(self):
        for reviewer, rules in all_rules().items():
            with self.subTest(reviewer=reviewer):
                body = parse_agent(agent_path(reviewer))[1]
                named = set(re.findall(r"`(%s\.[a-z0-9-]+)`" % re.escape(reviewer), body))
                self.assertEqual(named, set(rules))

    def test_rule_keys_pass_the_findings_validator(self):
        m = load("spec_review_findings", FINDINGS)
        for reviewer, rules in all_rules().items():
            for rule in rules:
                f = finding(reviewer=reviewer, key=rule.split(".", 1)[1])
                text = json.dumps(f)
                self.assertEqual(m.check_finding(f, text, 0, len(text)), [], rule)

    def test_example_output_is_valid_findings(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        for reviewer, rules in all_rules().items():
            with self.subTest(reviewer=reviewer):
                body = parse_agent(agent_path(reviewer))[1]
                blocks = re.findall(r"```json\n(.*?)```", body, re.S)
                self.assertEqual(len(blocks), 1)
                result = run(FINDINGS, write(tmp, reviewer + ".json", blocks[0]))
                self.assertEqual(result.returncode, 0, result.stdout)
                for f in json.loads(blocks[0]):
                    self.assertEqual(f["reviewer"], reviewer)
                    self.assertIn(f["rule"], rules)

    def test_output_section_restates_every_field(self):
        m = load("spec_review_findings", FINDINGS)
        for reviewer in REVIEWERS:
            with self.subTest(reviewer=reviewer):
                body = parse_agent(agent_path(reviewer))[1]
                output = body[body.index("## Output"):]
                for field in m.FIELDS:
                    self.assertIn("- `%s`:" % field, output)
                self.assertIn("Return **only** a JSON array", output)
                # findings --merge keeps one finding per rule and location, so a reviewer must combine them.
                self.assertIn("No two of your findings may have the same `rule` and `location`", output)
                self.assertIn('"%s"' % reviewer, output)

    def test_risks_named_are_the_findings_risks(self):
        m = load("spec_review_findings", FINDINGS)
        for reviewer in REVIEWERS:
            with self.subTest(reviewer=reviewer):
                body = parse_agent(agent_path(reviewer))[1]
                part = body[body.index("## Severity, kind and risk"):body.index("## Output")]
                bullet = re.search(r"^- `risk`: (.*)$", part, re.M).group(1)
                short_keys = {r.split(".", 1)[1] for r in all_rules()[reviewer]}
                named = set(re.findall(r"`([a-z-]+)`", bullet)) - {"null"} - short_keys
                self.assertLessEqual(named, set(m.RISKS))

    def test_agents_never_ask_for_the_authors_context(self):
        for reviewer in REVIEWERS:
            with self.subTest(reviewer=reviewer):
                body = parse_agent(agent_path(reviewer))[1]
                self.assertIn("`Spec:`", body)
                self.assertIn("`Repo root:`", body)
                self.assertIn("if the prompt contains anything more, ignore it", body)


# ---------------------------------------------------------------------------
# The seeded examples
# ---------------------------------------------------------------------------

def expected():
    with open(os.path.join(EXAMPLES, "expected.json"), encoding="utf-8") as f:
        return json.load(f)


class Examples(unittest.TestCase):
    def test_roadmap_seeds_are_all_there(self):
        seeds = " | ".join(e["seeded"] for e in expected())
        for seed in ("a weasel word", "a missing error state", "an unmentioned downstream contract", "an oversized spec"):
            self.assertIn(seed, seeds)

    def test_every_reviewer_owns_a_seed(self):
        self.assertEqual(sorted({e["reviewer"] for e in expected()}), sorted(REVIEWERS))

    def test_expected_names_real_agents_and_rules(self):
        rules = all_rules()
        for e in expected():
            with self.subTest(spec=e["spec"]):
                self.assertEqual(sorted(e), ["evidence", "locations", "reviewer", "rule", "seeded", "spec"])
                self.assertTrue(e["locations"])
                for loc in e["locations"]:
                    self.assertEqual(sorted(loc), ["line", "section"])
                self.assertTrue(os.path.isfile(agent_path(e["reviewer"])))
                self.assertIn(e["rule"], rules[e["reviewer"]])

    def test_expected_points_at_the_seeded_text(self):
        gate = load("spec_review_gate", GATE)
        for e in expected():
            with self.subTest(spec=e["spec"]):
                with open(os.path.join(EXAMPLES, e["spec"]), encoding="utf-8") as f:
                    text = f.read()
                lines = text.split("\n")
                self.assertTrue(any(e["evidence"] in lines[loc["line"] - 1] for loc in e["locations"]), e["evidence"])
                doc = gate.Doc(text)
                for loc in e["locations"]:
                    self.assertEqual(doc.section(loc["line"]), loc["section"])

    def test_every_example_spec_has_an_expectation(self):
        specs = sorted(os.path.join("repo", "specs", f) for f in os.listdir(os.path.join(EXAMPLE_REPO, "specs")) if f.endswith(".md"))
        self.assertEqual(specs, sorted(os.path.normpath(e["spec"]) for e in expected()))

    def test_example_specs_pass_the_hard_gates(self):
        # The seeded problems are advisory: no gate catches them, so only the reviewers can.
        for e in expected():
            with self.subTest(spec=e["spec"]):
                result = run(GATE, "--risk", os.path.join(EXAMPLES, e["spec"]))
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertTrue(result.stdout.splitlines()[-1].endswith(": risk low"), result.stdout)

    def test_oversized_example_is_over_the_slicer_anchor(self):
        e = next(e for e in expected() if e["reviewer"] == "slicer")
        out = run(GATE, "--counts", os.path.join(EXAMPLES, e["spec"])).stdout
        acs = int(re.search(r", (\d+) ACs$", out.strip()).group(1))
        self.assertGreater(acs, 10)
        self.assertIn("more than 10 ACs", parse_agent(agent_path("slicer"))[1])

    def test_specs_dont_give_the_seed_away(self):
        # Reviewers read the specs and the example repo; the answers live outside it.
        for root, _, files in os.walk(EXAMPLE_REPO):
            for name in files:
                with open(os.path.join(root, name), encoding="utf-8") as f:
                    text = f.read().lower()
                with self.subTest(file=name):
                    for word in ("seeded", "expected.json", "spec-review-"):
                        self.assertNotIn(word, text)

    def test_downstream_consumer_is_in_the_example_repo_but_not_the_spec(self):
        e = next(e for e in expected() if e["reviewer"] == "blast-radius")
        with open(os.path.join(EXAMPLES, e["spec"]), encoding="utf-8") as f:
            spec = f.read()
        self.assertTrue(os.path.isfile(os.path.join(EXAMPLE_REPO, "integrations", "standup", "digest.ts")))
        self.assertNotIn("digest", spec)
        self.assertNotIn("integrations/", spec)


# ---------------------------------------------------------------------------
# findings --merge: validation, dropping rejects, deduplication
# ---------------------------------------------------------------------------

class Merge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("spec_review_findings", FINDINGS)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def merge(self, *arrays):
        paths = [write(self.tmp, "r%d.json" % i, a) for i, a in enumerate(arrays)]
        result = run(FINDINGS, "--merge", *paths)
        return result, json.loads(result.stdout)

    def test_distinct_findings_are_all_kept_in_order(self):
        a = [finding(n=1), finding(key="missing-error-state", n=2)]
        b = [finding(reviewer="slicer", key="oversized", kind="decision", severity="blocker", section="Goal & Non-Goals", line=13, ref=None)]
        result, out = self.merge(a, b)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([f["id"] for f in out], ["ambiguity-1", "ambiguity-2", "slicer-1"])
        self.assertEqual(result.stderr.splitlines()[-1],
                         "merged: 3 findings from 2 files: 1 blocker (1 decision), 2 warning, 0 nit; 0 duplicates dropped, 0 rejected")

    def test_same_rule_and_location_is_a_duplicate(self):
        a = [finding(n=1, severity="nit"), finding(n=2, severity="blocker"), finding(n=3, severity="warning")]
        result, out = self.merge(a)
        self.assertEqual(result.returncode, 0)
        self.assertEqual([f["id"] for f in out], ["ambiguity-2"])
        notes = [l for l in result.stderr.splitlines() if "[merge.duplicate]" in l]
        self.assertEqual(len(notes), 2)
        self.assertIn("same rule and location as ambiguity-2", notes[0])

    def test_section_compares_ignoring_case_and_spacing(self):
        a = [finding(n=1), finding(n=2, section="  behavior   &  edge cases ", ref="ac-1")]
        self.assertEqual(len(self.merge(a)[1]), 1)

    def test_a_different_rule_line_ref_or_section_is_kept(self):
        base = finding(n=1)
        variants = [finding(n=2, key="untestable-ac"), finding(n=3, line=11), finding(n=4, line=None),
                    finding(n=5, ref="AC-2"), finding(n=6, ref=None), finding(n=7, section="Goal & Non-Goals")]
        self.assertEqual(len(self.merge([base] + variants)[1]), 7)

    def test_same_rule_and_location_from_two_files_is_a_duplicate(self):
        # Two runs of one reviewer: ids differ, rule and location match.
        result, out = self.merge([finding(n=1)], [finding(n=2, kind="decision")])
        self.assertEqual([f["id"] for f in out], ["ambiguity-2"])

    def test_decision_wins_a_tie_then_the_first(self):
        _, out = self.merge([finding(n=1), finding(n=2, kind="decision"), finding(n=3, kind="decision")])
        self.assertEqual([f["id"] for f in out], ["ambiguity-2"])
        _, out = self.merge([finding(n=1), finding(n=2)])
        self.assertEqual([f["id"] for f in out], ["ambiguity-1"])

    def test_kept_finding_takes_the_place_of_the_first(self):
        a = [finding(n=1, severity="nit"), finding(n=2, key="needs-table"), finding(n=3, severity="blocker")]
        self.assertEqual([f["id"] for f in self.merge(a)[1]], ["ambiguity-3", "ambiguity-2"])

    def test_a_merge_never_drops_a_risk(self):
        a = [finding(n=1, severity="blocker"), finding(n=2, severity="nit", risk="migration")]
        out = self.merge(a)[1]
        self.assertEqual([f["risk"] for f in out], [None, "migration"])

    def test_findings_are_never_changed(self):
        a = [finding(n=1), finding(reviewer="security", key="trust-boundary", n=1, risk="security-boundary")]
        self.assertEqual(self.merge(a)[1], a)

    def test_rejected_findings_are_dropped_and_reported(self):
        bad = finding(n=2)
        bad["severity"] = "critical"
        result, out = self.merge([finding(n=1), bad])
        self.assertEqual(result.returncode, 1)
        self.assertEqual([f["id"] for f in out], ["ambiguity-1"])
        self.assertIn("error [finding.severity] finding #2 (ambiguity-2)", result.stderr)
        self.assertTrue(result.stderr.splitlines()[-1].endswith("0 duplicates dropped, 1 rejected"))

    def test_an_unparseable_file_drops_only_its_findings(self):
        result, out = self.merge("Here are my findings: []", [finding(n=1)])
        self.assertEqual(result.returncode, 2)
        self.assertEqual([f["id"] for f in out], ["ambiguity-1"])
        self.assertIn("error [parse]", result.stderr)

    def test_an_id_clash_across_files_is_rejected(self):
        result, out = self.merge([finding(n=1)], [finding(n=1, key="needs-table")])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(out), 1)
        self.assertIn('id "ambiguity-1" is already used in', result.stderr)

    def test_output_passes_the_validator(self):
        bad = finding(n=3)
        del bad["location"]
        _, out = self.merge([finding(n=1), finding(n=2), bad], [finding(reviewer="slicer", key="oversized", n=1)])
        path = write(self.tmp, "merged.json", out)
        self.assertEqual(run(FINDINGS, path).returncode, 0)

    def test_deterministic(self):
        a = [finding(n=i, severity=s, line=l) for i, (s, l) in enumerate(
            [("nit", 1), ("blocker", 1), ("warning", 2), ("warning", 1), ("nit", 2)], 1)]
        runs = {self.merge(a, [finding(reviewer="security", key="data-flow", n=1)])[0].stdout for _ in range(3)}
        self.assertEqual(len(runs), 1)

    def test_dedupe_function_matches_the_script(self):
        a = [finding(n=1, severity="nit"), finding(n=2, severity="blocker"), finding(n=3, line=4)]
        kept, dropped = self.m.dedupe(a)
        self.assertEqual([f["id"] for f in kept], [f["id"] for f in self.merge(a)[1]])
        self.assertEqual([(d["id"], k["id"]) for d, k in dropped], [("ambiguity-1", "ambiguity-2")])

    def test_plain_check_mode_is_unchanged(self):
        result = run(FINDINGS, os.path.join(FIXTURES, "valid", "findings.json"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertEqual(result.stderr, "")

    def test_merge_needs_files(self):
        self.assertEqual(run(FINDINGS, "--merge").returncode, 2)

    def test_rules_lists_the_merge_note(self):
        self.assertIn("merge.duplicate", run(FINDINGS, "--rules").stdout)


# ---------------------------------------------------------------------------
# The review record's passes
# ---------------------------------------------------------------------------

V03 = {
    "spec": "show-due-dates-in-list",
    "risk": {"tier": "low", "risks": [], "reasons": []},
    "sign_off": None,
}


class RecordPasses(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def check(self, data):
        return run(RECORD, write(self.tmp, "show-due-dates-in-list.json", data))

    def with_passes(self, passes, risk=None):
        data = json.loads(json.dumps(V03))
        data["passes"] = passes
        if risk:
            data["risk"] = risk
        return data

    def rules(self, result):
        return sorted(set(re.findall(r"error \[([a-z.-]+)\]", result.stdout)))

    def test_v03_records_stay_valid(self):
        self.assertEqual(self.check(V03).returncode, 0)
        for case in ("risk-signed", "risk-stale", "risk-unsigned"):
            with self.subTest(case=case):
                d = os.path.join(FIXTURES, case, "specs", "reviews")
                self.assertEqual(run(RECORD, os.path.join(d, os.listdir(d)[0])).returncode, 0)

    def test_one_pass(self):
        fs = [finding(n=1, severity="blocker"), finding(reviewer="slicer", key="oversized", n=1, severity="nit")]
        result = self.check(self.with_passes([{"findings": fs, "open_blockers": 1}]))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(result.stdout.strip().endswith(
            "ok, risk low, no sign-off, 1 pass: 2 findings: 1 blocker (0 decision), 0 warning, 1 nit"))

    def test_an_empty_pass_is_valid(self):
        self.assertEqual(self.check(self.with_passes([{"findings": [], "open_blockers": 0}])).returncode, 0)

    def test_rejected(self):
        bad_finding = finding(n=1)
        bad_finding["kind"] = "maybe"
        cases = {
            "not a list": "x",
            "no passes": [],
            "four passes": [{"findings": [], "open_blockers": 0}] * 4,
            "pass not an object": [3],
            "missing open_blockers": [{"findings": []}],
            "unknown field": [{"findings": [], "open_blockers": 0, "notes": "x"}],
            "findings not a list": [{"findings": {}, "open_blockers": 0}],
            "invalid finding": [{"findings": [bad_finding], "open_blockers": 0}],
            "duplicate id": [{"findings": [finding(n=1), finding(n=1, line=3)], "open_blockers": 0}],
            "duplicate rule and location": [{"findings": [finding(n=1), finding(n=2)], "open_blockers": 0}],
            "wrong blocker count": [{"findings": [finding(n=1, severity="blocker")], "open_blockers": 0}],
            "boolean blocker count": [{"findings": [], "open_blockers": False}],
            "risk not in the tier": [{"findings": [finding(n=1, risk="public-api")], "open_blockers": 0}],
        }
        for name, passes in cases.items():
            with self.subTest(case=name):
                result = self.check(self.with_passes(passes))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(self.rules(result), ["record.passes"], result.stdout)

    def test_a_findings_risk_in_the_tier_is_valid(self):
        risk = {"tier": "high", "risks": ["public-api"], "reasons": ["specs/x.md:42: warning [risk.public-api] ..."]}
        data = self.with_passes([{"findings": [finding(n=1, risk="public-api")], "open_blockers": 0}], risk)
        self.assertEqual(self.check(data).returncode, 0)

    def test_merge_output_is_a_valid_pass(self):
        fs = [finding(n=1, severity="nit"), finding(n=2, severity="blocker"), finding(reviewer="security", key="data-flow", n=1)]
        merged = json.loads(run(FINDINGS, "--merge", write(self.tmp, "a.json", fs)).stdout)
        blockers = sum(1 for f in merged if f["severity"] == "blocker")
        self.assertEqual(self.check(self.with_passes([{"findings": merged, "open_blockers": blockers}])).returncode, 0)

    def test_gate_reads_a_record_with_passes(self):
        # A signed record that also holds a pass is still read as a sign-off.
        tmp_repo = os.path.join(self.tmp, "repo")
        shutil.copytree(os.path.join(FIXTURES, "risk-signed"), tmp_repo)
        rec = os.path.join(tmp_repo, "specs", "reviews", "add-due-dates.json")
        with open(rec, encoding="utf-8") as f:
            data = json.load(f)
        data["passes"] = [{"findings": [finding(n=1)], "open_blockers": 0}]
        write(os.path.dirname(rec), "add-due-dates.json", data)
        result = run(GATE, "--risk", "--repo", tmp_repo, os.path.join(tmp_repo, "specs", "add-due-dates.md"))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_rules_lists_passes(self):
        self.assertIn("record.passes", run(RECORD, "--rules").stdout)


# ---------------------------------------------------------------------------
# gate --counts: what the slicer gets
# ---------------------------------------------------------------------------

class Counts(unittest.TestCase):
    def test_counts_line(self):
        spec = os.path.join(EXAMPLE_REPO, "specs", "organize-todos.md")
        result = run(GATE, "--counts", spec)
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, r"^%s: \d+ words \(ceiling 2000\), 15 ACs\n$" % re.escape(spec))

    def test_words_match_the_length_gate(self):
        gate = load("spec_review_gate", GATE)
        spec = os.path.join(EXAMPLE_REPO, "specs", "archive-completed-todos.md")
        with open(spec, encoding="utf-8") as f:
            words = gate.count_words(gate.Doc(f.read()))
        self.assertIn(": %d words" % words, run(GATE, "--counts", spec).stdout)

    def test_acs_in_code_dont_count(self):
        gate = load("spec_review_gate", GATE)
        doc = gate.Doc("---\nid: x\n---\n\n## B\n\n- **AC-1:** Given\n\n```\n- **AC-2:** Given\n```\n")
        self.assertEqual(gate.count_acs(doc), 1)

    def test_ceiling_comes_from_the_settings(self):
        result = run(GATE, "--counts", "--repo", os.path.join(FIXTURES, "gate-length"),
                     os.path.join(FIXTURES, "gate-length", "export-todos-as-json.md"))
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, r"\(ceiling \d+\)")

    def test_usage(self):
        spec = os.path.join(EXAMPLE_REPO, "specs", "organize-todos.md")
        self.assertEqual(run(GATE, "--counts", "--risk", spec).returncode, 2)
        self.assertEqual(run(GATE, "--counts", os.path.join(EXAMPLE_REPO, "nope.md")).returncode, 2)

    def test_counts_writes_nothing_and_gate_still_has_no_file_writes(self):
        with open(GATE, encoding="utf-8") as f:
            text = f.read()
        self.assertIsNone(re.search(r"open\([^)]*['\"][wax]\+?['\"]|\.write_text\(|json\.dump\(", text))


class Docs(unittest.TestCase):
    def test_skill_names_every_agent_and_script(self):
        with open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        for reviewer in REVIEWERS:
            self.assertIn("orca-kit:spec-review-%s" % reviewer, text)
        for flag in ("findings --merge", "gate --counts", "gate --risk"):
            self.assertIn(flag, text)

    def test_skill_lists_every_rule(self):
        with open(os.path.join(SKILL_DIR, "reviewers.md"), encoding="utf-8") as f:
            text = f.read()
        for rules in all_rules().values():
            for rule in rules:
                self.assertIn("`%s`" % rule, text)


if __name__ == "__main__":
    unittest.main()
