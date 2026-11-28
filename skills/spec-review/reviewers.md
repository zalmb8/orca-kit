# The advisory reviewers

Reference for the advisory review (v0.4; severity levels v0.5; malformed replies and overlap v0.8). SKILL.md says when and how to run it; this file lists the reviewers, their rule keys, how their findings are merged and deduplicated, how they are recorded, and the seeded examples.

## The five reviewers

Each is a plugin agent in `${CLAUDE_PLUGIN_ROOT}/agents/`, invoked as `orca-kit:<agent>`. Each has one rubric, read-only tools and a fixed context. It gets only the spec path and the repo root (the slicer also gets its counts line) and returns only a JSON array in the findings format.

| Agent | Tools | Context it reads | Blocker rules | Nit rules |
|---|---|---|---|---|
| `spec-review-ambiguity` | Read | The spec only | `ambiguity.weasel-word`, `ambiguity.missing-error-state`, `ambiguity.untestable-ac`, `ambiguity.two-readings` | `ambiguity.vague-prose`, `ambiguity.needs-table`, `ambiguity.unstated-detail`, `ambiguity.compound-failure` |
| `spec-review-architecture` | Read, Grep, Glob | The spec, `CLAUDE.md` / `AGENTS.md`, ADRs (`docs/adr/`, …), the files under `Existing:` | `architecture.adr-conflict`, `architecture.steering-conflict`, `architecture.codebase-drift`, `architecture.existing-mismatch` | `architecture.list-placement`, `architecture.duplicate-capability` |
| `spec-review-security` | Read, Grep, Glob | The spec, `SECURITY.md` and other security policy files, the auth and data code the spec touches | `security.trust-boundary`, `security.data-flow`, `security.auth-scope`, `security.failure-mode`, `security.policy-conflict` | `security.hardening` |
| `spec-review-blast-radius` | Read, Grep, Glob | The spec, and a repo search for the readers and writers of every contract it changes | `blast-radius.unmentioned-contract`, `blast-radius.incompatible-change` | `blast-radius.stale-reference` |
| `spec-review-slicer` | Read | The spec and the `gate --counts` line | `slicer.oversized` | `slicer.independent-parts` |

## Severity is fixed by the rule

Severity has two levels, each mapped to one action:

- **`blocker`**: the spec can't be built or tested as written without someone guessing. A `kind: fix` blocker goes back to the author through the revision loop (`loop.md`); a `kind: decision` blocker goes to the user.
- **`nit`**: a comment. Nothing has to change.

Each agent's `## Rubric` table, `| Rule | Level | Graduates | Report when |`, declares every rule a blocker rule or a nit rule. That table is the only rule table: the agent reads it as its rubric, and `findings` reads the same rows from `agents/spec-review-*.md`. It rejects a finding whose `rule` isn't in it (`finding.rule`), or whose `severity` isn't its rule's level (`finding.severity`). `findings --rules` prints the table. A reviewer decides only whether a rule applies, never how bad the problem is. A problem that is sometimes serious and sometimes not is split into two rules, such as `ambiguity.weasel-word` (blocker, in an AC) and `ambiguity.vague-prose` (nit, in context prose). The Graduates column (v0.7) marks the rules whose repeated findings `findings --stats` may propose as a deterministic check: `check` (the spec checker), `secret_patterns` or `risk_terms` (the gate config), or `no` for a judgement call, which is never proposed. Only `ambiguity.weasel-word` and `ambiguity.vague-prose` are candidates: a weasel word is a string a checker can match, while every other rule needs a reading of the spec, the code or the docs.

Each agent file says when a rule applies, with worked examples for both levels, when a finding is a `decision` rather than a `fix`, and when it sets a `risk`. Rule keys are stable: renaming one splits its graduation count (v0.7), so a rename is a deliberate change with a Decision log row. A test keeps this table, the agent files and `examples/expected.json` in step.

## Invoking a reviewer

The prompt is exactly these lines, and nothing else: no summary of the spec, no history of the conversation, no reason it was written.

```
Spec: specs/<slug>.md
Repo root: /abs/path/to/repo
```

The slicer gets a third line, `Counts: <the line gate --counts printed>`. The five run in parallel, each in a fresh context; run them again for a new pass, never continue an earlier reviewer's context.

Save each reply, as returned, to its own file outside the repo (for example `$TMPDIR/spec-review/<slug>/<reviewer>.json`). Don't repair a reply that isn't a bare JSON array (a code fence, prose around it): the validator rejects the file and its findings are dropped and reported.

**A malformed reply** is one `findings` rejects, in whole or in part (exit 1 or 2). The rule is fixed, so it stays bounded:

1. Re-run that one reviewer **once**, in a fresh context with the same prompt, and save the new reply in place of the first. Never combine the two replies, and never re-run a reviewer whose reply passed.
2. The re-run's reply is the reviewer's reply for the pass, whatever it is. If it fails too, it goes into the merge as it is: the merge drops and reports each invalid finding (or the whole reply, if it isn't a JSON array), and the other four reviewers' findings stand.
3. Never re-run a reviewer a second time in the same pass. Tell the user which reviewer was re-run, why, and what was dropped.

## Merging and deduplication

`${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings --merge <reviewer.json> ...` validates every file, then prints one JSON array on stdout: every valid finding from every file, in the order given, deduplicated. Everything else goes to stderr.

- **Dropped and reported.** A rejected finding, every finding of a file that isn't a JSON array, and a finding whose `id` an earlier file already used are dropped, each with its line on stderr. The merge goes on with the rest.
- **Duplicates.** Two findings are duplicates when they have the same `rule` and the same location: `section` equal ignoring case and runs of whitespace, `line` equal (or both `null`), `ref` equal ignoring case (or both `null`), and the same `risk`. Including `risk` means a merge never drops the finding that raises the tier.
- **Which is kept.** A `decision` over a `fix`, then the first given. Duplicates share a rule, so they share a severity. It takes the place of the first of its set, so the order stays stable. Each dropped duplicate is a `note [merge.duplicate]` line on stderr. Findings are never edited.
- **Result line.** `merged: <n> findings from <f> files: <b> blocker (<d> decision), <k> nit; <u> duplicates dropped, <r> rejected`.
- **Exit.** The worst of the files' codes (0, 1 or 2), or 1 for an id clash. stdout is always a valid findings array, so it can be passed straight to `gate --risk --findings`.

Two different rules at the same spot are not duplicates: they are two problems, each owned by one rubric. The merge is deterministic, and its tests are in `tests/test_reviewers.py`.

**Overlap is reported, never merged** (v0.8). When two kept findings from different reviewers are at the same spot (the same section, and the same line or the same ref) and their evidence names the same repo path, the merge prints a `note [merge.overlap]` line on stderr. Both findings stay in the array, and the result line is unchanged. The note is a prompt for the person reading the report: the two may be one problem that two rubrics both claimed. Deciding that needs a reading of both, which a script can't do deterministically, so it never drops either. In the first hands-on review, `architecture.codebase-drift` and `blast-radius.unmentioned-contract` / `incompatible-change` each reported the same three issues (a fixture and two tests asserting the old wording), so 7 blockers were really about 5. The fix is in the rubrics: architecture owns whether a change fits the code's design (layering, access paths, invariants, ADRs, steering rules); blast-radius owns every consumer that reads, parses, asserts or stores what changes, tests and fixtures included, even under `Existing:`.

## The review record's passes

The review record `specs/reviews/<slug>.json` (format in `risk.md`) gains an optional `passes` field:

```json
"passes": [
  { "findings": [ /* the array findings --merge printed */ ], "open_blockers": 1, "words": 655, "gates": "passed" }
]
```

- One entry per review pass, at most 3. Writing a new review replaces `passes` with one entry. Each pass of the revision loop (`loop.md`) appends one.
- `words` and `gates` (v0.5) are optional: the spec's word count and its gate result (`passed` or `failed`) for that pass. The loop writes both, and `converge` checks them against the specs it is given.
- `findings` is the merged array: every finding valid, ids unique, no two with the same rule, location and risk.
- `open_blockers` is the pass's open blockers: its `blocker` findings, less a `slicer.oversized` blocker the user answered `keep` to in an earlier pass (v0.6's carry). `record` checks it with the same function `converge` and `summary` count with (v0.8), and rejects a count that disagrees.
- Every `risk` a finding in any pass names is in `risk.risks` (v0.8: a risk a pass raised stays raised for the review), so the record's tier is the one `gate --risk` computes from the spec and every pass.
- A record with no `passes` (every v0.3 record) stays valid. `record` checks all of this under `record.passes`.

## The seeded examples

`${CLAUDE_PLUGIN_ROOT}/skills/spec-review/examples/` holds a small fake repo (`repo/`: a TypeScript todo CLI with `CLAUDE.md`, an ADR, `SECURITY.md`, the store, three commands and a script that parses `todo list`) and six draft specs in `repo/specs/`. Each spec passes `gate --risk` with a low tier, so only a reviewer can catch its seeded problem. `expected.json` lists, for each spec, the problem, the reviewer and rule that should report it, the seeded text, and the locations where a finding would be on target:

| Spec | Seeded problem | Owner and rule |
|---|---|---|
| `archive-completed-todos.md` | A weasel word ("stays fast", "gracefully") | `ambiguity.weasel-word` |
| `import-todos-from-json.md` | A missing error state: a file that isn't a JSON array of todos | `ambiguity.missing-error-state` |
| `show-due-dates-in-list.md` | An unmentioned downstream contract: `integrations/standup/digest.ts` parses `todo list` | `blast-radius.unmentioned-contract` |
| `organize-todos.md` | An oversized spec: 15 ACs across three features | `slicer.oversized` |
| `rename-a-todo.md` | Drift from ADR 0001 (store access only through `src/store.ts`) | `architecture.adr-conflict` |
| `open-a-todos-link.md` | A stored link interpolated into a shell command | `security.trust-boundary` |

The examples are for checking the reviewers' rubrics, live, after a rubric changes: run the owning reviewer on its spec with the repo root `examples/repo`, validate the output with `findings`, and check that a finding with the expected rule is there. The answers live outside `repo/`, so a reviewer that stays inside its repo root can't read them. Reviewer output is probabilistic, so this is not a unit test; the deterministic tests check that the examples, agents and rules agree.
