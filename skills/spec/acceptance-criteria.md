# Acceptance criteria, edge cases and the Verification Gate

Refine writes Behavior & Edge Cases as a list of acceptance criteria (ACs) and an edge-case table, then builds the Verification Gate from the ACs. Read this file before writing those two sections.

## Acceptance criteria

Every behavior in Behavior & Edge Cases is an AC. Do not add free prose about behavior: if it is worth saying, it is worth an AC. This covers the happy path, every error state and every invariant.

```markdown
- **AC-1:** Given <starting state>, when <action>, then <observable result>.
  verify: `<exact command or test that checks it>`
```

- **ID.** `AC-1`, `AC-2`, … in the order written. IDs are stable: never renumber them, and never reuse the ID of a removed AC. Tests and the Verification Gate refer to them.
- **Given/When/Then.** One sentence. *Given* is the state before (data, config, environment), *when* is one action (a command, a request, an event), *then* is a result someone can observe from outside: output, exit code, a file, a response, a stored record. Not "calls `foo()`".
- **One outcome per AC.** If the *then* needs "and also" for an unrelated result, split it into two ACs.
- **`verify:`** is an indented line under the AC naming the exact command that checks it, in backticks. Use the runner and the filter syntax that Environment & Commands already uses (for example `vitest run -t`, `jest -t`, `pytest path::test_name` or `-k`, `go test -run`, `cargo test <name>`).
  - If the test doesn't exist yet, name the test file it will go in and a test name that starts with the AC ID and a colon, and filter on that: `` verify: `npm test -- test/commands/export.test.ts -t "AC-1:"` ``. The colon keeps `AC-1` from also matching `AC-10`.
  - Prefer a command that runs only this AC's check. Use a whole-suite command only when the AC is about the suite itself (for example "the build passes").
  - Never invent a runner or a command the repo doesn't have.
- **`TBD:`** In a `draft`, an AC whose check isn't known yet has a `TBD:` line in place of `verify:`, saying what is unknown: `TBD: no test harness for concurrent processes; how should this be checked?`. If the expected result itself is unknown, put `TBD:` in the *then* (`then TBD: it prints \`[]\`, or nothing?`) and keep the `verify:` line if the test is already known. An `accepted` spec has no `TBD:` lines.

## Edge cases

After the ACs, Behavior & Edge Cases always has this table:

```markdown
| Input or condition | Expected behavior | AC |
|---|---|---|
| Invalid input: <…> | <…> | AC-n |
| Failure: <…> | <…> | AC-n |
| State conflict: <…> | <…> | AC-n |
```

Walk each category against the goal and the critical files the scan found:

| Category | Look for |
|---|---|
| **Invalid input** | Missing, extra or malformed arguments, flags, fields or files; wrong types; out-of-range values; input the validators or types reject. |
| **Failure** | Network errors and timeouts, IO errors (unreadable, missing or full files and disks), corrupt stored data, a dependency or subprocess that fails, a closed pipe. |
| **State conflict** | Two writers at once, stale reads, duplicates, an item deleted or changed between read and write, running the same action twice. |
| Boundaries | Empty, one, many, the maximum size. Use `Empty:` or `Boundary:` as the prefix. |

- Start the first cell with the category (`Invalid input:`, `Failure:`, `State conflict:`, `Empty:`, `Boundary:`), so coverage is visible at a glance.
- **Every row points to an AC** that exists in the list above. Several rows can share one AC when the expected behavior is the same; the AC's *given* then covers all of them.
- **A category that can't happen** gets one line under the table with the reason, not a row: `Not applicable: state conflicts (export only reads the store).` Each of the three named categories appears either as a row or in that line.

### Where expected behavior comes from

Fill in the *Expected behavior* column from these, in order, before asking anyone:

1. What the user said in the conversation or the idea.
2. How the closest existing code handles the same case (the error handling, exit codes and messages of the sibling command, route or job the scan found). Following it is the default; say so in the row ("as `todo list` does").
3. Existing tests, validators and types, which often already define what is rejected.

Ask the user only about rows none of these answers. Put those questions in the single refine interview, as concrete choices ("When there are no todos, should `todo export` print `[]` or nothing?"). If the user doesn't know, write `TBD:` in the row's *Expected behavior* cell and in the AC's *then*.

## Verification Gate

Build it from the AC list; never write it by hand separately. It lists the checks and does not run them; a future verification skill runs them.

```markdown
Per acceptance criterion:

- AC-1: `<the AC's verify command, copied exactly>`
- AC-2: TBD: <the AC's TBD line, in a draft>

Whole suite, from Environment & Commands:

- `<lint command>`
- `<typecheck command>`
- `<test command>`
```

- One entry per AC, in ID order, with the command copied exactly from its `verify:` line, or its `TBD:` text in a draft.
- Then the whole-suite commands from Environment & Commands (lint, typecheck, test, build: whatever CI runs), in the order listed there. Leave out setup steps such as `npm ci`.
- Whenever an AC is added, removed or changes its `verify:` line, rebuild the gate.

## Check before saving

- Every behavior in Behavior & Edge Cases is an AC with an ID and Given/When/Then.
- Every AC has a `verify:` line, or a `TBD:` line in a `draft`.
- Every edge-case row names an AC that exists.
- Invalid input, failure and state conflict each appear as a row or in the `Not applicable:` line.
- The Verification Gate has exactly one entry per AC, with the same command, plus the whole-suite commands.
