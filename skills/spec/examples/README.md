# Examples

Worked examples for `orca-kit:spec`, kept as test fixtures. Each status has its own directory, so every file can be named `<id>.md` as a real spec would be.

| File | Status | Produced by |
|---|---|---|
| [`idea/export-todos-as-json.md`](idea/export-todos-as-json.md) | `idea` | capture |
| [`draft/export-todos-as-json.md`](draft/export-todos-as-json.md) | `draft` | refine, run on the idea above |

## Scenario

The target repo is a small TypeScript todo CLI, `todo`, using npm.

**Capture.** Mid-session, the user says: "People keep asking how to get their todos out. Spec this idea: a way to export todos as JSON, maybe from a new command next to `todo list`." Capture writes the `idea` with no questions and no repo scan. Everything the user didn't say becomes an open question.

**Refine, scan.** The scan finds, without asking anyone:

- `package.json` scripts `build`, `lint`, `typecheck` and `test`, and a `package-lock.json`, so commands run through npm.
- `.github/workflows/ci.yml`, which runs `npm ci`, `npm run lint`, `npm run typecheck` and `npm test`.
- The `Todo` type in `src/types.ts`, `loadTodos()` in `src/store.ts`, command registration in `src/cli.ts`, the `list` command in `src/commands/list.ts` and its tests in `test/commands/list.test.ts`.
- How the closest code handles errors: `src/cli.ts` prints a usage error to stderr and exits non-zero on unexpected arguments; `loadTodos()` reads the store file in one call and throws if it can't be read or parsed; `todo list` catches that, prints it to stderr and exits non-zero.
- No test in the repo runs two `todo` processes at once.

The scan answers the open question about which fields to export: the `Todo` type already defines them. It also gives the expected behavior for invalid arguments, an unreadable or corrupt store and a concurrent save (follow `src/cli.ts`, `loadTodos()` and `todo list`), so refine doesn't ask about those.

**Refine, interview.** Refine then asks only about intent:

> 1. Goal: should the export include completed todos, or only open ones?
> 2. Non-goals: is importing JSON back in, or exporting other formats, out of scope?
> 3. Decisions: is it settled whether the export goes to stdout or to a file?
> 4. Edge case: when there are no todos, should `todo export` print `[]`, or nothing?

The user answers: include everything, completed or not; import and other formats are out of scope, and so are filters; stdout only, since people can redirect it. The user has no answer yet for what an empty list should print.

**Refine, write.** Every behavior becomes an acceptance criterion (AC-1 to AC-6), and every edge-case row points to one. Each AC's `verify:` line names the test it will have in `test/commands/export.test.ts`, filtered by its ID. Two gaps stay as `TBD:` lines, which a `draft` allows: the empty-list output in AC-5, and AC-6's check, since the repo has no way yet to test concurrent processes. The Verification Gate lists each AC's command, then the CI suite.
