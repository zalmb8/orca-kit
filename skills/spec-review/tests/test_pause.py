"""Tests for the v0.6 human-in-the-loop pauses: `pause`, resuming after answers
(`converge` and the record's `questions`), and the review summary (`summary`).

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
PAUSE = os.path.join(SKILL_DIR, "pause")
SUMMARY = os.path.join(SKILL_DIR, "summary")
CONVERGE = os.path.join(SKILL_DIR, "converge")
RECORD = os.path.join(SKILL_DIR, "record")
GATE = os.path.join(SKILL_DIR, "gate")
FINDINGS = os.path.join(SKILL_DIR, "findings")
FIXTURES = os.path.join(HERE, "fixtures")
SLUG = "archive-completed-todos"
SPEC = os.path.join("specs", SLUG + ".md")
REC = os.path.join("specs", "reviews", SLUG + ".json")
PREV = os.path.join("previous", SLUG + ".md")

# case: (pause exit code, last line after "<spec>: ", the trigger asked or None)
EXPECTED = {
    "pause-decision": (1, "pause at pass 1: ask the question and record the answer", "decision"),
    "pause-answered": (0, "no pause: continue to pass 2", None),
    "pause-left-open": (0, "no pause: ended at pass 1 (decision left open); render the summary", None),
    "pause-resumed": (0, "no pause: done at pass 2; render the summary", None),
    "pause-cap": (1, "pause at pass 3: ask the question and record the answer", "loop"),
    "pause-oscillation": (1, "pause at pass 2: ask the question and record the answer", "loop"),
    "pause-no-progress": (1, "pause at pass 2: ask the question and record the answer", "loop"),
    "pause-bloat": (1, "pause at pass 2: ask the question and record the answer", "loop"),
    "pause-gate": (0, "no pause: ended at pass 2 (gate: fix the failing gates through orca-kit:spec refine, "
                      "then run a fresh review); render the summary", None),
    "pause-sign-off": (1, "pause at pass 2: ask the question and record the answer", "sign-off"),
    "pause-skim-length": (1, "pause at pass 1: ask the question and record the answer", "skim"),
    "pause-skim-slicer": (1, "pause at pass 1: ask the question and record the answer", "skim"),
    "pause-keep-carried": (0, "no pause: done at pass 2; render the summary", None),
}

QUESTION_RE = re.compile(r"^Question (\d+) of (\d+) \[([a-z0-9.-]+)\]: .+$")
OPTION_RE = re.compile(r"^   (\d+)\. [A-Z].+$")
HEADER_RE = re.compile(r"^.+: pause: ask \d+ questions? \((loop|skim|decision|sign-off)\)(; then, if the review goes on: [a-z, -]+)?$")
WRITES_RE = re.compile(r"open\([^)]*['\"][wax]\+?['\"]|\.write_text\(|json\.dump\(|os\.(rename|replace|remove|unlink)\(|shutil\.")


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


def run(script, *args, **kwargs):
    return subprocess.run([sys.executable, script] + list(args), capture_output=True, text=True, **kwargs)


def fixture(case):
    return os.path.join(FIXTURES, case)


def args_for(root):
    return (["--previous", PREV] if os.path.exists(os.path.join(root, PREV)) else []) + [SPEC]


def pause(root):
    return run(PAUSE, *args_for(root), cwd=root)


def converge(root):
    return run(CONVERGE, *args_for(root), cwd=root)


def summary(root):
    return run(SUMMARY, SPEC, cwd=root)


def last(result):
    return result.stdout.rstrip("\n").split("\n")[-1].split(": ", 1)[1]


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data, indent=2))
    return path


def asked(result):
    """[(question id, [option lines])] in the order printed."""
    out = []
    for line in result.stdout.split("\n"):
        m = QUESTION_RE.match(line)
        if m:
            out.append((m.group(3), []))
        elif out and OPTION_RE.match(line):
            out[-1][1].append(line)
    return out


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

    def answer(self, root, qid, choice, words="as typed by the user", trigger=None, finding=None, pass_no=None):
        """Add the question pause printed, with an answer, as the skill would after the user replied."""
        m = load("spec_review_pause", PAUSE)
        rec = self.record(root)
        n = pass_no or len(rec["passes"])
        if trigger is None:
            trigger = qid.split(".", 1)[1] if qid.split(".", 1)[1] in ("skim", "loop") else "decision"
            finding = None if trigger == "loop" else (finding if trigger == "skim" else qid.split(".", 1)[1])
        f = next((x for x in rec["passes"][n - 1]["findings"] if x["id"] == finding), None)
        over = trigger == "skim" and finding is None
        opts = m.options_of(trigger, f["suggested_fix"] if f else None, ceiling=600, over=over)
        rec.setdefault("questions", []).append({
            "id": qid, "pass": n, "trigger": trigger, "finding": finding,
            "question": f["concrete_question"] if f else "How do you want to finish this review?",
            "options": [{"key": k, "text": t} for k, t in opts],
            "answer": {"choice": choice, "words": words, "answered_on": "2026-11-27"}})
        self.save(root, rec)
        self.assertEqual(run(RECORD, os.path.join(root, REC)).returncode, 0, run(RECORD, os.path.join(root, REC)).stdout)

    def make_high_risk(self, root, risk="data-model"):
        rec = self.record(root)
        rec["passes"][-1]["findings"][0]["risk"] = risk
        f = rec["passes"][-1]["findings"][0]
        rec["risk"] = {"tier": "high", "risks": [risk], "reasons": ["%s:%d: warning [risk.%s] %s: finding %s raises it." % (
            SPEC, f["location"]["line"] or 1, risk, f["location"]["section"], f["id"])]}
        self.save(root, rec)


# ---------------------------------------------------------------------------
# One fixture per trigger
# ---------------------------------------------------------------------------

class Triggers(unittest.TestCase):
    def test_every_pause_fixture_has_an_expectation(self):
        self.assertEqual(sorted(d for d in os.listdir(FIXTURES) if d.startswith("pause-")), sorted(EXPECTED))

    def test_fixture_records_are_valid(self):
        for case in EXPECTED:
            with self.subTest(case=case):
                result = run(RECORD, os.path.join(fixture(case), REC))
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_fixtures(self):
        for case, (code, text, trigger) in EXPECTED.items():
            with self.subTest(case=case):
                result = pause(fixture(case))
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertEqual(last(result), text, result.stdout)
                header = [l for l in result.stdout.split("\n") if HEADER_RE.match(l)]
                if trigger:
                    self.assertEqual(len(header), 1, result.stdout)
                    self.assertEqual(HEADER_RE.match(header[0]).group(1), trigger)
                else:
                    self.assertEqual(header, [])
                    self.assertEqual(asked(result), [])

    def test_each_trigger_has_a_fixture(self):
        triggers = set(t for _, _, t in EXPECTED.values() if t)
        self.assertEqual(triggers, {"decision", "loop", "sign-off", "skim"})
        loop_reasons = set(last(converge(fixture(c))).rsplit(": ", 1)[1] for c, (_, _, t) in EXPECTED.items() if t == "loop")
        self.assertEqual(loop_reasons, {"cap", "oscillation", "no-progress", "bloat-growth"})

    def test_output_starts_with_converges_status_and_verdict(self):
        for case in EXPECTED:
            with self.subTest(case=case):
                c = converge(fixture(case)).stdout.rstrip("\n").split("\n")
                p = pause(fixture(case)).stdout.split("\n")
                self.assertEqual(p[:2], c[-2:])

    def test_decision_question(self):
        result = pause(fixture("pause-decision"))
        self.assertEqual([q for q, _ in asked(result)], ["pass-1.ambiguity-4"])
        out = result.stdout
        self.assertIn("The ambiguity reviewer raised a decision only you can make (ambiguity.two-readings), in Goal & Non-Goals, line 13:", out)
        self.assertIn("   > moves every completed todo out of the store into an archive file", out)
        self.assertIn("Should `todo archive` delete completed todos after archiving them, or keep them in the archive file forever?", out)
        self.assertIn("   1. Keep them in `archive.json` forever.\n   2. Delete them from the archive after 30 days.\n"
                      "   3. Give your own answer:", out)
        self.assertIn("Whichever you choose: Either way, say so in the Goal.", out)
        self.assertIn("Reply with 1, 2, 3 or 4, and for 3 add your answer.", out)
        self.assertNotIn("ambiguity-1", out)  # the fix blocker goes to the author, never to the user

    def test_loop_questions_name_the_reason(self):
        texts = {
            "pause-cap": "The loop has used all 3 passes, and pass 3 still has 1 open blocker.",
            "pause-oscillation": "Pass 2 has a new blocker in a section the last revision changed",
            "pause-no-progress": "Pass 2 has 2 open blockers, not fewer than pass 1",
            "pause-bloat": "The last revision grew the spec from 655 to 872 words, more than max_growth 0.25 allows in one pass. "
                           "The revision is rejected: put back the copy saved before it (previous/archive-completed-todos.md).",
        }
        for case, text in texts.items():
            with self.subTest(case=case):
                result = pause(fixture(case))
                self.assertIn(text, result.stdout)
                self.assertEqual([q for q, _ in asked(result)], ["pass-%s.loop" % last(converge(fixture(case)))[len("stop at pass "):][0]])
                self.assertIn("How do you want to finish this review?", result.stdout)
        self.assertIn("Open blockers by pass: 3, 2, 1.", pause(fixture("pause-cap")).stdout)

    def test_skim_by_length_offers_split_or_trim(self):
        result = pause(fixture("pause-skim-length"))
        self.assertIn("The spec is 655 words, over this repo's length ceiling of 600 (max_words), so it fails the skim test", result.stdout)
        self.assertIn("How do you want to bring the spec under 600 words?", result.stdout)
        (qid, options), = asked(result)
        self.assertEqual(qid, "pass-1.skim")
        self.assertTrue(options[0].startswith("   1. Split it:") and options[1].startswith("   2. Trim it:"))

    def test_skim_by_slicer_offers_split_or_keep(self):
        result = pause(fixture("pause-skim-slicer"))
        (qid, options), = asked(result)
        self.assertEqual(qid, "pass-1.skim")
        self.assertTrue(options[0].startswith("   1. Split it:") and options[1].startswith("   2. Keep it as one spec:"))
        self.assertIn("Its proposed slices: 1. Archive (AC-1 to AC-6)", result.stdout)

    def test_sign_off_question(self):
        result = pause(fixture("pause-sign-off"))
        self.assertIn("gate --risk puts this spec in the high-risk tier for: data-model.", result.stdout)
        self.assertIn("Do you sign off on exactly these risks: data-model?", result.stdout)
        self.assertEqual([q for q, _ in asked(result)], ["sign-off"])

    def test_a_non_length_gate_stop_asks_nothing(self):
        result = pause(fixture("pause-gate"))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("Question", result.stdout)

    def test_continue_asks_nothing(self):
        for case in ("loop-continue-1", "loop-continue-2", "loop-late-continue"):
            with self.subTest(case=case):
                result = pause(fixture(case))
                self.assertEqual(result.returncode, 0)
                self.assertRegex(last(result), r"^no pause: continue to pass [23]$")

    def test_every_loop_fixture_gets_a_plan(self):
        # pause runs on every v0.5 fixture: its stops are questions, its gate stop is not.
        for case in sorted(d for d in os.listdir(FIXTURES) if d.startswith("loop-")):
            with self.subTest(case=case):
                result = pause(fixture(case))
                self.assertIn(result.returncode, (0, 1), result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# Which trigger fires, and in what order
# ---------------------------------------------------------------------------

class Order(TempCase):
    def test_skim_comes_before_decisions(self):
        root = self.copy("pause-skim-slicer")
        result = pause(root)
        self.assertIn("pause: ask 1 question (skim); then, if the review goes on: decision", result.stdout)
        # Keep it as one: now the decision is asked.
        self.answer(root, "pass-1.skim", "keep", trigger="skim", finding="slicer-1")
        result = pause(root)
        self.assertEqual([q for q, _ in asked(result)], ["pass-1.ambiguity-4"])
        # Answer it: the loop resumes with the fix blocker and both answers.
        self.answer(root, "pass-1.ambiguity-4", "a", "1")
        self.assertEqual(last(converge(root)), "continue to pass 2: hand 1 fix blocker and 2 answers to the author")
        self.assertEqual(last(pause(root)), "no pause: continue to pass 2")

    def test_split_ends_the_review_before_any_decision(self):
        root = self.copy("pause-skim-slicer")
        self.answer(root, "pass-1.skim", "split", "split it", trigger="skim", finding="slicer-1")
        result = pause(root)
        self.assertEqual(last(result), "no pause: ended at pass 1 (split); render the summary")
        self.assertEqual(converge(root).returncode, 1)  # the slicer's blocker is still open: the loop doesn't go on

    def test_trim_ends_the_review(self):
        root = self.copy("pause-skim-length")
        self.answer(root, "pass-1.skim", "trim", "2", trigger="skim", finding=None)
        self.assertEqual(last(pause(root)), "no pause: ended at pass 1 (trim); render the summary")

    def test_length_skim_comes_before_the_slicer_and_decisions(self):
        root = self.copy("pause-skim-slicer")
        write(os.path.join(root, ".orca-kit", "spec-review.yml"), "max_words: 600\n")
        rec = self.record(root)
        rec["passes"][0]["gates"] = "failed"
        self.save(root, rec)
        result = pause(root)
        self.assertEqual([q for q, _ in asked(result)], ["pass-1.skim"])
        self.assertIn("over this repo's length ceiling of 600", result.stdout)
        self.assertIn("The slicer reviewer says", result.stdout)
        self.assertIn("2. Trim it:", result.stdout)

    def test_sign_off_waits_until_the_loop_is_done(self):
        root = self.copy("pause-decision")
        self.make_high_risk(root)
        result = pause(root)
        self.assertIn("pause: ask 1 question (decision); then, if the review goes on: sign-off", result.stdout)
        self.assertNotIn("[sign-off]", result.stdout)
        self.answer(root, "pass-1.ambiguity-4", "other", "keep them forever")
        self.assertEqual(last(pause(root)), "no pause: continue to pass 2")  # no sign-off mid-loop

    def test_sign_off_after_finishing_with_blockers_open(self):
        root = self.copy("pause-cap")
        self.make_high_risk(root)
        self.assertIn("then, if the review goes on: sign-off", pause(root).stdout)
        self.answer(root, "pass-3.loop", "finish", "1")
        self.assertEqual([q for q, _ in asked(pause(root))], ["sign-off"])

    def test_sign_off_after_leaving_a_decision_open(self):
        root = self.copy("pause-left-open")
        self.make_high_risk(root)
        self.assertEqual([q for q, _ in asked(pause(root))], ["sign-off"])

    def test_no_sign_off_when_the_review_ends_for_a_rewrite(self):
        root = self.copy("pause-cap")
        self.make_high_risk(root)
        self.answer(root, "pass-3.loop", "refine", "2")
        self.assertEqual(last(pause(root)), "no pause: ended at pass 3 (refine); render the summary")

    def test_finish_after_a_bloat_stop_asks_no_sign_off(self):
        root = self.copy("pause-bloat")
        rec = self.record(root)
        rec["passes"][1]["findings"] = [read_json(os.path.join(fixture("pause-decision"), REC))["passes"][0]["findings"][2]]  # a nit
        self.save(root, rec)
        self.make_high_risk(root)
        self.assertNotIn("sign-off", pause(root).stdout)
        self.answer(root, "pass-2.loop", "finish", "1")
        self.assertEqual(last(pause(root)), "no pause: ended at pass 2 (finished with blockers open; put back the saved copy); render the summary")

    def test_finish_without_risk_ends(self):
        root = self.copy("pause-cap")
        self.answer(root, "pass-3.loop", "finish", "1")
        self.assertEqual(last(pause(root)), "no pause: ended at pass 3 (finished with blockers open); render the summary")

    def test_a_recorded_sign_off_ends_the_pauses(self):
        root = self.copy("pause-sign-off")
        rec = self.record(root)
        rec["sign_off"] = {"signed_off_by": "Sam Rivera", "signed_off_on": "2026-11-27", "risks": ["data-model"]}
        self.save(root, rec)
        self.assertEqual(last(pause(root)), "no pause: done at pass 2; render the summary")

    def test_a_stale_sign_off_is_asked_again(self):
        root = self.copy("pause-sign-off")
        rec = self.record(root)
        rec["sign_off"] = {"signed_off_by": "Sam Rivera", "signed_off_on": "2026-11-20", "risks": ["migration"]}
        self.save(root, rec)
        out = pause(root).stdout
        self.assertIn("The sign-off by Sam Rivera on 2026-11-20 covers migration", out)
        self.assertIn("Do you sign off on exactly these risks: data-model?", out)

    def test_bloat_asks_the_loop_question_even_with_a_slicer_blocker(self):
        root = self.copy("pause-bloat")
        rec = self.record(root)
        rec["passes"][1]["findings"] = [read_json(os.path.join(fixture("pause-skim-slicer"), REC))["passes"][0]["findings"][2]]
        rec["passes"][1]["open_blockers"] = 1
        self.save(root, rec)
        self.assertEqual([q for q, _ in asked(pause(root))], ["pass-2.loop"])

    def test_several_decisions_are_numbered_in_order(self):
        root = self.copy("pause-decision")
        rec = self.record(root)
        second = dict(rec["passes"][0]["findings"][1], id="ambiguity-5", location={"section": "Behavior & Edge Cases", "line": 40, "ref": "AC-2"})
        rec["passes"][0]["findings"].append(second)
        rec["passes"][0]["open_blockers"] = 3
        self.save(root, rec)
        result = pause(root)
        self.assertIn("Question 1 of 2 [pass-1.ambiguity-4]", result.stdout)
        self.assertIn("Question 2 of 2 [pass-1.ambiguity-5]", result.stdout)
        self.assertEqual(last(result), "pause at pass 1: ask the 2 questions one at a time, and record each answer")
        # One answered: only the other is still asked.
        self.answer(root, "pass-1.ambiguity-4", "b", "2")
        self.assertEqual([q for q, _ in asked(pause(root))], ["pass-1.ambiguity-5"])

    def test_rules_list_every_trigger_in_order(self):
        out = run(PAUSE, "--rules").stdout
        keys = re.findall(r"pause\.([a-z-]+)", out)
        self.assertEqual(keys, ["loop", "skim", "gate", "decision", "sign-off"])
        self.assertEqual(run(PAUSE, "--help").returncode, 0)


# ---------------------------------------------------------------------------
# Resuming after answers
# ---------------------------------------------------------------------------

class Resume(TempCase):
    def test_an_answered_decision_resumes_the_loop(self):
        result = converge(fixture("pause-answered"))
        self.assertEqual(result.returncode, 3, result.stdout)
        self.assertEqual(last(result), "continue to pass 2: hand 1 fix blocker and 1 answer to the author")
        self.assertIn("note [loop.answered] Goal & Non-Goals: decision blocker ambiguity.two-readings (ambiguity-4) is answered "
                      "(pass-1.ambiguity-4: other)", result.stdout)

    def test_without_the_answer_the_same_pass_stops(self):
        self.assertEqual(last(converge(fixture("pause-decision"))), "stop at pass 1: decision")

    def test_an_unanswered_question_is_not_an_answer(self):
        root = self.copy("pause-answered")
        rec = self.record(root)
        rec["questions"][0]["answer"] = None
        self.save(root, rec)
        self.assertEqual(last(converge(root)), "stop at pass 1: decision")
        self.assertEqual([q for q, _ in asked(pause(root))], ["pass-1.ambiguity-4"])

    def test_a_decision_left_open_still_stops_the_loop(self):
        self.assertEqual(last(converge(fixture("pause-left-open"))), "stop at pass 1: decision")

    def test_the_next_pass_converges(self):
        result = converge(fixture("pause-resumed"))
        self.assertEqual(result.returncode, 0)
        self.assertIn("pass 2 of 3: 0 open blockers (0 fix, 0 decision), was 3, 0 new", result.stdout)

    def test_an_answered_decision_counts_in_its_own_pass(self):
        # pass 1 had 3 open blockers, the answered decision among them: pass 2 must have fewer than 3.
        root = self.copy("pause-resumed")
        rec = self.record(root)
        p1 = rec["passes"][0]["findings"]
        rec["passes"][1]["findings"] = [f for f in p1 if f["kind"] == "fix" and f["severity"] == "blocker"] + [
            dict(p1[0], id="architecture-1", rule="architecture.codebase-drift", reviewer="architecture",
                 location={"section": "Goal & Non-Goals", "line": 13, "ref": None})]
        rec["passes"][1]["open_blockers"] = 3
        self.save(root, rec)
        result = converge(root)
        self.assertIn("3 open blockers (3 fix, 0 decision), was 3", result.stdout)
        self.assertEqual(result.returncode, 1)

    def test_answers_add_no_passes(self):
        # A decision answered at pass 3 has no pass left to apply it: the loop stops at the cap.
        root = self.copy("pause-cap")
        rec = self.record(root)
        decision = read_json(os.path.join(fixture("pause-decision"), REC))["passes"][0]["findings"][1]
        rec["passes"][2]["findings"] = [decision]
        self.save(root, rec)
        self.assertEqual(last(converge(root)), "stop at pass 3: decision")
        self.answer(root, "pass-3.ambiguity-4", "a", "1")
        self.assertEqual(last(converge(root)), "stop at pass 3: cap")
        self.assertEqual([q for q, _ in asked(pause(root))], ["pass-3.loop"])

    def test_an_earlier_answer_is_not_asked_again(self):
        result = converge(fixture("pause-keep-carried"))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("note [loop.answered] Goal & Non-Goals: decision blocker slicer.oversized (slicer-2) was answered in pass 1 "
                      "(pass-1.skim: keep), so it isn't open again", result.stdout)
        self.assertEqual(asked(pause(fixture("pause-keep-carried"))), [])

    def test_another_decision_raised_again_is_asked_again(self):
        # pass 1's decision was answered; a decision with the same rule and section in pass 2 may be a new question.
        root = self.copy("pause-resumed")
        rec = self.record(root)
        again = dict(rec["passes"][0]["findings"][2], id="ambiguity-9")
        rec["passes"][1]["findings"].append(again)
        rec["passes"][1]["open_blockers"] = 1
        self.save(root, rec)
        self.assertEqual(last(converge(root)), "stop at pass 2: decision")
        self.assertNotIn("loop.answered", converge(root).stdout)
        self.assertEqual([q for q, _ in asked(pause(root))], ["pass-2.ambiguity-9"])

    def test_an_answer_that_ends_the_review_is_never_carried(self):
        root = self.copy("pause-keep-carried")
        rec = self.record(root)
        rec["questions"][0]["answer"]["choice"] = "split"
        self.save(root, rec)
        result = converge(root)
        # Not carried: pass 2's slicer blocker is open again (3 -> 1 is still progress), so the loop stops for the user.
        self.assertEqual(last(result), "stop at pass 2: decision")
        self.assertNotIn("loop.answered", result.stdout)

    def test_without_questions_the_verdict_is_v05s(self):
        for case in sorted(d for d in os.listdir(FIXTURES) if d.startswith("loop-")):
            with self.subTest(case=case):
                self.assertNotIn("loop.answered", converge(fixture(case)).stdout)

    def test_answers_never_reach_the_reviewers(self):
        # The reviewer prompt in SKILL.md stays exactly Spec:, Repo root: and Counts:.
        with open(os.path.join(SKILL_DIR, "pauses.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("never written into the spec by the reviewers", text)
        self.assertIn("The reviewers never see them", text)


# ---------------------------------------------------------------------------
# Never picks an answer, never writes
# ---------------------------------------------------------------------------

class NeverAnswers(TempCase):
    SCRIPTS = (PAUSE, SUMMARY, CONVERGE, RECORD, GATE, FINDINGS)

    def test_no_script_writes_files(self):
        for script in self.SCRIPTS:
            with open(script, encoding="utf-8") as f:
                text = f.read()
            with self.subTest(script=os.path.basename(script)):
                self.assertIsNone(WRITES_RE.search(text))

    def test_running_every_script_changes_no_file(self):
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
            root = os.path.join(tmp, case)
            for script in (PAUSE, CONVERGE):
                run(script, *args_for(root), cwd=root)
            run(SUMMARY, SPEC, cwd=root)
            run(RECORD, REC, cwd=root)
            run(GATE, "--risk", SPEC, cwd=root)
        self.assertEqual(snapshot(), before)

    def test_questions_offer_options_and_mark_none(self):
        for case, (_, _, trigger) in EXPECTED.items():
            if not trigger:
                continue
            with self.subTest(case=case):
                result = pause(fixture(case))
                for qid, options in asked(result):
                    self.assertGreaterEqual(len(options), 2)
                    self.assertEqual([int(OPTION_RE.match(o).group(1)) for o in options], list(range(1, len(options) + 1)))
                self.assertIsNone(re.search(r"(?i)recommend|default|\(chosen\)|\bpicked\b|\[x\]", result.stdout))
                self.assertIn("Reply with", result.stdout)

    def test_pause_never_answers_its_own_question(self):
        # Asking again without a recorded answer asks the same question again; nothing changes by itself.
        for case, (code, _, trigger) in EXPECTED.items():
            if trigger:
                with self.subTest(case=case):
                    a, b = pause(fixture(case)), pause(fixture(case))
                    self.assertEqual((a.returncode, a.stdout), (b.returncode, b.stdout))

    def test_record_options_match_what_pause_prints(self):
        # The fixtures' recorded options are exactly the ones pause shows for that trigger.
        m = load("spec_review_pause", PAUSE)
        for case in EXPECTED:
            rec = read_json(os.path.join(fixture(case), REC))
            for q in rec.get("questions", []):
                with self.subTest(case=case, q=q["id"]):
                    keys = [o["key"] for o in q["options"]]
                    over = keys == ["split", "trim"]
                    f = next((x for x in rec["passes"][q["pass"] - 1]["findings"] if x["id"] == q["finding"]), None)
                    opts = m.options_of(q["trigger"], f["suggested_fix"] if f else None, ceiling=600, over=over)
                    self.assertEqual([(o["key"], o["text"]) for o in q["options"]], opts)


# ---------------------------------------------------------------------------
# The record's questions
# ---------------------------------------------------------------------------

class RecordQuestions(TempCase):
    def check(self, root):
        return run(RECORD, os.path.join(root, REC))

    def test_every_earlier_record_stays_valid(self):
        for case in sorted(os.listdir(FIXTURES)):
            rec_dir = os.path.join(FIXTURES, case, "specs", "reviews")
            if case.startswith(("risk-", "loop-")) and os.path.isdir(rec_dir) and case != "risk-record-invalid":
                for name in os.listdir(rec_dir):
                    with self.subTest(case=case):
                        self.assertEqual(run(RECORD, os.path.join(rec_dir, name)).returncode, 0)

    def test_summary_line_counts_questions(self):
        out = self.check(fixture("pause-answered")).stdout
        self.assertIn(", 1 question (1 answered)", out)
        self.assertNotIn("question", self.check(fixture("loop-decision")).stdout)

    def bad(self, change, case="pause-answered"):
        root = self.copy(case)
        rec = self.record(root)
        change(rec)
        self.save(root, rec)
        result = self.check(root)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(sorted(set(re.findall(r"error \[([a-z.-]+)\]", result.stdout))), ["record.questions"], result.stdout)
        return result.stdout

    def test_bad_questions_are_rejected(self):
        q = lambda rec: rec["questions"][0]
        cases = {
            "id": lambda rec: q(rec).update(id="q1"),
            "trigger": lambda rec: q(rec).update(trigger="product"),
            "pass": lambda rec: q(rec).update(**{"pass": 2}),
            "finding missing": lambda rec: q(rec).update(finding="ambiguity-9"),
            "finding is a fix": lambda rec: q(rec).update(finding="ambiguity-1", id="pass-1.ambiguity-1"),
            "finding is a nit": lambda rec: q(rec).update(finding="slicer-1", id="pass-1.slicer-1"),
            "skim names a non-slicer finding": lambda rec: q(rec).update(trigger="skim", id="pass-1.skim"),
            "loop names a finding": lambda rec: q(rec).update(trigger="loop", id="pass-1.loop"),
            "question": lambda rec: q(rec).update(question=" "),
            "option keys": lambda rec: q(rec)["options"].reverse(),
            "option text": lambda rec: q(rec)["options"][0].update(text=""),
            "options not a list": lambda rec: q(rec).update(options="1, 2 or 3"),
            "choice": lambda rec: q(rec)["answer"].update(choice="keep"),
            "choice not shown": lambda rec: q(rec)["answer"].update(choice="c"),
            "words": lambda rec: q(rec)["answer"].update(words=""),
            "date": lambda rec: q(rec)["answer"].update(answered_on="2026-02-30"),
            "answer field": lambda rec: q(rec)["answer"].update(by="Claude"),
            "answer not an object": lambda rec: q(rec).update(answer="other"),
            "unknown field": lambda rec: q(rec).update(recommended="suggested"),
            "missing field": lambda rec: q(rec).pop("options"),
            "duplicate": lambda rec: rec["questions"].append(json.loads(json.dumps(q(rec)))),
            "not a list": lambda rec: rec.update(questions={}),
            "not an object": lambda rec: rec["questions"].append("pass-1.loop"),
        }
        for name, change in cases.items():
            with self.subTest(case=name):
                self.bad(change)

    def test_questions_need_passes(self):
        def change(rec):
            del rec["passes"]
        self.bad(change)

    def test_decision_trigger_cant_name_the_slicer(self):
        def change(rec):
            q = rec["questions"][0]
            q.update(trigger="decision", id="pass-1.slicer-1")
        self.bad(change, "pause-keep-carried")

    def test_an_empty_list_and_an_unanswered_question_are_valid(self):
        for change in (lambda rec: rec.update(questions=[]), lambda rec: rec["questions"][0].update(answer=None)):
            root = self.copy("pause-answered")
            rec = self.record(root)
            change(rec)
            self.save(root, rec)
            self.assertEqual(self.check(root).returncode, 0)

    def test_rules_list_questions(self):
        self.assertIn("record.questions", run(RECORD, "--rules").stdout)


# ---------------------------------------------------------------------------
# The review summary
# ---------------------------------------------------------------------------

class Summary(TempCase):
    def test_golden(self):
        with open(os.path.join(fixture("pause-resumed"), "summary.txt"), encoding="utf-8") as f:
            expected = f.read()
        result = summary(fixture("pause-resumed"))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, expected)

    def test_every_fixture_renders_every_section(self):
        for case in EXPECTED:
            with self.subTest(case=case):
                result = summary(fixture(case))
                self.assertEqual(result.returncode, 0, result.stdout)
                for heading in ("Review summary: ", "Gates:", "Risk:", "Blockers:", "Questions:", "Pass history",
                                "Resolved since pass 1", "Open at pass", "Questions and answers", "Sign-off"):
                    self.assertIn(heading, result.stdout)
                self.assertIn("the spec is the single source of truth for code generation", result.stdout)
                self.assertNotRegex(result.stdout, r"(?i)ready to build(?!\.)")

    def test_resolved_and_answered(self):
        out = summary(fixture("pause-resumed")).stdout
        self.assertIn("- ambiguity.two-readings in Goal & Non-Goals (blocker, decision): raised in pass 1, answered by you (pass-1.ambiguity-4), then revised", out)
        self.assertIn("Answered on 2026-11-27: option 1 (a), in your words: \"1\"", out)

    def test_carried_answer(self):
        out = summary(fixture("pause-keep-carried")).stdout
        self.assertIn("slicer.oversized in Goal & Non-Goals (blocker, decision): answered by you in pass 1 (pass-1.skim), raised again in pass 2 and not reopened", out)
        self.assertEqual(out.count("slicer.oversized in Goal"), 1)

    def test_open_blockers_and_pending_answers(self):
        out = summary(fixture("pause-answered")).stdout
        self.assertIn("Blockers:  2 blockers open at pass 1 (1 answered, not yet applied by a revision)", out)
        self.assertIn("[answered (pass-1.ambiguity-4), not yet applied]", out)
        out = summary(fixture("pause-decision")).stdout
        self.assertIn("Not answered yet.", summary(self.unanswered()).stdout)
        self.assertIn("Questions: none asked", out)

    def unanswered(self):
        root = self.copy("pause-answered")
        rec = self.record(root)
        rec["questions"][0]["answer"] = None
        self.save(root, rec)
        return root

    def test_risk_lines(self):
        self.assertIn("Risk:      high (data-model); sign-off needed, not given", summary(fixture("pause-sign-off")).stdout)
        root = self.copy("pause-sign-off")
        rec = self.record(root)
        rec["sign_off"] = {"signed_off_by": "Sam Rivera", "signed_off_on": "2026-11-27", "risks": ["data-model"]}
        self.save(root, rec)
        self.assertIn("Risk:      high (data-model); signed off by Sam Rivera on 2026-11-27", summary(root).stdout)
        rec["sign_off"]["risks"] = ["migration"]
        self.save(root, rec)
        self.assertIn("sign-off stale", summary(root).stdout)
        self.assertIn("Risk:      low; no sign-off needed", summary(fixture("pause-cap")).stdout)

    def test_gates_line(self):
        self.assertIn("Gates:     FAILED on pass 1, the last pass", summary(fixture("pause-skim-length")).stdout)
        self.assertIn("Gates:     not recorded for pass 1", summary(fixture("pause-decision")).stdout)

    def test_a_changed_spec_gets_a_note(self):
        out = summary(fixture("pause-bloat")).stdout  # the rejected revision is still on disk in the fixture; words match
        self.assertNotIn("Note:", out)
        root = self.copy("pause-resumed")
        with open(os.path.join(root, SPEC), "a", encoding="utf-8") as f:
            f.write("\nOne more line of words here.\n")
        self.assertIn("Note: specs/archive-completed-todos.md has", summary(root).stdout)

    def test_deterministic(self):
        env = dict(os.environ, LANG="C", TZ="Pacific/Auckland", PYTHONHASHSEED="7")
        for case in EXPECTED:
            with self.subTest(case=case):
                a = summary(fixture(case))
                b = run(SUMMARY, SPEC, cwd=fixture(case), env=env)
                self.assertEqual((a.returncode, a.stdout), (b.returncode, b.stdout))

    def test_inputs(self):
        root = self.copy("pause-resumed")
        os.remove(os.path.join(root, REC))
        self.assertEqual(summary(root).returncode, 2)
        root = self.copy("pause-resumed")
        write(os.path.join(root, REC), "{")
        self.assertEqual(summary(root).returncode, 2)
        root = self.copy("pause-resumed")
        rec = self.record(root)
        del rec["passes"], rec["questions"]
        self.save(root, rec)
        self.assertEqual(summary(root).returncode, 2)
        self.assertEqual(run(SUMMARY).returncode, 2)
        self.assertEqual(run(SUMMARY, "a.md", "b.md").returncode, 2)
        self.assertEqual(run(SUMMARY, "--bogus", "a.md").returncode, 2)
        self.assertEqual(run(SUMMARY, "--help").returncode, 0)
        self.assertEqual(run(SUMMARY, "--record", REC, SPEC, cwd=fixture("pause-resumed")).returncode, 0)


class PauseInputs(TempCase):
    def test_converges_input_errors_are_exit_2(self):
        self.assertEqual(run(PAUSE, SPEC, cwd=fixture("pause-cap")).returncode, 2)  # pass 3 without --previous
        self.assertEqual(run(PAUSE).returncode, 2)
        self.assertEqual(run(PAUSE, "--bogus", SPEC).returncode, 2)
        root = self.copy("pause-decision")
        os.remove(os.path.join(root, REC))
        self.assertEqual(pause(root).returncode, 2)

    def test_deterministic(self):
        env = dict(os.environ, LANG="C", TZ="Pacific/Auckland", PYTHONHASHSEED="7")
        for case in EXPECTED:
            with self.subTest(case=case):
                a = pause(fixture(case))
                b = run(PAUSE, *args_for(fixture(case)), cwd=fixture(case), env=env)
                self.assertEqual((a.returncode, a.stdout), (b.returncode, b.stdout))


class Alternatives(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("spec_review_pause", PAUSE)

    def test_lettered_alternatives_become_options(self):
        alts, tail = self.m.alternatives("Choose: (a) names follow the tag rule; or (b) any non-empty name is allowed. Add the AC.")
        self.assertEqual(alts, ["Names follow the tag rule.", "Any non-empty name is allowed."])
        self.assertEqual(tail, "Add the AC.")
        keys = [k for k, _ in self.m.options_of("decision", "(a) one, (b) two, or (c) three")]
        self.assertEqual(keys, ["a", "b", "c", "other", "open"])

    def test_without_letters_the_user_answers_in_their_own_words(self):
        for fix in ("Choose: exit 1, or list nothing and exit 0.", "(b) out of order; (a) first", "Only (a) one option."):
            with self.subTest(fix=fix):
                self.assertEqual(self.m.alternatives(fix), ([], None))
                self.assertEqual([k for k, _ in self.m.options_of("decision", fix)], ["other", "open"])

    def test_every_option_key_set_is_valid_in_the_record(self):
        rec = load("spec_review_record", RECORD)
        for fix in ("(a) x; or (b) y", "(a) x (b) y (c) z (d) w (e) v", "no letters"):
            self.assertIn(tuple(k for k, _ in self.m.options_of("decision", fix)), rec.OPTION_KEYS["decision"])


class Docs(unittest.TestCase):
    def read(self, *parts):
        with open(os.path.join(*parts), encoding="utf-8") as f:
            return f.read()

    def test_skill_names_the_scripts_and_lists_them_available(self):
        # v0.7 made every release available; the status names the pauses and the summary as built.
        skill = self.read(SKILL_DIR, "SKILL.md")
        for name in ("pause", "summary", "pauses.md"):
            self.assertIn(name, skill)
        self.assertIn("## Status (v0.7)", skill)
        status = skill.split("## Status (v0.7)", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("not yet available", status)
        for name in ("`pause`", "`summary`"):
            self.assertIn(name, status)
        self.assertNotIn("| v0.6 |", status)

    def test_pauses_md_names_every_trigger_choice_and_option(self):
        text = self.read(SKILL_DIR, "pauses.md")
        m = load("spec_review_record", RECORD)
        for trigger in m.TRIGGERS + ("sign-off",):
            self.assertIn("`%s`" % trigger, text)
        for keys in m.OPTION_KEYS.values():
            for k in keys:
                for key in k:
                    self.assertIn("`%s`" % key, text)

    def test_roadmap_ticks_v06(self):
        text = self.read(PLUGIN_ROOT, "docs", "spec-review", "ROADMAP.md")
        section = text.split("### v0.6: Human-in-the-loop pauses ✅", 1)[1].split("\n### ", 1)[0]
        self.assertNotIn("- [ ]", section)

    def test_plugin_version(self):
        # v0.6 shipped as 0.14.0; later releases bump it (test_stats.py pins v0.7's).
        version = json.loads(self.read(PLUGIN_ROOT, ".claude-plugin", "plugin.json"))["version"]
        self.assertGreaterEqual(tuple(int(n) for n in version.split(".")), (0, 14, 0))


if __name__ == "__main__":
    unittest.main()
