---
id: add-due-dates
title: Add due dates to todos
status: draft
created: 2026-11-26
updated: 2026-11-27
accepted_by:
accepted_on:
---

## Goal & Non-Goals

Todos get an optional due date, set with `todo add --due <YYYY-MM-DD>` and shown by `todo list`, so users can see what is due first.

Why: users track deadlines in the title today, which `todo list` can't sort or show consistently.

Non-goals:

- Reminders or notifications.
- Times of day or time zones; a due date is a calendar date.
- Sorting or filtering `todo list` by due date, or changing `src/commands/export.ts`.

## Environment & Commands

Run from the repo root. CI (`.github/workflows/ci.yml`) runs, in order:

- `npm ci`
- `npm run lint` (`eslint .`, from `package.json`)
- `npm run typecheck` (`tsc --noEmit`, from `package.json`)
- `npm test` (`vitest run`, from `package.json`)

## Interfaces & Data Contracts

Existing:

- `src/types.ts` (`Todo`): gains `due: string | null`.
- `src/store.ts` (`loadTodos()`): reads all todos and runs pending store migrations.
- `src/commands/add.ts`: where `--due` is parsed.
- `src/commands/list.ts`: where the due date is shown.

New:

- Store migration `src/migrations/0002-add-due.ts`: sets `due: null` on every stored todo that has no `due` field, then bumps the store version from 1 to 2.
- CLI: `todo add <title> --due <YYYY-MM-DD>`; `--due` is optional.
- Tests: `test/migrations/0002-add-due.test.ts` and `test/commands/add.test.ts`, one test per acceptance criterion, each named starting with its ID (`AC-1: …`).

## Behavior & Edge Cases

- **AC-1:** Given a version 1 store with todos that have no `due` field, when any command loads it, then every todo has `due: null`, the store is saved as version 2, and the command behaves as before.
  verify: `npm test -- test/migrations/0002-add-due.test.ts -t "AC-1:"`
- **AC-2:** Given the user runs `todo add "Pay rent" --due 2026-12-01`, when the command finishes, then the new todo has `due: "2026-12-01"` and the command exits 0.
  verify: `npm test -- test/commands/add.test.ts -t "AC-2:"`
- **AC-3:** Given `--due` is not a real YYYY-MM-DD date (for example `--due 2026-02-30`), when the user runs `todo add`, then stderr says `invalid due date`, no todo is added, and the command exits 1.
  example: `todo add x --due 2026-02-30` → `invalid due date` on stderr, exit 1
  verify: `npm test -- test/commands/add.test.ts -t "AC-3:"`
- **AC-4:** Given the store can't be written during the migration, when a command loads it, then the error is printed to stderr, the stored file is unchanged, and the command exits 1.
  verify: `npm test -- test/migrations/0002-add-due.test.ts -t "AC-4:"`
- **AC-5:** Given a store already at version 2, when a command loads it, then the migration does not run again and the file is not rewritten.
  verify: `npm test -- test/migrations/0002-add-due.test.ts -t "AC-5:"`

| Input or condition | Expected behavior | AC |
|---|---|---|
| Invalid input: `--due` that isn't a real YYYY-MM-DD date | `invalid due date` on stderr, nothing added, exit 1 | AC-3 |
| Failure: the store can't be written during the migration | Error on stderr, file unchanged, exit 1 | AC-4 |
| State conflict: the store is already at version 2 | No migration, no rewrite | AC-5 |

## Boundaries & Decision Log

Always:

- Run `npm run lint`, `npm run typecheck` and `npm test` before calling the work done, and fix what fails.
- Write the migrated store to a temporary file and rename it over the old one.

Ask First:

- Changing any other field of `Todo`.
- Adding a dependency to `package.json`.

Never:

- Read, print, modify or commit `.env`.
- Skip, weaken or delete a test, or edit an AC, to make the Verification Gate pass.

Decision Log:

- **D-1:** Old todos get `due: null` through a versioned store migration.
  why: every reader can then rely on the field being present.
  rejected: treating a missing field as null in every reader.
  source: interview
- **D-2:** A due date is a calendar date string, YYYY-MM-DD.
  why: users asked for days, not times, and a string sorts correctly.
  rejected: a timestamp with a time zone.
  source: interview

## Verification Gate

Per acceptance criterion:

- AC-1: `npm test -- test/migrations/0002-add-due.test.ts -t "AC-1:"`
- AC-2: `npm test -- test/commands/add.test.ts -t "AC-2:"`
- AC-3: `npm test -- test/commands/add.test.ts -t "AC-3:"`
- AC-4: `npm test -- test/migrations/0002-add-due.test.ts -t "AC-4:"`
- AC-5: `npm test -- test/migrations/0002-add-due.test.ts -t "AC-5:"`

Whole suite, from Environment & Commands:

- `npm run lint`
- `npm run typecheck`
- `npm test`
