# Examples

Worked examples for `orca-kit:spec`, kept as test fixtures. Each status has its own directory, so every file can be named `<id>.md` as a real spec would be. All four pass `skills/spec/check`; the failing fixtures live in [`../tests/fixtures/`](../tests/fixtures/).

| File | Status | Produced by |
|---|---|---|
| [`idea/export-todos-as-json.md`](idea/export-todos-as-json.md) | `idea` | capture |
| [`draft/export-todos-as-json.md`](draft/export-todos-as-json.md) | `draft` | refine, run on the idea above |
| [`accepted/export-todos-as-json.md`](accepted/export-todos-as-json.md) | `accepted` | refine, run again on the draft above, then the user's yes |
| [`updated/export-todos-as-json.md`](updated/export-todos-as-json.md) | `accepted` | update, run on the accepted spec above after the build |

The updated spec is still `accepted`, so it can't sit in `accepted/` beside the spec it was updated from; its directory names the mode that wrote it instead.

## Scenario

The target repo is a small TypeScript todo CLI, `todo`, using npm.

**Capture.** Mid-session, the user says: "People keep asking how to get their todos out. Spec this idea: a way to export todos as JSON, maybe from a new command next to `todo list`." Capture writes the `idea` with no questions and no repo scan. Everything the user didn't say becomes an open question.

**Refine, scan.** The scan finds, without asking anyone:

- `package.json` scripts `build`, `lint`, `typecheck` and `test`, and a `package-lock.json`, so commands run through npm.
- `.github/workflows/ci.yml`, which runs `npm ci`, `npm run lint`, `npm run typecheck` and `npm test`.
- The `Todo` type in `src/types.ts`, `loadTodos()` in `src/store.ts`, command registration in `src/cli.ts`, the `list` command in `src/commands/list.ts` and its tests in `test/commands/list.test.ts`.
- How the closest code handles errors: `src/cli.ts` prints a usage error to stderr and exits non-zero on unexpected arguments; `loadTodos()` reads the store file in one call and throws if it can't be read or parsed; `todo list` catches that, prints it to stderr and exits non-zero.
- No test in the repo runs two `todo` processes at once.
- Protected and generated files: `.gitignore` lists `dist/` (written by `npm run build`) and `.env`; `package-lock.json` is the lockfile; `tsconfig.json` and `eslint.config.js` are the config; `src/store.ts` owns the storage format. There are no migrations and no `CODEOWNERS`.

The scan answers the open question about which fields to export: the `Todo` type already defines them. It also gives the expected behavior for invalid arguments, an unreadable or corrupt store and a concurrent save (follow `src/cli.ts`, `loadTodos()` and `todo list`), so refine doesn't ask about those. And it shows one settled choice: every command reads todos through `loadTodos()`, which becomes decision D-4 with `src/store.ts` as its source.

**Refine, guardrails.** Before asking anything, refine proposes non-goals from the idea, the obvious extensions of the goal and the adjacent code (`todo list`, `src/store.ts`), and adapts the default Always / Ask First / Never lists from `guardrails.md` to the scan: the CI commands, `list.ts` and its test, `package.json`, `src/store.ts`, `src/types.ts`, the CI and config files, `.env`, `dist/` and the lockfile. There are no migrations, so the migration default becomes the `src/store.ts` rule.

**Refine, interview.** Refine then asks only about intent:

> 1. Goal: should the export include completed todos, or only open ones?
> 2. Non-goals: I propose these as out of scope: importing JSON back in; formats other than JSON; filter or sort flags; changing `todo list` or the storage format. Confirm or change?
> 3. Decisions: should the export go to stdout, to a file, or both? And `Todo` in `src/types.ts` already defines the fields: should the export mirror it exactly, or have its own export schema?
> 4. Boundaries: here are the Always / Ask First / Never rules adapted to this repo (the lists as written in the draft, without the `src/cli.ts` rule). Confirm or change?
> 5. Edge case: when there are no todos, should `todo export` print `[]`, or nothing?

The user answers: include everything, completed or not, since it's a backup; the non-goals are right, and writing to a file is out too; stdout only, since people can redirect it; mirror `Todo`, because a separate schema would drift; the boundaries are fine, but ask first before changing `src/cli.ts` beyond registering the command. The user has no answer yet for what an empty list should print.

**Refine, write.** Every behavior becomes an acceptance criterion (AC-1 to AC-6), and every edge-case row points to one. Each AC's `verify:` line names the test it will have in `test/commands/export.test.ts`, filtered by its ID. Two gaps stay as `TBD:` lines, which a `draft` allows: the empty-list output in AC-5, and AC-6's check, since the repo has no way yet to test concurrent processes. The Verification Gate lists each AC's command, then the CI suite. Boundaries & Decision Log holds the confirmed lists, with the user's `src/cli.ts` rule under Ask First, and four decisions: D-1 to D-3 from the interview, each rejecting the options the question offered, and D-4 from the repo. The draft can't be accepted yet because of the two `TBD:` lines: `check --as accepted` fails on them and on AC-6's missing `verify:` line.

**Refine again, then accept.** Later the user says "refine the export-todos-as-json spec". The scan finds nothing new, and the guardrails have no gaps, so refine keeps them as written and asks only about the two `TBD:` lines:

> 1. Edge case: when there are no todos, should `todo export` print `[]`, or nothing?
> 2. AC-6: the repo can't run two `todo` processes in a test. Should AC-6 be checked in one process (the test changes the store file after `loadTodos()` returns and checks that stdout is still the complete array), or should we add a multi-process test harness?

The user answers: `[]`, so the output always parses; one process, since a harness isn't worth building for this. Refine fills in AC-5 and AC-6's `verify:` line, rebuilds the gate, and records both answers as D-5 and D-6. Its checklists pass with no `TBD:` lines and no open questions left, and `check --as accepted` exits 0, so it asks whether the user accepts the spec. The user says "Yes, I accept it", and refine sets `status: accepted`, `accepted_by` and `accepted_on`. The accepted spec has the same non-goals and boundaries as the draft, six decisions, and a `verify:` line on every AC.

**Build, then update.** An agent builds the command from the accepted spec. While building, it finds that `loadTodos()` in `src/store.ts` returns no todos when the store file doesn't exist yet, and adds a test `AC-5: missing store file prints []`. Seeing the first output, the user says: "Indent it, so the backups diff nicely in git." The agent writes `JSON.stringify(todos, null, 2)` in `src/commands/export.ts`. Then the user says "sync the spec".

Update finds the commit that accepted the spec and reads the diff since then on the files the spec links to, the test file its `verify:` lines name and their directories, which shows the new `src/commands/export.ts`. Together with the conversation, that gives three changes, all information only:

- **Edge case.** A missing store file is a new `Empty:` row. `loadTodos()` already returns no todos for it, so AC-5's *then* covers it, and the row points to AC-5. No AC changes, so no re-acceptance.
- **Decision.** The indentation is the user's choice, made during the build, so it becomes D-7 with `source: conversation; src/commands/export.ts`, and the user's reason as `why:`. The alternative on the table was the compact JSON the first output showed.
- **Contract and trim.** `src/commands/export.ts` and `test/commands/export.test.ts` now exist and pin the exact output, so the Interfaces & Data Contracts passage that described the output in prose becomes links to them, with the indentation noted against D-7.

Update bumps `updated` and leaves `accepted_by` and `accepted_on` alone, since nothing gated changed. The six headings, the ACs, the Non-goals and the Always / Ask First / Never lists are exactly as accepted, and the checker still prints `ok (accepted)`. Had the build shown a behavior no AC covers, such as a closed stdout pipe, update would have proposed a new AC-7 and asked the user to accept again before writing it.
