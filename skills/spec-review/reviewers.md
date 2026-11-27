# The advisory reviewers

Reference for the advisory review (v0.4). SKILL.md says when and how to run it; this file lists the reviewers, their rule keys, how their findings are merged and deduplicated, how they are recorded, and the seeded examples.

## The five reviewers

Each is a plugin agent in `${CLAUDE_PLUGIN_ROOT}/agents/`, invoked as `orca-kit:<agent>`. Each has one rubric, read-only tools and a fixed context. It gets only the spec path and the repo root (the slicer also gets its counts line) and returns only a JSON array in the findings format.

| Agent | Tools | Context it reads | Rule keys |
|---|---|---|---|
| `spec-review-ambiguity` | Read | The spec only | `ambiguity.weasel-word`, `ambiguity.missing-error-state`, `ambiguity.untestable-ac`, `ambiguity.needs-table`, `ambiguity.two-readings` |
| `spec-review-architecture` | Read, Grep, Glob | The spec, `CLAUDE.md` / `AGENTS.md`, ADRs (`docs/adr/`, …), the files under `Existing:` | `architecture.adr-conflict`, `architecture.steering-conflict`, `architecture.codebase-drift`, `architecture.existing-mismatch`, `architecture.duplicate-capability` |
| `spec-review-security` | Read, Grep, Glob | The spec, `SECURITY.md` and other security policy files, the auth and data code the spec touches | `security.trust-boundary`, `security.data-flow`, `security.auth-scope`, `security.failure-mode`, `security.policy-conflict` |
| `spec-review-blast-radius` | Read, Grep, Glob | The spec, and a repo search for the readers and writers of every contract it changes | `blast-radius.unmentioned-contract`, `blast-radius.incompatible-change` |
| `spec-review-slicer` | Read | The spec and the `gate --counts` line | `slicer.oversized`, `slicer.independent-parts` |

Each agent file says when its findings are a `blocker`, `warning` or `nit`, when they are a `decision` rather than a `fix`, and when they set a `risk`. Rule keys are stable: renaming one splits its graduation count (v0.7), so a rename is a deliberate change with a Decision log row. A test keeps this table, the agent files and `examples/expected.json` in step.

## Invoking a reviewer

The prompt is exactly these lines, and nothing else: no summary of the spec, no history of the conversation, no reason it was written.

```
Spec: specs/<slug>.md
Repo root: /abs/path/to/repo
```

The slicer gets a third line, `Counts: <the line gate --counts printed>`. The five run in parallel, each in a fresh context; run them again for a new pass, never continue an earlier reviewer's context.

Save each reply, as returned, to its own file outside the repo (for example `$TMPDIR/spec-review/<slug>/<reviewer>.json`). Don't repair a reply that isn't a bare JSON array (a code fence, prose around it): the validator rejects the file and its findings are dropped and reported. That reviewer can be re-run once in a fresh context; say so if it is.

## Merging and deduplication

`${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings --merge <reviewer.json> ...` validates every file, then prints one JSON array on stdout: every valid finding from every file, in the order given, deduplicated. Everything else goes to stderr.

- **Dropped and reported.** A rejected finding, every finding of a file that isn't a JSON array, and a finding whose `id` an earlier file already used are dropped, each with its line on stderr. The merge goes on with the rest.
- **Duplicates.** Two findings are duplicates when they have the same `rule` and the same location: `section` equal ignoring case and runs of whitespace, `line` equal (or both `null`), `ref` equal ignoring case (or both `null`), and the same `risk`. Including `risk` means a merge never drops the finding that raises the tier.
- **Which is kept.** The most severe (blocker, then warning, then nit), then a `decision` over a `fix`, then the first given. It takes the place of the first of its set, so the order stays stable. Each dropped duplicate is a `note [merge.duplicate]` line on stderr. Findings are never edited.
- **Result line.** `merged: <n> findings from <f> files: <b> blocker (<d> decision), <w> warning, <k> nit; <u> duplicates dropped, <r> rejected`.
- **Exit.** The worst of the files' codes (0, 1 or 2), or 1 for an id clash. stdout is always a valid findings array, so it can be passed straight to `gate --risk --findings`.

Two different rules at the same spot are not duplicates: they are two problems, each owned by one rubric. The merge is deterministic, and its tests are in `tests/test_reviewers.py`.

## The review record's passes

The review record `specs/reviews/<slug>.json` (format in `risk.md`) gains an optional `passes` field:

```json
"passes": [
  { "findings": [ /* the array findings --merge printed */ ], "open_blockers": 1 }
]
```

- One entry per review pass, at most 3. In v0.4 a review is one pass: writing a new review replaces `passes` with one entry. The loop (v0.5) appends.
- `findings` is the merged array: every finding valid, ids unique, no two with the same rule, location and risk.
- `open_blockers` is the number of `blocker` findings in that pass.
- Every `risk` a finding in the last pass names is in `risk.risks`, so the record's tier is the one `gate --risk --findings` computed from those findings.
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
