---
id: show-due-dates-in-list
title: Show due dates in todo list
status: draft
created: 2026-11-22
updated: 2026-11-26
accepted_by:
accepted_on:
---

## Goal & Non-Goals

`todo list` shows each todo's due date after its title, so users can see what is due without opening the store.

Why: todos already carry a `due` date, but nothing shows it.

Non-goals:

- Setting or changing due dates; `todo add` (`src/commands/add.ts`) stays as it is.
- Sorting or filtering `todo list` by due date.
- Highlighting overdue todos or colouring output.

## Environment & Commands

Run from the repo root. CI (`.github/workflows/ci.yml`) runs, in order:

- `npm ci`
- `npm run lint` (`eslint .`, from `package.json`)
- `npm run typecheck` (`tsc --noEmit`, from `package.json`)
- `npm test` (`vitest run`, from `package.json`)

## Interfaces & Data Contracts

Existing:

- `src/commands/list.ts` (`list`): prints one line per todo; the due date is added here.
- `src/types.ts` (`Todo`): `due` is `string | null`, a YYYY-MM-DD date.
- `test/commands/list.test.ts`: the existing tests for `todo list`, extended here.

New:

- stdout: a todo with a due date prints as `- [ ] <title> (due YYYY-MM-DD)`; a todo with `due: null` prints as before.

## Behavior & Edge Cases

- **AC-1:** Given an open todo "Pay rent" due 2026-12-01, when the user runs `todo list`, then its line is `- [ ] Pay rent (due 2026-12-01)`.
  example: `todo list` → `- [ ] Pay rent (due 2026-12-01)`
  verify: `npm test -- test/commands/list.test.ts -t "AC-1:"`
- **AC-2:** Given a todo with `due: null`, when the user runs `todo list`, then its line is unchanged: `- [ ] <title>`.
  verify: `npm test -- test/commands/list.test.ts -t "AC-2:"`
- **AC-3:** Given a completed todo with a due date, when the user runs `todo list`, then its line is `- [x] <title> (due YYYY-MM-DD)`.
  verify: `npm test -- test/commands/list.test.ts -t "AC-3:"`
- **AC-4:** Given a stored `due` value that isn't a YYYY-MM-DD date, when the user runs `todo list`, then that todo prints without a due date and the command still exits 0.
  verify: `npm test -- test/commands/list.test.ts -t "AC-4:"`

| Input or condition | Expected behavior | AC |
|---|---|---|
| Invalid input: a stored `due` that isn't YYYY-MM-DD | Printed without a due date, exit 0 | AC-4 |
| Failure: the store can't be read | Unchanged: `todo list` already prints the error and exits 1 | AC-2 |
| State conflict: `due: null` | Printed as before | AC-2 |

## Boundaries & Decision Log

Always:

- Run `npm run lint`, `npm run typecheck` and `npm test` before calling the work done, and fix what fails.
- Keep the existing `todo list` tests passing unchanged.

Ask First:

- Changing `src/store.ts` or the `Todo` type.
- Adding a dependency to `package.json`.

Never:

- Read, print, modify or commit `.env`.
- Skip, weaken or delete a test, or edit an AC, to make the Verification Gate pass.

Decision Log:

- **D-1:** The due date goes after the title, in parentheses.
  why: the line still starts with the checkbox and title, as users read it today.
  rejected: a separate column; a second line per todo.
  source: interview

## Verification Gate

Per acceptance criterion:

- AC-1: `npm test -- test/commands/list.test.ts -t "AC-1:"`
- AC-2: `npm test -- test/commands/list.test.ts -t "AC-2:"`
- AC-3: `npm test -- test/commands/list.test.ts -t "AC-3:"`
- AC-4: `npm test -- test/commands/list.test.ts -t "AC-4:"`

Whole suite, from Environment & Commands:

- `npm run lint`
- `npm run typecheck`
- `npm test`
