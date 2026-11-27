---
id: import-todos-from-json
title: Import todos from a JSON file
status: draft
created: 2026-11-21
updated: 2026-11-26
accepted_by:
accepted_on:
---

## Goal & Non-Goals

A new `todo import <file>` command adds the todos in a JSON file to the store, so users can move their todos from another machine.

Why: users who back up the store by copying `~/.todos.json` have no way to merge a backup into a new store.

Non-goals:

- Importing formats other than a JSON array of todos (CSV, Markdown, …).
- Importing from a URL or stdin.
- Merging or updating todos that already exist; `src/store.ts` and `todo list` (`src/commands/list.ts`) stay as they are.

## Environment & Commands

Run from the repo root. CI (`.github/workflows/ci.yml`) runs, in order:

- `npm ci`
- `npm run lint` (`eslint .`, from `package.json`)
- `npm run typecheck` (`tsc --noEmit`, from `package.json`)
- `npm test` (`vitest run`, from `package.json`)

## Interfaces & Data Contracts

Existing:

- `src/store.ts` (`loadTodos()`, `saveTodos()`): the only way to read and write the store.
- `src/types.ts` (`Todo`): the shape of every todo, and of every entry in the imported file.
- `src/cli.ts`: where commands are registered; `import` is added here.

New:

- CLI: `todo import <file>`, exactly one argument.
- Input: `<file>` holds a JSON array of `Todo`, as `~/.todos.json` does.
- stdout: `imported <n>`, where `<n>` is the number of todos added.
- Tests: `test/commands/import.test.ts`, one test per acceptance criterion, each named starting with its ID (`AC-1: …`).

## Behavior & Edge Cases

- **AC-1:** Given a file holding three todos, when the user runs `todo import <file>`, then the three todos are added to the end of the store with new IDs after the highest existing ID, stdout is `imported 3`, and the command exits 0.
  verify: `npm test -- test/commands/import.test.ts -t "AC-1:"`
- **AC-2:** Given no argument, or more than one, when the user runs `todo import`, then `usage: todo import <file>` is printed to stderr, the store is unchanged, and the command exits 2.
  example: `todo import` → `usage: todo import <file>` on stderr, exit 2
  verify: `npm test -- test/commands/import.test.ts -t "AC-2:"`
- **AC-3:** Given `<file>` doesn't exist, when the user runs `todo import <file>`, then `todo: no such file <file>` is printed to stderr, the store is unchanged, and the command exits 1.
  example: `todo import missing.json` → `todo: no such file missing.json` on stderr, exit 1
  verify: `npm test -- test/commands/import.test.ts -t "AC-3:"`
- **AC-4:** Given a todo in the file has the same title as an open todo in the store, when the user runs `todo import <file>`, then that todo is skipped, the others are added, and stdout counts only the todos added.
  verify: `npm test -- test/commands/import.test.ts -t "AC-4:"`

| Input or condition | Expected behavior | AC |
|---|---|---|
| Invalid input: no argument, or more than one | Usage error on stderr, store unchanged, exit 2 | AC-2 |
| Failure: `<file>` doesn't exist | `todo: no such file <file>` on stderr, store unchanged, exit 1 | AC-3 |
| State conflict: an imported todo has the same title as an open todo | Skipped; the rest are added | AC-4 |

## Boundaries & Decision Log

Always:

- Run `npm run lint`, `npm run typecheck` and `npm test` before calling the work done, and fix what fails.
- Read and write the store only through `loadTodos()` and `saveTodos()`.

Ask First:

- Changing `src/store.ts` or the `Todo` type.
- Adding a dependency to `package.json`.

Never:

- Read, print, modify or commit `.env`.
- Skip, weaken or delete a test, or edit an AC, to make the Verification Gate pass.

Decision Log:

- **D-1:** Imported todos get new IDs; their IDs in the file are ignored.
  why: IDs in a backup can clash with IDs already in the store.
  rejected: keeping the file's IDs and failing on a clash.
  source: interview
- **D-2:** A todo whose title matches an open todo is skipped.
  why: importing the same backup twice shouldn't duplicate the list.
  rejected: importing everything; asking per todo.
  source: interview

## Verification Gate

Per acceptance criterion:

- AC-1: `npm test -- test/commands/import.test.ts -t "AC-1:"`
- AC-2: `npm test -- test/commands/import.test.ts -t "AC-2:"`
- AC-3: `npm test -- test/commands/import.test.ts -t "AC-3:"`
- AC-4: `npm test -- test/commands/import.test.ts -t "AC-4:"`

Whole suite, from Environment & Commands:

- `npm run lint`
- `npm run typecheck`
- `npm test`
