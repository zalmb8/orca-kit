---
id: rename-a-todo
title: Rename a todo
status: draft
created: 2026-11-23
updated: 2026-11-26
accepted_by:
accepted_on:
---

## Goal & Non-Goals

A new `todo rename <id> <title>` command changes a todo's title, so users can fix a typo without deleting and re-adding the todo.

Why: today the only way to change a title is to edit `~/.todos.json` by hand.

Non-goals:

- Changing any field other than the title.
- Renaming several todos at once.
- Changing `todo list` (`src/commands/list.ts`) or `todo add` (`src/commands/add.ts`).

## Environment & Commands

Run from the repo root. CI (`.github/workflows/ci.yml`) runs, in order:

- `npm ci`
- `npm run lint` (`eslint .`, from `package.json`)
- `npm run typecheck` (`tsc --noEmit`, from `package.json`)
- `npm test` (`vitest run`, from `package.json`)

## Interfaces & Data Contracts

Existing:

- `src/types.ts` (`Todo`): `title` is the field that changes.
- `src/store.ts` (`STORE_PATH`): the path of the store file.
- `src/cli.ts`: where commands are registered; `rename` is added here.

New:

- CLI: `todo rename <id> <title>`; the title is every argument after the ID, joined by spaces.
- `src/commands/rename.ts`: reads the store file at `STORE_PATH` with `readFileSync`, changes the one todo's title, and writes the file back with `writeFileSync`.
- Tests: `test/commands/rename.test.ts`, one test per acceptance criterion, each named starting with its ID (`AC-1: …`).

## Behavior & Edge Cases

- **AC-1:** Given todo 3 is titled "Buy mlik", when the user runs `todo rename 3 Buy milk`, then todo 3's title is "Buy milk", every other field and todo is unchanged, and the command exits 0.
  verify: `npm test -- test/commands/rename.test.ts -t "AC-1:"`
- **AC-2:** Given an ID that isn't an integer, or no title, when the user runs `todo rename`, then `usage: todo rename <id> <title>` is printed to stderr, the store is unchanged, and the command exits 2.
  example: `todo rename x` → `usage: todo rename <id> <title>` on stderr, exit 2
  verify: `npm test -- test/commands/rename.test.ts -t "AC-2:"`
- **AC-3:** Given no todo has the ID, when the user runs `todo rename 99 New title`, then `todo: no todo 99` is printed to stderr, the store is unchanged, and the command exits 1.
  example: `todo rename 99 New title` → `todo: no todo 99` on stderr, exit 1
  verify: `npm test -- test/commands/rename.test.ts -t "AC-3:"`
- **AC-4:** Given the store file can't be read or parsed, when the user runs `todo rename`, then the error is printed to stderr and the command exits 1.
  verify: `npm test -- test/commands/rename.test.ts -t "AC-4:"`

| Input or condition | Expected behavior | AC |
|---|---|---|
| Invalid input: a non-integer ID, or no title | Usage error on stderr, store unchanged, exit 2 | AC-2 |
| Failure: the store file can't be read or parsed | Error on stderr, exit 1 | AC-4 |
| State conflict: no todo has the ID | `todo: no todo <id>` on stderr, exit 1 | AC-3 |

## Boundaries & Decision Log

Always:

- Run `npm run lint`, `npm run typecheck` and `npm test` before calling the work done, and fix what fails.
- Follow the structure of `src/commands/done.ts`.

Ask First:

- Changing the `Todo` type.
- Adding a dependency to `package.json`.

Never:

- Read, print, modify or commit `.env`.
- Skip, weaken or delete a test, or edit an AC, to make the Verification Gate pass.

Decision Log:

- **D-1:** `todo rename` reads and writes the store file itself.
  why: a rename touches one field of one todo, so loading and saving every todo is more than it needs.
  rejected: `loadTodos()` and `saveTodos()`.
  source: interview

## Verification Gate

Per acceptance criterion:

- AC-1: `npm test -- test/commands/rename.test.ts -t "AC-1:"`
- AC-2: `npm test -- test/commands/rename.test.ts -t "AC-2:"`
- AC-3: `npm test -- test/commands/rename.test.ts -t "AC-3:"`
- AC-4: `npm test -- test/commands/rename.test.ts -t "AC-4:"`

Whole suite, from Environment & Commands:

- `npm run lint`
- `npm run typecheck`
- `npm test`
