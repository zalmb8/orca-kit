---
id: export-todos-as-json
title: Export todos as JSON
status: accepted
created: 2026-11-24
updated: 2026-11-26
accepted_by: zalmb8
accepted_on: 2026-11-26
---

## Goal & Non-Goals

A new `todo export` command writes every todo, open and completed, to stdout as a JSON array, so users can back up their todos or use them in other tools.

Why: users keep asking how to get their todos out of the CLI; today they can only view them with `todo list`.

Non-goals:

- Importing JSON back into the CLI.
- Any format other than JSON (CSV, Markdown, …).
- Filtering or sorting flags on `todo export`.
- Writing to a file directly; users redirect stdout.
- Changing `todo list` (`src/commands/list.ts`) or the storage format (`src/store.ts`).

## Environment & Commands

Run from the repo root. CI (`.github/workflows/ci.yml`) runs, in order:

- `npm ci`
- `npm run lint` (`eslint .`, from `package.json`)
- `npm run typecheck` (`tsc --noEmit`, from `package.json`)
- `npm test` (`vitest run`, from `package.json`)

Build locally with `npm run build` (`tsc -p tsconfig.json`, from `package.json`).

## Interfaces & Data Contracts

Existing:

- `src/types.ts` (`Todo`): the shape of every todo; the export's fields come from here.
- `src/store.ts` (`loadTodos()`): reads all todos from the store.
- `src/cli.ts`: where commands are registered; `export` is added here.
- `src/commands/list.ts`: the closest existing command, to follow for structure and output.
- `test/commands/list.test.ts`: the test style to follow for the new command.

New:

- CLI: `todo export`, no arguments or flags.
- stdout: `Todo[]` as JSON, each todo with exactly the fields `Todo` defines, then a newline; nothing else.
- Tests: `test/commands/export.test.ts`, with one test per acceptance criterion, each named starting with its ID (`AC-1: …`).

## Behavior & Edge Cases

- **AC-1:** Given the store holds open and completed todos, when the user runs `todo export`, then stdout is a JSON array of every todo, open and completed, followed by a newline, and the command exits 0.
  verify: `yarn vitest test/commands/export.test.ts -t "AC-1:"`
- **AC-2:** Given a todo with every field the `Todo` type defines, when the user runs `todo export`, then that todo's JSON object has exactly those fields and values, so fields added to `Todo` later appear without changes to the command.
  verify: `npm test -- test/commands/export.test.ts -t "AC-2:"`
- **AC-3:** Given any argument or flag (for example `todo export --csv`), when the user runs it, then the usage error is printed to stderr as `src/cli.ts` does for other commands, nothing is written to stdout, and the command exits non-zero.
  example: `todo export --csv` → nothing on stdout, non-zero exit
  verify: `npm test -- test/commands/export.test.ts -t "AC-3:"`
- **AC-4:** Given `loadTodos()` throws because the store can't be read or parsed, when the user runs `todo export`, then the error is printed to stderr, nothing is written to stdout, and the command exits non-zero, as `todo list` does.
  verify: `npm test -- test/commands/export.test.ts -t "AC-4:"`
- **AC-5:** Given the store holds no todos, when the user runs `todo export`, then stdout is `[]` followed by a newline, and the command exits 0.
  example: `todo export` with an empty store → stdout `[]` and a newline, exit 0
  verify: `npm test -- test/commands/export.test.ts -t "AC-5:"`
- **AC-6:** Given another `todo` command saves the store while `todo export` reads it, when the export finishes, then its output comes from one `loadTodos()` call: either a complete JSON array or the AC-4 error, never a partial array.
  verify: `npm test -- test/commands/export.test.ts -t "AC-6:"`

| Input or condition | Expected behavior | AC |
|---|---|---|
| Invalid input: an argument or flag, such as `todo export --csv` | Usage error on stderr, nothing on stdout, non-zero exit | AC-3 |
| Failure: the store file can't be read (permissions, IO error) | Error on stderr, nothing on stdout, non-zero exit | AC-4 |
| Failure: the store file isn't valid JSON | Same as an unreadable store | AC-4 |
| Empty: no todos in the store | `[]` and a newline on stdout, exit 0 | AC-5 |
| State conflict: another `todo` command saves the store during the export | One complete array or the AC-4 error, never a partial array | AC-6 |

## Boundaries & Decision Log

Always:

- Run `npm run lint`, `npm run typecheck` and `npm test` before calling the work done, and fix what fails.
- Follow the structure and style of `src/commands/list.ts` and `test/commands/list.test.ts`.
- Write one test per AC in `test/commands/export.test.ts`, named starting with its ID and a colon (`AC-n: …`).
- Before the final commit, sync this spec with what the build found (`orca-kit:spec` update) and commit it with the code.

Ask First:

- Adding, removing or upgrading a dependency in `package.json`.
- Changing the store format, `loadTodos()` or anything else in `src/store.ts`.
- Changing the `Todo` type in `src/types.ts`.
- Changing `src/cli.ts` beyond registering `export`.
- Changing `.github/workflows/ci.yml`, `tsconfig.json` or `eslint.config.js`.

Never:

- Read, print, modify or commit `.env`.
- Edit `dist/` or `package-lock.json` by hand: `npm run build` writes `dist/`, and npm writes the lockfile.
- Refactor, rename or reformat code the goal doesn't need, such as `src/commands/list.ts`.
- Skip, weaken or delete a test, or edit an AC, to make the Verification Gate pass.

Decision Log:

- **D-1:** Output goes to stdout only.
  why: users can redirect it to a file or pipe it to another tool, and the command stays simple.
  rejected: writing to a file; writing to both stdout and a file.
  source: interview
- **D-2:** Completed todos are included.
  why: the export is meant as a full backup.
  rejected: exporting only open todos.
  source: interview
- **D-3:** The JSON mirrors the `Todo` type, with no separate export schema.
  why: the export stays in sync with the type without extra code; a separate schema would drift.
  rejected: a separate export schema with its own field list.
  source: interview
- **D-4:** The export reads todos only through `loadTodos()`.
  why: it is the store's only reader, which every command uses, and it reads the file in one call, which AC-6 relies on.
  rejected: reading the store file directly in the command.
  source: `src/store.ts`, `src/commands/list.ts`
- **D-5:** An empty store exports `[]`.
  why: the output is always valid JSON, so `todo export | jq` and other tools that parse it work with no todos.
  rejected: printing nothing.
  source: interview
- **D-6:** AC-6 is checked in one process: the test changes the store file after `loadTodos()` returns and before the output is written, and asserts stdout is still the complete array that was read.
  why: the repo has no harness for concurrent processes, and building one is outside this goal.
  rejected: a multi-process test harness.
  source: interview

## Verification Gate

Per acceptance criterion:

- AC-1: `yarn vitest test/commands/export.test.ts -t "AC-1:"`
- AC-2: `npm test -- test/commands/export.test.ts -t "AC-2:"`
- AC-3: `npm test -- test/commands/export.test.ts -t "AC-3:"`
- AC-4: `npm test -- test/commands/export.test.ts -t "AC-4:"`
- AC-5: `npm test -- test/commands/export.test.ts -t "AC-5:"`
- AC-6: `npm test -- test/commands/export.test.ts -t "AC-6:"`

Whole suite, from Environment & Commands:

- `npm run lint`
- `npm run typecheck`
- `npm test`
