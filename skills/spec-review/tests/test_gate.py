"""Tests for skills/spec-review/gate.

Run from the repo root:

    python3 -m unittest discover -s skills/spec-review/tests -v
"""

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
SKILL_DIR = os.path.dirname(HERE)
GATE = os.path.join(SKILL_DIR, "gate")
CHECK = os.path.join(SKILL_DIR, "..", "spec", "check")
FIXTURES = os.path.join(HERE, "fixtures")
NAME = "export-todos-as-json.md"

PROBLEM_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+): (?P<sev>error|warning) \[(?P<rule>[a-z0-9.-]+)\] "
                        r"(?P<section>[^:]+): .+\. Fix: .+\.$")
RESULT_RE = re.compile(r"^(?P<file>.+?): gates (?:ok: (?P<ok>[a-z, ]+)|failed: (?P<failed>[a-z0-9(), ]+?)(?:; passed: (?P<passed>[a-z, ]+))?)$")


def run(*args, **kwargs):
    return subprocess.run([sys.executable, GATE] + list(args), capture_output=True, text=True, **kwargs)


def fixture(case):
    return os.path.join(FIXTURES, case, NAME)


def gate_fixture(case):
    return run("--repo", os.path.join(FIXTURES, case), fixture(case))


def problems(stdout):
    return [m.groupdict() for m in map(PROBLEM_RE.match, stdout.splitlines()) if m]


def load_module():
    loader = importlib.machinery.SourceFileLoader("spec_review_gate", GATE)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("spec_review_gate", loader))
    loader.exec_module(module)
    return module


# fixture directory -> (exit code, {(severity, rule), ...} it must report, and nothing else)
FIXTURE_EXPECTATIONS = {
    # Passing specs: one using every setting, blocks and a $schema; one with no config at all.
    "gate-pass": (0, set()),
    "gate-pass-no-config": (0, set()),
    # One failing fixture per gate (the v0.2 done criterion), and the edges of each.
    "gate-check": (1, {("error", "check.no-tbd")}),
    "gate-check-parse": (2, {("error", "check.parse")}),
    "gate-secrets": (1, {("error", "secrets.aws-key"), ("error", "pii.email"), ("error", "pii.phone")}),
    "gate-secrets-custom": (1, {("error", "secrets.custom")}),
    "gate-blocks-json": (1, {("error", "blocks.json")}),
    "gate-blocks-yaml": (1, {("error", "blocks.yaml")}),
    "gate-blocks-openapi": (1, {("error", "blocks.openapi")}),
    "gate-blocks-schema": (1, {("error", "blocks.schema")}),
    "gate-blocks-unsupported": (0, {("warning", "blocks.yaml-unsupported")}),
    "gate-trace": (1, {("error", "trace.ticket")}),
    "gate-length": (1, {("error", "length.words")}),
    # Settings files the gate refuses.
    "gate-config-unknown": (2, {("error", "config")}),
    "gate-config-bad-regex": (2, {("error", "config")}),
}


class Fixtures(unittest.TestCase):
    def test_every_gate_fixture_has_an_expectation(self):
        found = sorted(d for d in os.listdir(FIXTURES) if d.startswith("gate-"))
        self.assertEqual(found, sorted(FIXTURE_EXPECTATIONS))

    def test_fixtures(self):
        for case, (code, expected) in sorted(FIXTURE_EXPECTATIONS.items()):
            with self.subTest(case=case):
                result = gate_fixture(case)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                found = {(p["sev"], p["rule"]) for p in problems(result.stdout)}
                self.assertEqual(found, expected, result.stdout)

    def test_every_gate_has_a_failing_fixture(self):
        m = load_module()
        failing = set()
        for case, (code, expected) in FIXTURE_EXPECTATIONS.items():
            if code == 1:
                failing |= {rule.split(".")[0].replace("pii", "secrets") for sev, rule in expected if sev == "error"}
        self.assertEqual(failing, set(m.GATES))

    def test_every_output_line_is_a_problem_or_result(self):
        for case in sorted(FIXTURE_EXPECTATIONS):
            with self.subTest(case=case):
                lines = gate_fixture(case).stdout.splitlines()
                self.assertTrue(lines)
                for line in lines:
                    self.assertTrue(PROBLEM_RE.match(line) or RESULT_RE.match(line), line)

    def test_result_line_names_every_gate(self):
        m = load_module()
        for case, (code, _) in sorted(FIXTURE_EXPECTATIONS.items()):
            if case.startswith("gate-config"):
                continue
            with self.subTest(case=case):
                last = RESULT_RE.match(gate_fixture(case).stdout.splitlines()[-1])
                self.assertTrue(last)
                if code == 0:
                    self.assertEqual(last.group("ok"), ", ".join(m.GATES))
                else:
                    failed = re.findall(r"([a-z]+) \(\d+\)", last.group("failed"))
                    passed = (last.group("passed") or "").split(", ") if last.group("passed") else []
                    self.assertEqual(sorted(failed + passed), sorted(m.GATES))


class Determinism(unittest.TestCase):
    """v0.2 done criterion: the same spec always gets the same result."""

    def test_same_input_same_output(self):
        for case in sorted(FIXTURE_EXPECTATIONS):
            with self.subTest(case=case):
                runs = [gate_fixture(case) for _ in range(3)]
                self.assertEqual(len({(r.returncode, r.stdout, r.stderr) for r in runs}), 1)

    def test_problems_are_sorted_by_line(self):
        result = gate_fixture("gate-secrets")
        lines = [int(p["line"]) for p in problems(result.stdout)]
        self.assertEqual(lines, sorted(lines))

    def test_output_does_not_depend_on_the_environment(self):
        env = dict(os.environ, TZ="Pacific/Kiritimati", LANG="C", PYTHONHASHSEED="12345")
        a = gate_fixture("gate-secrets")
        b = run("--repo", os.path.join(FIXTURES, "gate-secrets"), fixture("gate-secrets"), env=env)
        self.assertEqual((a.returncode, a.stdout), (b.returncode, b.stdout))


class CheckGate(unittest.TestCase):
    def test_checker_is_found_next_to_the_gate(self):
        m = load_module()
        self.assertTrue(os.path.isfile(os.path.normpath(m.CHECK)))
        self.assertEqual(os.path.realpath(m.CHECK), os.path.realpath(CHECK))

    def test_checker_problems_pass_through_under_its_rule_names(self):
        path = fixture("gate-check")
        checked = subprocess.run([sys.executable, CHECK, "--as", "accepted", path], capture_output=True, text=True)
        expected = [line.replace(" [", " [check.", 1) for line in checked.stdout.splitlines() if PROBLEM_RE.match(line)]
        gated = [line for line in gate_fixture("gate-check").stdout.splitlines() if "[check." in line]
        self.assertTrue(expected)
        self.assertEqual(gated, expected)

    def test_draft_status_is_checked_as_accepted(self):
        with open(fixture("gate-pass"), encoding="utf-8") as f:
            self.assertIn("\nstatus: draft\n", f.read())
        self.assertEqual(gate_fixture("gate-pass").returncode, 0)


class Config(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def load(self, text):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        if text is not None:
            os.makedirs(os.path.join(tmp, ".orca-kit"))
            with open(os.path.join(tmp, ".orca-kit", "spec-review.yml"), "w", encoding="utf-8") as f:
                f.write(text)
        return self.m.load_config(tmp)[0]

    def test_defaults_without_a_file(self):
        config = self.load(None)
        self.assertIsNone(config["ticket_re"])
        self.assertEqual(config["max_words"], 2000)
        self.assertEqual(config["secret_res"], [])

    def test_empty_file_is_defaults(self):
        self.assertEqual(self.load("# nothing set\n")["max_words"], 2000)

    def test_every_setting(self):
        config = self.load("ticket_pattern: 'ABC-[0-9]+'\nmax_words: 900\nsecret_patterns:\n  - 'k_[a-z]{8}'\n  - \"x\\\\d+\"\n")
        self.assertEqual(config["ticket_re"].pattern, "ABC-[0-9]+")
        self.assertEqual(config["max_words"], 900)
        self.assertEqual([r.pattern for r in config["secret_res"]], ["k_[a-z]{8}", "x\\d+"])

    def test_rejected(self):
        for text in ("max_lines: 3\n", "max_words: 0\n", "max_words: '900'\n", "max_words: true\n",
                     "ticket_pattern: 12\n", "ticket_pattern: '[a-'\n", "secret_patterns: 'abc'\n",
                     "secret_patterns:\n  - 3\n", "- a\n", "max_words: 1\nmax_words: 2\n", "a: &x 1\n"):
            with self.subTest(text=text):
                with self.assertRaises(self.m.ConfigError):
                    self.load(text)

    def test_documented_examples_are_valid(self):
        with open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8") as f:
            skill = re.search(r"\.orca-kit/spec-review\.yml`.*?```yaml\n(.*?)```", f.read(), re.S).group(1)
        help_text = re.search(r"spec-review\.yml:\n(.*?)The file is YAML", self.m.__doc__, re.S).group(1)
        for text in (skill, help_text):
            with self.subTest(text=text):
                config = self.load(text)
                self.assertIsNotNone(config["ticket_re"])
                self.assertEqual(config["max_words"], 2000)
                self.assertEqual(len(config["secret_res"]), 1)

    def test_found_by_walking_up_from_the_spec(self):
        result = run(fixture("gate-trace"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("[trace.ticket]", result.stdout)

    def test_config_error_names_the_settings_file(self):
        result = gate_fixture("gate-config-unknown")
        self.assertIn(os.path.join(".orca-kit", "spec-review.yml") + ":1: error [config] settings: unknown setting max_lines",
                      result.stdout)


class Yaml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def test_parses_the_subset(self):
        text = "\n".join([
            "openapi: 3.1.0",
            "info:",
            "  title: Todos  # a comment",
            "  version: \"1.0\"",
            "paths:",
            "  /todos/{id}:",
            "    get:",
            "      parameters:",
            "        - name: id",
            "          in: path",
            "          required: true",
            "      responses:",
            "        '200':",
            "          description: |",
            "            A todo.",
            "            Second line.",
            "        \"404\": {description: Not found}",
            "tags: [a, 'b c', 1]",
            "list:",
            "- x",
            "- - nested",
            "empty:",
            "n: 1.5",
            "off: false",
            "none: ~",
        ])
        self.assertEqual(self.m.parse_yaml(text), {
            "openapi": "3.1.0",
            "info": {"title": "Todos", "version": "1.0"},
            "paths": {"/todos/{id}": {"get": {
                "parameters": [{"name": "id", "in": "path", "required": True}],
                "responses": {"200": {"description": "A todo.\nSecond line.\n"}, "404": {"description": "Not found"}},
            }}},
            "tags": ["a", "b c", 1],
            "list": ["x", ["nested"]],
            "empty": None,
            "n": 1.5,
            "off": False,
            "none": None,
        })

    def test_errors(self):
        for text, line in (("a: 1\na: 2", 2), ("a: b: c", 1), ("a:\n\tb: 1", 2), ("  a: 1\nb: 2", 2),
                           ("- a\nb: 1", 2), ("a: \"\\q\"", 1), ("a: [1, }", 1)):
            with self.subTest(text=text):
                with self.assertRaises(self.m.YamlError) as cm:
                    self.m.parse_yaml(text)
                self.assertNotIsInstance(cm.exception, self.m.YamlUnsupported)
                self.assertEqual(cm.exception.line, line)

    def test_unsupported_is_reported_not_guessed(self):
        for text in ("a: &x 1", "a: *x", "a: !!str 1", "<<: {a: 1}", "%YAML 1.2\n---\na: 1", "a: 1\n---\nb: 2",
                     "? a\n: 1", "a: [1,\n  2]", "a: plain\n  continued", "a:\n  plain\n  continued"):
            with self.subTest(text=text):
                with self.assertRaises(self.m.YamlUnsupported):
                    self.m.parse_yaml(text)


class Secrets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def rules(self, line):
        config = dict(self.m.DEFAULTS, secret_res=[], ticket_re=None)
        return sorted({p.rule for p in self.m.gate_secrets("x.md", self.m.Doc(line + "\n"), config, ".")})

    def test_flagged(self):
        cases = {
            "-----BEGIN RSA PRIVATE KEY-----": "secrets.private-key",
            "token ghp_" + "a1B2" * 9: "secrets.github-token",
            "xoxb-1234567890-abcdefghij": "secrets.slack-token",
            "sk_live_" + "4eC39HqLyjWDarjtT1zdp7dc": "secrets.stripe-key",
            "AIza" + "SyD-9tSrke72PouQMnMX-a7eZSW0jkFMBWY": "secrets.google-key",
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U": "secrets.jwt",
            "postgres://admin:s3cretPass@db.internal:5432/todos": "secrets.url-credentials",
            "DB_PASSWORD=hunter2hunter2": "secrets.assignment",
            "ssn 123-45-6789": "pii.ssn",
            "card 4539 1488 0343 6467": "pii.card",
            "jane.doe@acme-corp.io": "pii.email",
            "call +1 415 555 2671": "pii.phone",
        }
        for line, rule in cases.items():
            with self.subTest(line=line):
                self.assertIn(rule, self.rules(line))

    def test_not_flagged(self):
        for line in ("postgres://<user>:<password>@localhost/todos", "postgres://user:${DB_PASSWORD}@db/todos",
                     "password: <your-password>", "token: string", "api_key=${API_KEY}", "apiKey: process.env.API_KEY",
                     "dev@example.com, a@b.test", "card 4242 4242 4242 4242", "created: 2026-11-24",
                     "version 1.2.3, port 5432, id 1700000000000", "C++ 20 is fine", "use `sk-` keys from the vault"):
            with self.subTest(line=line):
                self.assertEqual(self.rules(line), [])

    def test_secret_values_are_masked_in_output(self):
        result = gate_fixture("gate-secrets")
        self.assertNotIn("AKIAZ7Q3EXAMPLEKEY42", result.stdout)
        self.assertNotIn("jane.doe@acme-corp.io", result.stdout)
        self.assertIn("(AKIA...)", result.stdout)


class Blocks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module()

    def rules(self, body, repo="."):
        config = dict(self.m.DEFAULTS, secret_res=[], ticket_re=None)
        return [(p.rule, p.line) for p in self.m.gate_blocks("x.md", self.m.Doc(body), config, repo)]

    def test_problem_line_is_inside_the_block(self):
        self.assertEqual(self.rules("## A\n\n```json\n{\n  \"a\": 1,\n}\n```\n"), [("blocks.json", 6)])

    def test_other_fences_are_ignored(self):
        self.assertEqual(self.rules("```text\n{not json\n```\n```\na: b: c\n```\n"), [])

    def test_indented_fence_in_a_list_item(self):
        self.assertEqual(self.rules("- item:\n\n  ```yaml\n  a: 1\n  b:\n    - x\n  ```\n"), [])

    def test_openapi_by_key_in_a_json_block(self):
        self.assertEqual(self.rules('```json\n{"openapi": "3.0.3", "info": {"title": "T", "version": "1"}}\n```\n'),
                         [("blocks.openapi", 1)])

    def test_swagger(self):
        self.assertEqual(self.rules('```yaml\nswagger: "2.0"\ninfo: {title: T, version: "1"}\npaths: {}\n```\n'), [])

    def test_remote_schema_is_a_warning(self):
        found = self.rules('```json\n{"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}\n```\n')
        self.assertEqual(found, [("blocks.schema-unsupported", 1)])


class Usage(unittest.TestCase):
    def test_no_files(self):
        self.assertEqual(run().returncode, 2)

    def test_unknown_option(self):
        self.assertEqual(run("--nope", fixture("gate-pass")).returncode, 2)

    def test_repo_not_a_directory(self):
        self.assertEqual(run("--repo", fixture("gate-pass"), fixture("gate-pass")).returncode, 2)

    def test_unreadable_file(self):
        result = run(os.path.join(FIXTURES, "gate-pass", "missing.md"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("error [usage] file", result.stdout)

    def test_gates_lists_every_rule(self):
        m = load_module()
        result = run("--gates")
        self.assertEqual(result.returncode, 0)
        for rule_id in m.RULE_TEXT:
            self.assertIn(rule_id, result.stdout)

    def test_worst_exit_code_across_files(self):
        result = run(fixture("gate-pass-no-config"), fixture("gate-check"), fixture("gate-check-parse"))
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
