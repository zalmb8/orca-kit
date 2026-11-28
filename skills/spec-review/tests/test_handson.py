"""Tests for v0.8, fixes from the first hands-on review: pass snapshots that make
every verdict reproducible, one open-blocker counting rule, risks that stay
raised for the review, reviewer overlap, malformed replies, and no git calls.

Run from the repo root:

    python3 -m unittest discover -s skills/spec-review/tests -v
"""

import glob
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
PAUSE = os.path.join(SKILL_DIR, "pause")
SUMMARY = os.path.join(SKILL_DIR, "summary")
RECORD = os.path.join(SKILL_DIR, "record")
GATE = os.path.join(SKILL_DIR, "gate")
FINDINGS = os.path.join(SKILL_DIR, "findings")
FIXTURES = os.path.join(HERE, "fixtures")
SLUG = "archive-completed-todos"
SPEC = os.path.join("specs", SLUG + ".md")
REC = os.path.join("specs", "reviews", SLUG + ".json")
PREV = os.path.join("previous", SLUG + ".md")


def snap(n):
    return os.path.join("specs", "reviews", SLUG, "pass-%d" % n, SLUG + ".md")


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


def run(script, *args, **kwargs):
    return subprocess.run([sys.executable, script] + list(args), capture_output=True, text=True, **kwargs)


def fixture(case):
    return os.path.join(FIXTURES, case)


def last(result):
    return result.stdout.rstrip("\n").split("\n")[-1].split(": ", 1)[1]


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data, indent=2))
    return path


def args_for(root):
    return (["--previous", PREV] if os.path.exists(os.path.join(root, PREV)) else []) + [SPEC]


class TempCase(unittest.TestCase):
    def copy(self, case):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        root = os.path.join(tmp, case)
        shutil.copytree(fixture(case), root)
        return root

    def record(self, root):
        return read_json(os.path.join(root, REC))

    def save(self, root, rec):
        write(os.path.join(root, REC), rec)


# ---------------------------------------------------------------------------
# Fix 1: every pass's verdict is reproducible from what is in the repo
# ---------------------------------------------------------------------------

class Snapshots(TempCase):
    def test_converge_reads_the_previous_pass_snapshot(self):
        result = run(CONVERGE, SPEC, cwd=fixture("handson-snapshots"))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(last(result), "converged at pass 2")

    def test_the_snapshot_gives_the_same_verdict_as_previous(self):
        # handson-snapshots is loop-converge-2 with its previous/ copy kept as the pass 1 snapshot.
        with_prev = run(CONVERGE, *args_for(fixture("loop-converge-2")), cwd=fixture("loop-converge-2"))
        with_snap = run(CONVERGE, SPEC, cwd=fixture("handson-snapshots"))
        self.assertEqual((with_prev.returncode, with_prev.stdout), (with_snap.returncode, with_snap.stdout))
        for script in (PAUSE,):
            a = run(script, *args_for(fixture("loop-converge-2")), cwd=fixture("loop-converge-2"))
            b = run(script, SPEC, cwd=fixture("handson-snapshots"))
            self.assertEqual((a.returncode, a.stdout), (b.returncode, b.stdout))

    def test_every_handson_loop_fixture_runs_without_previous(self):
        for case in ("handson-snapshots", "handson-sticky-risk"):
            with self.subTest(case=case):
                self.assertIn(run(PAUSE, SPEC, cwd=fixture(case)).returncode, (0, 1))
                self.assertFalse(os.path.exists(os.path.join(fixture(case), "previous")))

    def test_previous_still_overrides_the_snapshot(self):
        root = self.copy("handson-snapshots")
        with open(os.path.join(root, snap(1)), encoding="utf-8") as f:
            other = write(os.path.join(root, "other.md"), f.read() + "\nmore words " * 400)
        result = run(CONVERGE, "--previous", other, SPEC, cwd=root)
        self.assertEqual(result.returncode, 2, result.stdout)  # the record's pass 1 words don't match the override
        self.assertIn("pass 1 records 655 words, but %s has" % other, result.stdout)

    def test_without_a_snapshot_pass_two_still_needs_previous(self):
        # Existing records stay valid, and behave as before without --previous: exit 2.
        result = run(CONVERGE, SPEC, cwd=fixture("loop-converge-2"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("pass 2 needs --previous", result.stdout)
        self.assertIn("no snapshot of pass 1 at specs/reviews/%s/pass-1/%s.md" % (SLUG, SLUG), result.stdout)
        self.assertEqual(run(PAUSE, SPEC, cwd=fixture("loop-converge-2")).returncode, 2)

    def test_pass_one_still_takes_no_previous(self):
        root = self.copy("handson-snapshots")
        rec = self.record(root)
        rec["passes"] = rec["passes"][:1]
        rec["passes"][0]["words"] = 664
        self.save(root, rec)
        shutil.copy(os.path.join(root, SPEC), os.path.join(root, snap(1)))
        self.assertEqual(run(CONVERGE, SPEC, cwd=root).returncode, 3)
        self.assertEqual(run(CONVERGE, "--previous", snap(1), SPEC, cwd=root).returncode, 2)

    def test_a_spec_that_differs_from_its_pass_snapshot_is_refused(self):
        root = self.copy("handson-snapshots")
        with open(os.path.join(root, SPEC), encoding="utf-8") as f:
            text = f.read()
        write(os.path.join(root, SPEC), text.replace("completed", "finished", 1))  # same word count
        result = run(CONVERGE, SPEC, cwd=root)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("differs from specs/reviews/%s/pass-2/%s.md" % (SLUG, SLUG), result.stdout)

    def test_the_last_pass_can_be_rechecked_after_the_spec_moved_on(self):
        root = self.copy("handson-snapshots")
        with open(os.path.join(root, SPEC), "a", encoding="utf-8") as f:
            f.write("\nAn edit after the review.\n")
        self.assertEqual(run(CONVERGE, SPEC, cwd=root).returncode, 2)
        result = run(CONVERGE, "--record", REC, snap(2), cwd=root)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(last(result), "converged at pass 2")

    def test_a_snapshot_passes_the_gates_like_its_spec(self):
        for n in (1, 2):
            result = run(GATE, snap(n), cwd=fixture("handson-snapshots"))
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_check_specs_glob_does_not_reach_snapshots(self):
        found = sorted(os.path.relpath(p, fixture("handson-snapshots")) for p in glob.glob(os.path.join(fixture("handson-snapshots"), "specs", "*.md")))
        self.assertEqual(found, [SPEC])

    def test_bloat_text_names_the_snapshot_to_put_back(self):
        root = self.copy("pause-bloat")
        os.makedirs(os.path.dirname(os.path.join(root, snap(1))))
        shutil.move(os.path.join(root, PREV), os.path.join(root, snap(1)))
        result = run(PAUSE, SPEC, cwd=root)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("put back the copy saved before it (%s)" % os.path.join("specs", "reviews", SLUG, "pass-1", SLUG + ".md"), result.stdout)


# ---------------------------------------------------------------------------
# Fix 2: one counting rule for the record, converge, pause and summary
# ---------------------------------------------------------------------------

class OneCount(TempCase):
    def test_the_hands_on_count_is_rejected(self):
        result = run(RECORD, REC, cwd=fixture("handson-carried-count"))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("error [record.passes] passes[2].open_blockers: open_blockers is 1, but pass 2 has 0 open blockers "
                      "(1 blocker, less 1 slicer.oversized the user answered keep to in an earlier pass)", result.stdout)
        for script in (CONVERGE, PAUSE, SUMMARY):
            with self.subTest(script=os.path.basename(script)):
                self.assertEqual(run(script, SPEC, cwd=fixture("handson-carried-count")).returncode, 2)

    def test_the_corrected_count_converges(self):
        root = self.copy("handson-carried-count")
        rec = self.record(root)
        rec["passes"][1]["open_blockers"] = 0
        self.save(root, rec)
        self.assertEqual(run(RECORD, REC, cwd=root).returncode, 0)
        self.assertEqual(last(run(CONVERGE, SPEC, cwd=root)), "converged at pass 2")
        out = run(SUMMARY, SPEC, cwd=root).stdout
        self.assertIn("Blockers:  no open blockers at pass 2", out)
        self.assertIn("  pass 2: 0 blockers (0 fix, 0 decision)", out)

    def test_record_converge_pause_and_summary_agree_on_every_fixture(self):
        m = load("spec_review_record", RECORD)
        status_re = re.compile(r": pass (\d) of 3: (\d+) open blockers?")
        history_re = re.compile(r"^  pass (\d): (\d+) blockers? ")
        for rec_path in sorted(glob.glob(os.path.join(FIXTURES, "*", "specs", "reviews", SLUG + ".json"))):
            root = os.path.dirname(os.path.dirname(os.path.dirname(rec_path)))
            code, _, data = m.check_file(rec_path)
            if data is None or not data.get("passes"):
                continue
            with self.subTest(case=os.path.basename(root)):
                counts = m.open_counts(data)
                self.assertEqual([p["open_blockers"] for p in data["passes"]], counts)
                c = run(CONVERGE, *args_for(root), cwd=root)
                if c.returncode != 2:
                    n, k = status_re.search(c.stdout).groups()
                    self.assertEqual(int(k), counts[int(n) - 1])
                hist = [int(mm.group(2)) for mm in map(history_re.match, run(SUMMARY, SPEC, cwd=root).stdout.split("\n")) if mm]
                self.assertEqual(hist, counts)

    def test_the_scripts_share_the_function(self):
        conv = load("spec_review_converge", CONVERGE)
        for name in ("open_of", "resolutions", "blocker_key", "blockers_of"):
            self.assertIs(getattr(conv, name), getattr(conv.RECORD, name))
        for path in (SUMMARY, PAUSE):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertNotRegex(text, r"def (open_of|resolutions|blocker_key)\(")
            self.assertNotRegex(text, r'severity"\] == "blocker"\)\s*$')

    def test_a_count_of_the_wrong_type_is_rejected(self):
        root = self.copy("handson-snapshots")
        rec = self.record(root)
        rec["passes"][0]["open_blockers"] = "2"
        self.save(root, rec)
        result = run(RECORD, REC, cwd=root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("passes[1].open_blockers: open_blockers is \"2\", not a whole number", result.stdout)


# ---------------------------------------------------------------------------
# Fix 3: a risk any pass raised stays raised for the review
# ---------------------------------------------------------------------------

class StickyRisk(TempCase):
    def test_gate_keeps_the_risk_pass_one_raised(self):
        result = run(GATE, "--risk", SPEC, cwd=fixture("handson-sticky-risk"))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("warning [risk.breaking-change] Interfaces & Data Contracts: finding blast-radius-1 (blocker fix from blast-radius) "
                      "raised it in pass 1, and it stays raised for this review.", result.stdout)
        self.assertEqual(last(result), "risk high: breaking-change; sign-off needed")

    def test_the_spec_alone_is_low(self):
        # The revision fixed the finding: the text no longer names the risk, but the review still does.
        root = self.copy("handson-sticky-risk")
        os.remove(os.path.join(root, REC))
        self.assertEqual(last(run(GATE, "--risk", SPEC, cwd=root)), "risk low")

    def test_pause_asks_the_sign_off_naming_the_pass(self):
        result = run(PAUSE, SPEC, cwd=fixture("handson-sticky-risk"))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Do you sign off on exactly these risks: breaking-change?", result.stdout)
        self.assertIn("raised it in pass 1", result.stdout)

    def test_summary_says_which_pass_raised_it(self):
        out = run(SUMMARY, SPEC, cwd=fixture("handson-sticky-risk")).stdout
        self.assertIn("Risk:      high (breaking-change); sign-off needed, not given", out)
        self.assertIn("breaking-change: raised in pass 1 by blast-radius-1 (blast-radius.unmentioned-contract)", out)

    def test_a_record_that_dropped_the_risk_is_rejected(self):
        # The hands-on record's shape: pass 1 raised breaking-change, pass 2 recorded the tier as low.
        root = self.copy("handson-sticky-risk")
        rec = self.record(root)
        rec["risk"] = {"tier": "low", "risks": [], "reasons": []}
        self.save(root, rec)
        result = run(RECORD, REC, cwd=root)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("passes[1].findings: a finding in pass 1 names risk breaking-change, which risk.risks doesn't list", result.stdout)
        self.assertEqual(run(GATE, "--risk", SPEC, cwd=root).returncode, 2)

    def test_a_sign_off_covers_it(self):
        root = self.copy("handson-sticky-risk")
        rec = self.record(root)
        rec["sign_off"] = {"signed_off_by": "Sam Rivera", "signed_off_on": "2026-11-27", "risks": ["breaking-change"]}
        self.save(root, rec)
        self.assertEqual(run(GATE, "--risk", SPEC, cwd=root).returncode, 0)
        self.assertEqual(last(run(PAUSE, SPEC, cwd=root)), "no pause: done at pass 2; render the summary")

    def test_a_fresh_review_starts_over(self):
        root = self.copy("handson-sticky-risk")
        rec = self.record(root)
        rec["passes"] = rec["passes"][1:]
        rec["risk"] = {"tier": "low", "risks": [], "reasons": []}
        self.save(root, rec)
        shutil.rmtree(os.path.join(root, "specs", "reviews", SLUG))
        self.assertEqual(run(RECORD, REC, cwd=root).returncode, 0)
        self.assertEqual(last(run(GATE, "--risk", SPEC, cwd=root)), "risk low")
        self.assertEqual(last(run(PAUSE, SPEC, cwd=root)), "no pause: done at pass 1; render the summary")

    def test_a_finding_given_and_recorded_is_listed_once(self):
        root = self.copy("handson-sticky-risk")
        rec = self.record(root)
        findings = write(os.path.join(root, "merged.json"), rec["passes"][0]["findings"])
        result = run(GATE, "--risk", "--findings", findings, SPEC, cwd=root)
        reasons = [l for l in result.stdout.split("\n") if "[risk.breaking-change]" in l]
        self.assertEqual(len(reasons), 1, result.stdout)
        self.assertIn("finding blast-radius-1 (blocker fix from blast-radius) raises it", reasons[0])

    def test_an_invalid_record_stops_even_a_low_spec(self):
        root = self.copy("handson-snapshots")
        write(os.path.join(root, REC), "{")
        self.assertEqual(run(GATE, "--risk", SPEC, cwd=root).returncode, 2)


# ---------------------------------------------------------------------------
# Fix 4: overlapping reviewers are reported, never merged
# ---------------------------------------------------------------------------

class Overlap(unittest.TestCase):
    FILES = [os.path.join(fixture("handson-overlap"), n) for n in ("architecture.json", "blast-radius.json")]

    def test_same_spot_same_path_is_noted_and_both_are_kept(self):
        result = run(FINDINGS, "--merge", *self.FILES)
        self.assertEqual(result.returncode, 0, result.stderr)
        ids = [f["id"] for f in json.loads(result.stdout)]
        self.assertEqual(ids, ["architecture-1", "architecture-2", "blast-radius-1", "blast-radius-2"])
        notes = [l for l in result.stderr.split("\n") if "[merge.overlap]" in l]
        self.assertEqual(len(notes), 1, result.stderr)
        self.assertIn("finding #1 (blast-radius-1, blast-radius.incompatible-change): same spot as architecture-1 "
                      "(architecture.codebase-drift)", notes[0])
        self.assertIn("both cite skills/spec-review/tests/test_loop.py", notes[0])
        self.assertEqual(result.stderr.rstrip("\n").split("\n")[-1],
                         "merged: 4 findings from 2 files: 3 blocker (0 decision), 1 nit; 0 duplicates dropped, 0 rejected")

    def test_the_same_reviewer_or_another_spot_is_not_an_overlap(self):
        m = load("spec_review_findings", FINDINGS)
        a, b = (read_json(p) for p in self.FILES)
        self.assertEqual(len(m.overlaps(a + b)), 1)
        moved = dict(b[0], location=dict(b[0]["location"], line=48))
        self.assertEqual(m.overlaps(a + [moved]), [])
        same_reviewer = dict(a[0], id="architecture-9", rule="architecture.existing-mismatch")
        self.assertEqual(m.overlaps([a[0], same_reviewer]), [])
        no_path = dict(b[0], evidence="the oscillation line changes")
        self.assertEqual(m.overlaps(a + [no_path]), [])

    def test_rules_list_the_overlap_note(self):
        self.assertIn("merge.overlap", run(FINDINGS, "--rules").stdout)

    def test_rubrics_give_consumers_to_blast_radius(self):
        with open(os.path.join(PLUGIN_ROOT, "agents", "spec-review-architecture.md"), encoding="utf-8") as f:
            arch = f.read()
        with open(os.path.join(PLUGIN_ROOT, "agents", "spec-review-blast-radius.md"), encoding="utf-8") as f:
            blast = f.read()
        self.assertIn("blast-radius owns it", arch)
        self.assertIn("consumers of what the spec changes, wherever they are, including tests and fixtures", arch)
        self.assertIn("A test or fixture that asserts the old behaviour is a consumer too, and yours", blast)
        self.assertIn("Architecture owns whether the change itself fits the code's design", blast)


# ---------------------------------------------------------------------------
# Fixes 5 and 6: malformed replies, and no git or GitHub calls
# ---------------------------------------------------------------------------

GIT_RE = re.compile(r"(?i)\bcommit\w*\b|\bgit (?:push|commit|checkout|merge|branch)\b|\bpull requests?\b|\bgh pr\b|\bbranch(?:es)?\b"
                    r"|\bpush(?:es|ed)?\b(?! the spec)|(?-i:\bPRs?\b)")
NEGATION_RE = re.compile(r"(?i)\b(never|no|not|doesn't|don't|isn't|won't|nor)\b")


class Docs(unittest.TestCase):
    def read(self, *parts):
        with open(os.path.join(*parts), encoding="utf-8") as f:
            return f.read()

    def test_malformed_reply_rule(self):
        for name in ("SKILL.md", "reviewers.md"):
            with self.subTest(doc=name):
                text = self.read(SKILL_DIR, name)
                self.assertRegex(text, r"(?i)re-run that one reviewer \*\*once\*\*")
                self.assertRegex(text, r"(?i)never re-run a reviewer a second time in the same pass")
                self.assertIn("never combine the two", text.lower())

    def test_no_doc_tells_claude_to_use_git(self):
        docs = [os.path.join(SKILL_DIR, n) for n in ("SKILL.md", "loop.md", "pauses.md", "risk.md", "reviewers.md")]
        docs += sorted(glob.glob(os.path.join(PLUGIN_ROOT, "agents", "spec-review-*.md")))
        for path in docs:
            for no, line in enumerate(self.read(path).split("\n"), 1):
                if GIT_RE.search(line):
                    with self.subTest(doc=os.path.basename(path), line=no):
                        self.assertRegex(line, NEGATION_RE, "%s:%d mentions a git action without ruling it out: %s" % (path, no, line))

    def test_graduation_hands_the_proposal_up_as_text(self):
        skill = self.read(SKILL_DIR, "SKILL.md")
        self.assertIn("hand the approved proposal up **as text**", skill)
        self.assertIn("It runs no git or GitHub commands", skill)
        self.assertNotIn("committed with", skill + self.read(SKILL_DIR, "risk.md"))

    def test_roadmap_v08_is_done(self):
        roadmap = self.read(PLUGIN_ROOT, "docs", "spec-review", "ROADMAP.md")
        part = roadmap[roadmap.index("### v0.8"):roadmap.index("## Decision log")]
        self.assertIn("### v0.8: Fixes from the first hands-on review ✅", part)
        self.assertNotIn("- [ ]", part)
        self.assertNotIn("It is committed with the spec.", roadmap)

    def test_plugin_version(self):
        self.assertEqual(json.loads(self.read(PLUGIN_ROOT, ".claude-plugin", "plugin.json"))["version"], "0.16.0")


class NoWrites(TempCase):
    def test_running_the_scripts_on_the_handson_fixtures_changes_no_file(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        cases = [d for d in os.listdir(FIXTURES) if d.startswith("handson-") and os.path.isdir(os.path.join(FIXTURES, d, "specs"))]
        for case in cases:
            shutil.copytree(fixture(case), os.path.join(tmp, case))

        def snapshot():
            out = {}
            for d, _, files in os.walk(tmp):
                for name in files:
                    with open(os.path.join(d, name), "rb") as fh:
                        out[os.path.join(d, name)] = fh.read()
            return out

        before = snapshot()
        for case in cases:
            root = os.path.join(tmp, case)
            for script in (CONVERGE, PAUSE, SUMMARY):
                run(script, SPEC, cwd=root)
            run(RECORD, REC, cwd=root)
            run(GATE, "--risk", SPEC, cwd=root)
        self.assertEqual(snapshot(), before)


if __name__ == "__main__":
    unittest.main()
