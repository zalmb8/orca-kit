---
id: oscillation-by-finding-location
title: Oscillation by finding location
status: accepted
created: 2026-11-27
updated: 2026-11-27
accepted_by: zalmb8
accepted_on: 2026-11-27
---

## Goal & Non-Goals

`skills/spec-review/converge` counts a new blocker as oscillation only when the revision changed the text at the finding's own location: the AC or decision its `location.ref` names, with the edge-case rows that point to it, in its `location.section`. With no ref, or a ref that matches nothing, it falls back to today's whole-section comparison.

Today a new blocker is oscillation, and stops the loop, whenever its `## ` section changed between `--previous` and the spec. That is too coarse: in a live run a blocker on AC-5 was counted as oscillation because its section changed, though AC-5's text was untouched. Background: `docs/spec-review/ROADMAP.md` (the v0.5 Decision Log rows on oscillation and same-blocker identity) and `skills/spec-review/loop.md`.

Non-goals:

- Changing same-blocker identity (`blocker_key`, `new_blockers` in `skills/spec-review/converge`): it stays rule and section, as a multiset.
- Changing `skills/spec-review/findings.schema.json`, the `findings` validator, or the reviewer agents' `location.ref` instructions in `agents/spec-review-*.md`.
- Changing the stop order or any verdict other than oscillation versus late.
- Changing the logic of `skills/spec-review/pause` or `skills/spec-review/summary`; only pause's oscillation wording changes.

## Environment & Commands

- Test: `python3 -m unittest discover -s skills/spec-review/tests` (from `CLAUDE.md`; the repo has no CI config).
- Python 3 standard library only; no install step (`skills/spec-review/converge` docstring).

## Interfaces & Data Contracts

Existing:

- `skills/spec-review/converge` (`assess`, `changed_sections`, `sections_of`, `blocker_key`): where a new blocker is split into oscillation (`caused`) and late.
- `skills/spec-review/findings.schema.json` (`location`): `location.ref` is text or null.
- `skills/spec-review/pause` (`LOOP_TEXT`): the oscillation question's wording.
- `skills/spec-review/tests/test_loop.py` (`EXPECTED`, `ChangedSections`, `test_new_blockers_stop_even_when_the_count_falls`): the loop's fixture verdicts, section tests and the oscillation message assertion.
- `skills/spec-review/tests/test_pause.py` (`EXPECTED`, `test_each_trigger_has_a_fixture`, `test_loop_questions_name_the_reason`): pause's oscillation fixture and wording assertion.
- `skills/spec-review/tests/fixtures/loop-oscillation/`, `skills/spec-review/tests/fixtures/loop-oscillation-fewer/` and `skills/spec-review/tests/fixtures/pause-oscillation/`: pass 2's new blocker `ambiguity-5` has `ref: AC-1`, but only AC-4 changed.
- `skills/spec-review/loop.md`: "The verdict" table and "The same blocker".
- `docs/spec-review/ROADMAP.md`: the v0.5 Decision Log.
- `.claude-plugin/plugin.json` (`version`): bumped for the change.

New:

- `location_text(section_text: str, ref: str | None) -> str | None` in `converge`: the lines of every list item starting `- **<ref>:**` or `- <ref>:` with its indented continuation lines, then every table row whose last cell, split on commas, lists `<ref>`, trailing spaces dropped, ref matched ignoring case and surrounding spaces; `None` when `ref` is null or nothing matches.
- A finding's location changed when the ref's `location_text` differs between `--previous` and the spec in its section, or is `None` in exactly one; when `None` in both, when the section changed (today's rule).
- Oscillation error: `blocker <rule> (<id>, <kind>) is new in pass <n>, in <ref>, which the revision changed`; the section text stays for the section fallback.
- Late note: `blocker <rule> (<id>, <kind>) is new in pass <n>, in <ref>, which the revision didn't change`; the section text stays for the section fallback.
- Status line: unchanged byte for byte, `(<k> in changed sections)` counting oscillation blockers.
- `pause` `LOOP_TEXT["oscillation"]`: `Pass %(n)d has a new blocker in a part of the spec the last revision changed, so another pass would trade one problem for another.`

## Behavior & Edge Cases

- **AC-1:** Given pass 2 has a new blocker with `ref: AC-5` in Behavior & Edge Cases, and the revision changed that section but not AC-5's item or any edge-case row naming AC-5, when `converge` runs, then the blocker is a `note [loop.late]` line, not oscillation.
  example: new blocker `ambiguity.untestable-ac (ambiguity-5, fix)` with `ref: AC-5`, only AC-4 edited, open blockers 3 → 2 → note `in AC-5, which the revision didn't change`, verdict `continue to pass 3: hand 2 fix blockers to the author`, exit 3
  verify: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_1_`
- **AC-2:** Given a new blocker whose ref names an AC or decision, when the revision changed that item's line or one of its indented lines, then `converge` stops with oscillation and names the ref.
  example: new blocker with `ref: AC-4`, AC-4's *then* edited → `error [loop.oscillation] Behavior & Edge Cases: blocker ambiguity.untestable-ac (ambiguity-5, fix) is new in pass 2, in AC-4, which the revision changed. Fix: Stop and ask the user; the revision introduced a blocker, so another pass won't converge.`, verdict `stop at pass 2: oscillation`, exit 1
  verify: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_2_`
- **AC-3:** Given a new blocker with `ref: AC-n`, when the revision changed only an edge-case row whose AC cell is `AC-n`, then `converge` stops with oscillation.
  verify: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_3_`
- **AC-4:** Given a new blocker with `ref: D-n` in Boundaries & Decision Log, when the revision changed that section but not D-n's entry, then the blocker is late, not oscillation.
  verify: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_4_`
- **AC-5:** Given a new blocker with `ref: null`, when `converge` runs, then it is oscillation exactly when its section changed, with today's messages.
  verify: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_5_`
- **AC-6:** Given a new blocker whose ref matches nothing in its section in either spec, when `converge` runs, then the section comparison decides, as for a null ref.
  verify: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_6_`
- **AC-7:** Given a new blocker whose ref matches in exactly one of the two specs (the AC was added, removed or renumbered), when `converge` runs, then the location counts as changed and the loop stops with oscillation.
  verify: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_7_`
- **AC-8:** Given a new blocker in a section the spec doesn't have, when `converge` runs, then it is oscillation whatever its ref, as today.
  verify: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_8_`
- **AC-9:** Given any pass 2 or 3, when `converge` runs, then the status line has today's format, with `(<k> in changed sections)` counting the oscillation blockers.
  example: `loop-oscillation-fewer` after the fixture edit → status contains `was 3, 1 new (1 in changed sections)`
  verify: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_9_`
- **AC-10:** Given an oscillation stop, when `pause` runs, then the loop question's body is the new `LOOP_TEXT["oscillation"]` text.
  example: `pause` on a pass 2 `oscillation` stop → `Pass 2 has a new blocker in a part of the spec the last revision changed, so another pass would trade one problem for another.`
  verify: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_10_`
- **AC-11:** Given the `loop-oscillation`, `loop-oscillation-fewer` and `pause-oscillation` fixtures with pass 2's new blocker moved to `ref: AC-4`, when the suite runs, then all three still stop at pass 2 with oscillation, `EXPECTED` in both test files and pause's loop reasons are unchanged, and the two wording assertions expect the new text.
  example: `test_new_blockers_stop_even_when_the_count_falls` → expects `ambiguity.untestable-ac (ambiguity-5, fix) is new in pass 2, in AC-4, which the revision changed`
  example: `test_loop_questions_name_the_reason` → expects `Pass 2 has a new blocker in a part of the spec the last revision changed`
  verify: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_11_`

| Input or condition | Expected behavior | AC |
|---|---|---|
| Invalid input: ref names nothing in its section (`AC-99`, `Non-goals`, `AC-5, AC-6`) | Section comparison decides | AC-6 |
| Invalid input: ref differs only in case or spaces (` ac-5 `) | Matches `AC-5` | AC-2 |
| State conflict: the AC was added, removed or renumbered by the revision | Counts as changed; oscillation | AC-7 |
| State conflict: the same ID appears twice in the section | All its items and rows are compared together | AC-2 |
| Boundary: an edge-case row's AC cell is `AC-2, AC-7` | The row belongs to both AC-2 and AC-7 | AC-3 |
| Boundary: `ref: AC-5` in Verification Gate | Its `- AC-5:` entry is the location | AC-2 |
| Boundary: the section was removed by the revision | Oscillation, as today | AC-8 |
| Empty: `ref: null` | Section comparison decides | AC-5 |

Not applicable: failure states (no new IO; `converge` already reads both specs, and read errors stay exit 2 as today).

## Boundaries & Decision Log

Always:

- Follow the repo rules in `CLAUDE.md`, including bumping `.claude-plugin/plugin.json`'s `version`.
- Run `python3 -m unittest discover -s skills/spec-review/tests` before calling the work done, and fix what fails.
- Follow the structure of `changed_sections` in `skills/spec-review/converge` and the fixture style of `skills/spec-review/tests/test_loop.py`.
- Write one test per AC, named `test_ac_<n>_…` (unittest method names can't hold `AC-n:`).
- Before the final commit, sync this spec with what the build found (`orca-kit:spec` update) and commit it with the code.

Ask First:

- Importing anything outside the Python standard library in `skills/spec-review/converge`.
- Changing `skills/spec-review/findings.schema.json` or the record format (`skills/spec-review/record`).
- Changing `converge`'s exit codes, verdict lines or any output Interfaces & Data Contracts doesn't list.

Never:

- Changing `blocker_key` or `new_blockers` in `skills/spec-review/converge`.
- Deleting or loosening an existing test in `skills/spec-review/tests/`, or editing an AC, to make the Verification Gate pass. Updating the expected strings AC-11 names to the new contract is allowed.
- Refactoring the rest of `converge`, `pause` or `summary`.

Decision Log:

- **D-1:** A ref's location is its AC or decision item, with indented lines, plus every edge-case row whose AC cell, split on commas, lists it, within the finding's section.
  why: matches the "AC or edge-case row" the change describes; edge-case rows have no ID of their own; a row for several ACs belongs to each.
  rejected: the item alone; the item, its rows and its Verification Gate entry across sections; a row only when its whole AC cell equals the ref.
  source: interview, review question pass-1.ambiguity-1
- **D-2:** A ref that matches nothing in its section in either spec falls back to the section comparison.
  why: the same as having no ref.
  rejected: counting it as changed.
  source: interview
- **D-3:** The status line stays byte for byte; the oscillation and late messages name the ref, and pause's oscillation text says "a part of the spec".
  why: keeps the status format others parse while saying what changed.
  rejected: changing no text; renaming the status line to `in changed locations`.
  source: interview
- **D-4:** The three oscillation fixtures (`loop-oscillation`, `loop-oscillation-fewer`, `pause-oscillation`) move pass 2's new blocker to `ref: AC-4`, and new fixtures cover an untouched AC.
  why: keeps oscillation covered by fixtures and adds the live case as its own regression.
  rejected: keeping the fixtures and changing their expected verdicts.
  source: interview
- **D-5:** The change also updates `loop.md`, `converge`'s docstring and adds a ROADMAP Decision Log row superseding the v0.5 oscillation row.
  why: the docs state today's section rule.
  rejected: leaving the docs as they are.
  source: interview
- **D-6:** Same-blocker identity stays rule and section; only the oscillation test uses the ref.
  why: fresh reviewers anchor the same problem differently, so refs would make surviving blockers look new.
  rejected: identity by rule, section and ref.
  source: `docs/spec-review/ROADMAP.md`
- **D-7:** A location present in only one spec counts as changed, and refs match ignoring case.
  why: a section missing from either file already counts as changed, and the merge already compares refs ignoring case.
  rejected: treating a missing location as unchanged; case-sensitive refs.
  source: `skills/spec-review/converge`, `skills/spec-review/reviewers.md`

## Verification Gate

Per acceptance criterion:

- AC-1: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_1_`
- AC-2: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_2_`
- AC-3: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_3_`
- AC-4: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_4_`
- AC-5: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_5_`
- AC-6: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_6_`
- AC-7: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_7_`
- AC-8: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_8_`
- AC-9: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_9_`
- AC-10: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_10_`
- AC-11: `python3 -m unittest discover -s skills/spec-review/tests -k test_ac_11_`

Whole suite, from Environment & Commands:

- `python3 -m unittest discover -s skills/spec-review/tests`
