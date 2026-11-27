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

The scan answers the open question about which fields to export: the `Todo` type already defines them.

**Refine, interview.** Refine then asks only about intent:

> 1. Goal: should the export include completed todos, or only open ones?
> 2. Non-goals: is importing JSON back in, or exporting other formats, out of scope?
> 3. Decisions: is it settled whether the export goes to stdout or to a file?

The user answers: include everything, completed or not; import and other formats are out of scope, and so are filters; stdout only, since people can redirect it. The user has no answer yet for what an empty list should print, so that stays a `TBD` in the draft.
