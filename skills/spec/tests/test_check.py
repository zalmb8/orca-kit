"""Tests for skills/spec/check.

Run from the repo root:

    python3 -m unittest discover -s skills/spec/tests -v
"""

import glob
import importlib.machinery
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC_DIR = os.path.dirname(HERE)
CHECK = os.path.join(SPEC_DIR, "check")
EXAMPLES = os.path.join(SPEC_DIR, "examples")
FIXTURES = os.path.join(HERE, "fixtures")
NAME = "export-todos-as-json.md"

PROBLEM_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+): (?P<sev>error|warning) \[(?P<rule>[a-z.-]+)\] (?P<section>[^:]+): .+\. Fix: .+\.$")


def run(*args):
    return subprocess.run([sys.executable, CHECK] + list(args), capture_output=True, text=True)


def example(status):
    return os.path.join(EXAMPLES, status, NAME)


def fixture(case):
    return os.path.join(FIXTURES, case, NAME)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def problems(stdout):
    found = []
    for line in stdout.splitlines():
        m = PROBLEM_RE.match(line)
        if m:
            found.append(m.groupdict())
    return found


def load_module():
    loader = importlib.machinery.SourceFileLoader("spec_check", CHECK)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("spec_check", loader))
    loader.exec_module(module)
    return module


# fixture directory -> (exit code, {(severity, rule), ...} it must report, and nothing else)
FIXTURE_EXPECTATIONS = {
    # The v0.5 done criterion.
    "accepted-open-question": (1, {("error", "no-open-questions")}),
    "accepted-tbd": (1, {("error", "no-tbd")}),
    "accepted-no-verify": (1, {("error", "ac.verify")}),
    # Frontmatter.
    "bad-id": (1, {("error", "frontmatter.id")}),
    "bad-status-and-dates": (1, {("error", "frontmatter.status"), ("error", "frontmatter.dates")}),
    "accepted-unsigned": (1, {("error", "frontmatter.accepted")}),
    "accepted-by-on-draft": (1, {("error", "frontmatter.unaccepted")}),
    # draft rules.
    "missing-heading": (1, {("error", "spec.sections")}),
    "edge-case-missing-ac": (1, {("error", "edge.ac")}),
    "draft-missing-never": (1, {("error", "guard.labels")}),
    "draft-free-prose": (1, {("error", "ac.only")}),
    "draft-ac-format": (1, {("error", "ac.format")}),
    # accepted guardrails.
    "accepted-thin-guardrails": (1, {("error", "guard.items"), ("error", "guard.decisions")}),
    # idea rules.
    "idea-no-open-questions": (1, {("error", "idea.sections")}),
    "idea-long-goal": (1, {("error", "idea.goal-length")}),
    # Word budgets: a warning at draft, an error at accepted.
    "draft-over-budget": (0, {("warning", "budget")}),
    "accepted-over-budget": (1, {("error", "budget")}),
    # done: accepted content rules only; fields from future skills are ignored.
    "pass-done-future-fields": (0, set()),
    # Parse errors.
    "bad-frontmatter-nested": (2, {("error", "parse")}),
    "bad-frontmatter-unclosed": (2, {("error", "parse")}),
    # v0.7: the Verification Gate matches the ACs and Environment & Commands.
    "accepted-gate-mismatch": (1, {("error", "gate.matches-acs")}),
    "accepted-gate-suite": (1, {("error", "gate.suite")}),
    # v0.7: edge-case categories, an error at accepted and a warning at draft.
    "accepted-missing-category": (1, {("error", "edge.categories")}),
    "draft-missing-category": (0, {("warning", "edge.categories")}),
    # v0.7: heuristics are warnings.
    "accepted-nongoal-no-path": (0, {("warning", "nongoal.path")}),
    "accepted-verify-runner": (0, {("warning", "verify.runner")}),
    # v0.7: concrete examples and typed contracts.
    "accepted-bad-example": (1, {("error", "ac.example")}),
    "accepted-old-contracts": (1, {("error", "contract.labels")}),
    "accepted-contract-format": (1, {("error", "contract.format")}),
    "accepted-no-contracts": (1, {("error", "contract.items")}),
}


class ExamplesPass(unittest.TestCase):
    def test_each_example_passes(self):
        for status in ("idea", "draft", "accepted"):
            with self.subTest(status=status):
                result = run(example(status))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.strip(), "%s: ok (%s)" % (example(status), status))

    def test_updated_example_passes(self):
        path = os.path.join(EXAMPLES, "updated", NAME)
        result = run(path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "%s: ok (accepted)" % path)

    def test_all_examples_in_one_call(self):
        result = run(*sorted(glob.glob(os.path.join(EXAMPLES, "*", "*.md"))))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(len(result.stdout.splitlines()), 4)

    def test_accepted_example_passes_as_accepted(self):
        self.assertEqual(run("--as", "accepted", example("accepted")).returncode, 0)


class DoneCriterion(unittest.TestCase):
    """v0.5: an accepted spec with open questions, TBDs or an AC with no verify: line fails."""

    def assert_fails(self, case, rule):
        result = run(fixture(case))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(rule, [p["rule"] for p in problems(result.stdout)])

    def test_open_question_fails(self):
        self.assert_fails("accepted-open-question", "no-open-questions")

    def test_tbd_fails(self):
        self.assert_fails("accepted-tbd", "no-tbd")

    def test_ac_without_verify_fails(self):
        self.assert_fails("accepted-no-verify", "ac.verify")

    def test_draft_example_cannot_be_accepted_yet(self):
        # Refine's gate: the draft has TBDs and an AC with only a TBD: line.
        result = run("--as", "accepted", example("draft"))
        self.assertEqual(result.returncode, 1, result.stdout)
        rules = {p["rule"] for p in problems(result.stdout)}
        self.assertEqual(rules, {"no-tbd", "ac.verify"})
        self.assertNotIn("frontmatter.accepted", rules)


class UpdateDoneCriterion(unittest.TestCase):
    """v0.6: a discovery made during implementation is synced into the spec, and it still passes.

    examples/updated/ is examples/accepted/ after an update that adds a
    discovered edge case and a decision and trims one passage of prose. None of
    those needs re-acceptance, so everything gated stays exactly as accepted.
    """

    @classmethod
    def setUpClass(cls):
        cls.m = load_module()
        cls.before = cls.m.Spec(NAME, read(example("accepted")))
        cls.after = cls.m.Spec(NAME, read(os.path.join(EXAMPLES, "updated", NAME)))

    def acs(self, spec):
        return {n: [it.line.text] + [c.text for c in it.children] for n, it in spec.behavior()[1]}

    def edge_rows(self, spec):
        return [ln.text for table in spec.behavior()[2] for ln in table[2:]]

    def lists(self, spec):
        found = {}
        for title in (self.m.GOAL, self.m.BOUNDARIES):
            for label, (_, entries) in self.m.labelled(spec, title)[1].items():
                found[label] = [[it.line.text] + [c.text for c in it.children] for it in entries]
        return found

    def test_still_accepted_and_passes(self):
        status, found = self.m.check_spec(self.after)
        self.assertEqual(status, "accepted")
        self.assertEqual(found, [])

    def test_frontmatter(self):
        b, a = self.before.fields, self.after.fields
        self.assertGreater(a["updated"], b["updated"])
        for key in ("id", "title", "status", "created", "accepted_by", "accepted_on"):
            self.assertEqual(a[key], b[key], key)

    def test_six_headings_and_no_changelog(self):
        self.assertEqual([s.title for s in self.after.sections], list(self.m.SPEC_SECTIONS))

    def test_acs_unchanged(self):
        self.assertEqual(self.acs(self.after), self.acs(self.before))

    def test_guardrail_lists_unchanged(self):
        b, a = self.lists(self.before), self.lists(self.after)
        for label in self.m.LIST_LABELS:
            self.assertEqual(a[label], b[label], label)

    def test_discovered_edge_case_added_under_existing_ac(self):
        b, a = self.edge_rows(self.before), self.edge_rows(self.after)
        self.assertTrue(set(b) <= set(a), "existing edge-case rows changed")
        added = [r for r in a if r not in b]
        self.assertEqual(len(added), 1, added)
        new = added[0]
        self.assertTrue(self.m.table_cells(new)[0].startswith("Empty:"), new)
        self.assertIn(self.m.table_cells(new)[-1], ["AC-%d" % n for n in self.acs(self.before)])

    def test_decision_added_with_next_id(self):
        b = self.lists(self.before)["Decision Log"]
        a = self.lists(self.after)["Decision Log"]
        self.assertEqual(a[:len(b)], b, "existing decisions changed")
        self.assertEqual(len(a), len(b) + 1)
        self.assertTrue(a[-1][0].startswith("- **D-%d:**" % (len(b) + 1)), a[-1][0])

    def test_prose_trimmed_to_links(self):
        before = read(example("accepted"))
        after = read(os.path.join(EXAMPLES, "updated", NAME))
        trimmed = "- stdout: `Todo[]` as JSON"
        self.assertIn(trimmed, before)
        self.assertNotIn(trimmed, after)
        interfaces = self.after.section("Interfaces & Data Contracts")
        text = "\n".join(ln.text for ln in interfaces.lines)
        self.assertIn("`src/commands/export.ts`", text)
        self.assertIn("`test/commands/export.test.ts`", text)
        self.assertLess(self.m.count_words(interfaces),
                        self.m.count_words(self.before.section("Interfaces & Data Contracts")))


class Fixtures(unittest.TestCase):
    def test_every_fixture_has_an_expectation(self):
        cases = sorted(os.listdir(FIXTURES))
        self.assertEqual(cases, sorted(FIXTURE_EXPECTATIONS))

    def test_fixtures(self):
        for case, (code, expected) in sorted(FIXTURE_EXPECTATIONS.items()):
            with self.subTest(case=case):
                result = run(fixture(case))
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                found = {(p["sev"], p["rule"]) for p in problems(result.stdout)}
                self.assertEqual(found, expected, result.stdout)

    def test_every_output_line_is_a_problem_or_ok(self):
        for case in FIXTURE_EXPECTATIONS:
            with self.subTest(case=case):
                path = fixture(case)
                for line in run(path).stdout.splitlines():
                    self.assertTrue(PROBLEM_RE.match(line) or re.match(r"^.+: ok \(", line), line)
                    self.assertTrue(line.startswith(path), line)


class ExitCodes(unittest.TestCase):
    def test_no_arguments_is_a_usage_error(self):
        result = run()
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)

    def test_unknown_option_is_a_usage_error(self):
        self.assertEqual(run("--strict", example("idea")).returncode, 2)

    def test_bad_as_status_is_a_usage_error(self):
        self.assertEqual(run("--as", "done", example("idea")).returncode, 2)

    def test_missing_file_is_a_usage_error(self):
        self.assertEqual(run(os.path.join(FIXTURES, "nope.md")).returncode, 2)

    def test_rule_failure_and_pass_together_exit_1(self):
        self.assertEqual(run(example("accepted"), fixture("accepted-tbd")).returncode, 1)

    def test_parse_error_wins_over_rule_failure(self):
        self.assertEqual(run(fixture("accepted-tbd"), fixture("bad-frontmatter-nested")).returncode, 2)

    def test_warnings_never_change_the_exit_code(self):
        result = run(fixture("draft-over-budget"))
        self.assertEqual(result.returncode, 0)
        self.assertIn("warning [budget]", result.stdout)

    def test_help_and_rules_exit_0(self):
        self.assertEqual(run("--help").returncode, 0)
        result = run("--rules")
        self.assertEqual(result.returncode, 0)
        self.assertIn("no-open-questions", result.stdout)


class FrontmatterParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def parse(self, *lines):
        return self.m.parse_frontmatter(["---"] + list(lines) + ["---"])[0]

    def test_plain_quoted_and_comments(self):
        fields = self.parse(
            "id: a-b            # equals the file name",
            'title: "Export: JSON"',
            "status: 'it''s'",
            "accepted_by:   # required when accepted",
            "accepted_on:",
        )
        self.assertEqual(fields, {"id": "a-b", "title": "Export: JSON", "status": "it's",
                                  "accepted_by": "", "accepted_on": ""})

    def test_rejects_malformed(self):
        bad = [
            ("id: a", "id: b"),            # duplicate key
            ("  id: a",),                  # indented
            ("id:a",),                     # no space after the colon
            ("tags: [a, b]",),             # flow list
            ("tags:", "- a"),              # block list
            ("title: Export: JSON",),      # unquoted ': '
            ('title: "open',),             # unterminated quote
            ("title: |",),                 # block scalar
            ("just text",),                # not key: value
        ]
        for lines in bad:
            with self.subTest(lines=lines):
                with self.assertRaises(self.m.ParseError):
                    self.parse(*lines)

    def test_requires_opening_and_closing_lines(self):
        with self.assertRaises(self.m.ParseError):
            self.m.parse_frontmatter(["id: a", "---"])
        with self.assertRaises(self.m.ParseError):
            self.m.parse_frontmatter(["---", "id: a"])

    def test_unclosed_code_fence_is_a_parse_error(self):
        text = read(example("idea")) + "\n```\nnever closed\n"
        with self.assertRaises(self.m.ParseError):
            self.m.Spec(NAME, text)


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def rules_for(self, text, as_status=None):
        _, found = self.m.check_spec(self.m.Spec(NAME, text), as_status)
        return {(p.severity, p.rule) for p in found}

    def test_every_status_rule_is_implemented(self):
        for status, rule_ids in self.m.STATUS_RULES.items():
            for rule_id in rule_ids:
                self.assertIn(rule_id, self.m.RULES, status)
                self.assertIn(rule_id, self.m.RULE_TEXT, status)

    def test_tbd_and_question_marks_inside_code_are_ignored(self):
        text = read(example("accepted")).replace(
            "- CLI: `todo export`, no arguments or flags.",
            "- CLI: `todo export`, no arguments or flags; `TBD:` and `?` in code are fine.")
        self.assertEqual(self.rules_for(text), set())

    def test_open_questions_heading_fails_accepted(self):
        text = read(example("accepted")) + "\n## Open Questions\n\n- None.\n"
        self.assertEqual(self.rules_for(text), {("error", "spec.sections"), ("error", "no-open-questions")})

    def test_sections_out_of_order(self):
        text = read(example("draft"))
        env = text.index("## Environment & Commands")
        interfaces = text.index("## Interfaces & Data Contracts")
        behavior = text.index("## Behavior & Edge Cases")
        swapped = text[:env] + text[interfaces:behavior] + text[env:interfaces] + text[behavior:]
        self.assertEqual(self.rules_for(swapped), {("error", "spec.sections")})

    def test_duplicate_ac_id(self):
        text = read(example("draft")).replace("- **AC-2:**", "- **AC-1:**")
        self.assertEqual(self.rules_for(text), {("error", "ac.format")})

    def test_gate_missing_and_out_of_order(self):
        text = read(example("accepted"))
        ac2 = '- AC-2: `npm test -- test/commands/export.test.ts -t "AC-2:"`\n'
        missing = text.replace(ac2, "")
        self.assertEqual(self.rules_for(missing), {("error", "gate.matches-acs")})
        swapped = missing.replace("- AC-3:", ac2 + "- AC-3:", 1).replace("- AC-1:", "- AC-0:", 1)
        found = self.rules_for(swapped)
        self.assertEqual(found, {("error", "gate.matches-acs")})

    def test_gate_tbd_must_stay_tbd_in_a_draft(self):
        text = read(example("draft")).replace(
            "- AC-6: TBD: the repo has no test harness", "- AC-6: `npm test` the repo has no test harness")
        self.assertEqual(self.rules_for(text), {("error", "gate.matches-acs")})

    def test_not_applicable_line_covers_a_category(self):
        text = read(example("accepted"))
        row = next(l for l in text.splitlines() if l.startswith("| State conflict:"))
        text = text.replace(row + "\n", "").replace(
            "\n## Boundaries", "\nNot applicable: state conflicts (the export only reads the store).\n\n## Boundaries", 1)
        self.assertEqual(self.rules_for(text), set())

    def test_example_arrow_inside_code_doesnt_count(self):
        text = read(example("accepted")).replace(
            "  example: `todo export` with an empty store → stdout `[]` and a newline, exit 0",
            "  example: `a -> b`")
        self.assertEqual(self.rules_for(text), {("error", "ac.example")})

    def test_draft_contracts_may_be_tbd(self):
        text = read(example("draft"))
        start = text.index("## Interfaces & Data Contracts")
        end = text.index("## Behavior & Edge Cases")
        text = text[:start] + "## Interfaces & Data Contracts\n\nTBD.\n\n" + text[end:]
        self.assertEqual(self.rules_for(text), set())

    def test_fenced_contract_counts_as_code(self):
        text = read(example("accepted")).replace(
            "- CLI: `todo export`, no arguments or flags.",
            "- CLI usage:\n\n  ```\n  todo export\n  ```")
        self.assertEqual(self.rules_for(text), set())

    def test_draft_ac_without_verify_or_tbd(self):
        text = read(example("draft")).replace(
            "  TBD: the repo has no test harness for concurrent processes; how should this be checked?\n", "", 1)
        self.assertEqual(self.rules_for(text), {("error", "ac.verify-or-tbd")})


if __name__ == "__main__":
    unittest.main()


class Section(unittest.TestCase):
    """v0.7: --section prints one section, so agents can load only what they need."""

    def test_prints_one_section(self):
        result = run("--section", "Verification Gate", example("accepted"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("## Verification Gate\n\nPer acceptance criterion:\n"))
        self.assertTrue(result.stdout.endswith("- `npm test`\n"))
        self.assertNotIn("## Boundaries", result.stdout)

    def test_stops_at_the_next_section(self):
        result = run("--section", "Goal & Non-Goals", example("accepted"))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("## Environment", result.stdout)
        self.assertTrue(result.stdout.rstrip().endswith("(`src/store.ts`)."))

    def test_works_on_an_idea(self):
        self.assertEqual(run("--section", "Open Questions", example("idea")).returncode, 0)

    def test_missing_section_is_a_usage_error(self):
        result = run("--section", "Nope", example("accepted"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("Verification Gate", result.stderr)

    def test_one_file_only_and_no_other_options(self):
        self.assertEqual(run("--section", "Goal & Non-Goals", example("accepted"), example("draft")).returncode, 2)
        self.assertEqual(run("--section", "Goal & Non-Goals", "--as", "accepted", example("draft")).returncode, 2)


TODO_REPO = {
    "package.json": '{"scripts": {"build": "tsc -p tsconfig.json", "lint": "eslint .", '
                    '"typecheck": "tsc --noEmit", "test": "vitest run"}}\n',
    "src/types.ts": "export interface Todo { id: number; text: string; done: boolean }\n",
    "src/store.ts": "export function loadTodos(): Todo[] { return []; }\n",
    "src/cli.ts": "// registers commands\n",
    "src/commands/list.ts": "export function listTodos() {}\n",
    "test/commands/list.test.ts": "// list tests\n",
    ".github/workflows/ci.yml": "steps: []\n",
}


class Repo(unittest.TestCase):
    """v0.7: --repo checks links, commands and staleness against the target repo, as warnings."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        for path, text in TODO_REPO.items():
            self.write(path, text)
        self.spec = os.path.join(self.root, "specs", NAME)
        self.write(os.path.join("specs", NAME), read(example("accepted")))

    def write(self, path, text):
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)

    def check(self, spec=None):
        result = run("--repo", self.root, spec or self.spec)
        return result, {(p["sev"], p["rule"]) for p in problems(result.stdout)}

    def git(self, *args):
        subprocess.run(["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@example.com"] + list(args),
                       check=True, capture_output=True)

    def test_matching_repo_passes_clean(self):
        result, found = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(found, set(), result.stdout)

    def test_missing_path_and_symbol(self):
        os.remove(os.path.join(self.root, "src/cli.ts"))
        self.write("src/store.ts", "export function readAll() {}\n")
        result, found = self.check()
        self.assertEqual(result.returncode, 0, "repo rules are warnings")
        self.assertEqual(found, {("warning", "repo.paths")})
        self.assertIn("`src/cli.ts` doesn't exist", result.stdout)
        self.assertIn("doesn't contain `loadTodos`", result.stdout)

    def test_missing_script(self):
        self.write("package.json", '{"scripts": {"lint": "eslint .", "test": "vitest run", "build": "tsc"}}\n')
        result, found = self.check()
        self.assertEqual(found, {("warning", "repo.commands")})
        self.assertIn("no script 'typecheck' in package.json", result.stdout)
        self.assertEqual(len([l for l in result.stdout.splitlines() if "typecheck" in l]), 1,
                         "each missing script is reported once")

    def test_make_and_just_targets(self):
        m = load_module()
        self.write("Makefile", "test lint: deps\n\t@true\nX := 1\n")
        self.write("justfile", "build target='x':\n  echo\nalias b := build\n")
        targets = m.repo_targets(self.root)
        self.assertEqual(targets["make"][1], {"test", "lint"})
        self.assertEqual(targets["just"][1], {"build", "b"})
        self.assertEqual(m.named_target("make test"), ("make", "test"))
        self.assertEqual(m.named_target("CI=1 pnpm typecheck"), ("script", "typecheck"))
        self.assertIsNone(m.named_target("pnpm install"))
        self.assertIsNone(m.named_target("npm ci"))
        self.assertIsNone(m.named_target("npm -w pkg run test"))

    def test_repo_rules_need_the_flag(self):
        os.remove(os.path.join(self.root, "src/cli.ts"))
        result = run(self.spec)
        self.assertEqual(result.stdout.strip(), "%s: ok (accepted)" % self.spec)

    def test_repo_must_be_a_directory(self):
        self.assertEqual(run("--repo", os.path.join(self.root, "nope"), self.spec).returncode, 2)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_stale_until_the_spec_is_synced(self):
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "accept")
        self.assertEqual(self.check()[1], set())
        self.write("src/store.ts", "export function loadTodos(): Todo[] { return [] as Todo[]; }\n")
        self.git("commit", "-qam", "build")
        result, found = self.check()
        self.assertEqual(found, {("warning", "repo.stale")}, result.stdout)
        self.assertIn("1 commit since the spec last changed touches src/store.ts", result.stdout)
        self.write(os.path.join("specs", NAME), read(example("accepted")).replace("updated: 2026-11-26", "updated: 2026-11-27"))
        self.assertEqual(self.check()[1], set(), "uncommitted spec changes mean a sync is in progress")
        self.git("commit", "-qam", "sync")
        self.assertEqual(self.check()[1], set())

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_stale_only_at_accepted(self):
        self.write(os.path.join("specs", NAME), read(example("draft")))
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "draft")
        self.write("src/store.ts", "export function loadTodos() { return []; }\n")
        self.git("commit", "-qam", "change")
        self.assertEqual(self.check()[1], set())
