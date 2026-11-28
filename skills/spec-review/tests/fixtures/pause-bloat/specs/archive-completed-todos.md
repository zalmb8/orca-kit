---
id: archive-completed-todos
title: Archive completed todos
status: draft
created: 2026-11-20
updated: 2026-11-26
accepted_by:
accepted_on:
---

## Goal & Non-Goals

A new `todo archive` command moves every completed todo out of the store into an archive file, so `todo list` shows only what is left to do.

Why: long-time users have hundreds of completed todos, and `todo list` prints all of them.

Archiving keeps the list short and readable for people with a long history of finished work. Archiving keeps the list short and readable for people with a long history of finished work. Archiving keeps the list short and readable for people with a long history of finished work. Archiving keeps the list short and readable for people with a long history of finished work. Archiving keeps the list short and readable for people with a long history of finished work. Archiving keeps the list short and readable for people with a long history of finished work. Archiving keeps the list short and readable for people with a long history of finished work. Archiving keeps the list short and readable for people with a long history of finished work. Archiving keeps the list short and readable for people with a long history of finished work. Archiving keeps the list short and readable for people with a long history of finished work. Archiving keeps the list short and readable for people with a long history of finished work. Archiving keeps the list short and readable for people with a long history of finished work. Archiving keeps the list short and readable for people with a long history of finished work.

Non-goals:

- Restoring archived todos.
- Archiving open todos, or todos selected by date.
- Changing `todo list` (`src/commands/list.ts`) or the store format (`src/store.ts`).

## Environment & Commands

Run from the repo root. CI (`.github/workflows/ci.yml`) runs, in order:

- `npm ci`
- `npm run lint` (`eslint .`, from `package.json`)
- `npm run typecheck` (`tsc --noEmit`, from `package.json`)
- `npm test` (`vitest run`, from `package.json`)

## Interfaces & Data Contracts

Existing:

- `src/store.ts` (`loadTodos()`, `saveTodos()`): the only way to read and write the store.
- `src/types.ts` (`Todo`): the shape of every todo.
- `src/cli.ts`: where commands are registered; `archive` is added here.

New:

- CLI: `todo archive`, no arguments.
- Archive file: `archive.json` next to the store, a JSON array of `Todo`; archived todos are appended to it.
- stdout: `archived <n>`, where `<n>` is the number of todos moved.
- Tests: `test/commands/archive.test.ts`, one test per acceptance criterion, each named starting with its ID (`AC-1: …`).

## Behavior & Edge Cases

- **AC-1:** Given the store holds open and completed todos, when the user runs `todo archive`, then every completed todo is appended to `archive.json`, removed from the store, stdout is `archived <n>`, and the command exits 0.
  verify: `npm test -- test/commands/archive.test.ts -t "AC-1:"`
- **AC-2:** Given the store holds no completed todos, when the user runs `todo archive`, then neither file changes, stdout is `archived 0`, and the command exits 0.
  example: `todo archive` → `archived 0`, exit 0
  verify: `npm test -- test/commands/archive.test.ts -t "AC-2:"`
- **AC-3:** Given any argument (for example `todo archive --all`), when the user runs it, then `usage: todo archive` is printed to stderr, no file changes, and the command exits 2.
  example: `todo archive --all` → `usage: todo archive` on stderr, exit 2
  verify: `npm test -- test/commands/archive.test.ts -t "AC-3:"`
- **AC-4:** Given a store with thousands of completed todos, when the user runs `todo archive`, then the command finishes within 2 seconds for 10,000 completed todos, with the result AC-1 gives.
  verify: `npm test -- test/commands/archive.test.ts -t "AC-4:"`
- **AC-5:** Given `archive.json` can't be written, when the user runs `todo archive`, then the error is printed to stderr, the store is unchanged, and the command exits 1.
  verify: `npm test -- test/commands/archive.test.ts -t "AC-5:"`

| Input or condition | Expected behavior | AC |
|---|---|---|
| Invalid input: any argument, such as `todo archive --all` | Usage error on stderr, no file changes, exit 2 | AC-3 |
| Failure: `archive.json` can't be written | Error on stderr, store unchanged, exit 1 | AC-5 |
| State conflict: nothing to archive | `archived 0`, no file changes | AC-2 |
| Large store: thousands of completed todos | Within 2 seconds for 10,000 todos | AC-4 |

## Boundaries & Decision Log

Always:

- Run `npm run lint`, `npm run typecheck` and `npm test` before calling the work done, and fix what fails.
- Write `archive.json` before saving the store, so a failure never loses a todo.

Ask First:

- Changing `src/store.ts` or the `Todo` type.
- Adding a dependency to `package.json`.

Never:

- Read, print, modify or commit `.env`.
- Skip, weaken or delete a test, or edit an AC, to make the Verification Gate pass.

Decision Log:

- **D-1:** Archived todos go to `archive.json` next to the store, not to a second store format.
  why: users can read it, and `Todo[]` is already the store's format.
  rejected: deleting completed todos; a separate archive format.
  source: interview

## Verification Gate

Per acceptance criterion:

- AC-1: `npm test -- test/commands/archive.test.ts -t "AC-1:"`
- AC-2: `npm test -- test/commands/archive.test.ts -t "AC-2:"`
- AC-3: `npm test -- test/commands/archive.test.ts -t "AC-3:"`
- AC-4: `npm test -- test/commands/archive.test.ts -t "AC-4:"`
- AC-5: `npm test -- test/commands/archive.test.ts -t "AC-5:"`

Whole suite, from Environment & Commands:

- `npm run lint`
- `npm run typecheck`
- `npm test`
