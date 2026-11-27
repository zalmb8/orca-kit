---
id: open-a-todos-link
title: Open a todo's link
status: draft
created: 2026-11-24
updated: 2026-11-26
accepted_by:
accepted_on:
---

## Goal & Non-Goals

A new `todo open <id>` command opens the link attached to a todo in the user's default browser, so users can get from a todo to the page it is about in one step.

Why: todos already store a `link`, but users have to copy it out of the store by hand.

Non-goals:

- Attaching or editing links; `todo add` (`src/commands/add.ts`) stays as it is.
- Opening several links at once.
- Showing links in `todo list` (`src/commands/list.ts`).

## Environment & Commands

Run from the repo root. CI (`.github/workflows/ci.yml`) runs, in order:

- `npm ci`
- `npm run lint` (`eslint .`, from `package.json`)
- `npm run typecheck` (`tsc --noEmit`, from `package.json`)
- `npm test` (`vitest run`, from `package.json`)

## Interfaces & Data Contracts

Existing:

- `src/types.ts` (`Todo`): `link` is `string | null`, whatever text was stored with the todo.
- `src/store.ts` (`loadTodos()`): reads all todos.
- `src/cli.ts`: where commands are registered; `open` is added here.

New:

- CLI: `todo open <id>`, exactly one argument.
- `src/commands/open.ts`: builds the command line `open <link>` on macOS, or `xdg-open <link>` elsewhere, and runs it with `child_process.exec`.
- Tests: `test/commands/open.test.ts`, one test per acceptance criterion, each named starting with its ID (`AC-1: …`), with `exec` stubbed.

## Behavior & Edge Cases

- **AC-1:** Given todo 2 has the link `https://example.com/rent`, when the user runs `todo open 2` on macOS, then `exec` is called with `open https://example.com/rent` and the command exits 0.
  verify: `npm test -- test/commands/open.test.ts -t "AC-1:"`
- **AC-2:** Given an ID that isn't an integer, or not exactly one argument, when the user runs `todo open`, then `usage: todo open <id>` is printed to stderr and the command exits 2.
  example: `todo open x` → `usage: todo open <id>` on stderr, exit 2
  verify: `npm test -- test/commands/open.test.ts -t "AC-2:"`
- **AC-3:** Given todo 2 has `link: null`, when the user runs `todo open 2`, then `todo: todo 2 has no link` is printed to stderr, `exec` isn't called, and the command exits 1.
  example: `todo open 2` → `todo: todo 2 has no link` on stderr, exit 1
  verify: `npm test -- test/commands/open.test.ts -t "AC-3:"`
- **AC-4:** Given the browser command exits non-zero, when the user runs `todo open 2`, then its stderr is printed and the command exits 1.
  verify: `npm test -- test/commands/open.test.ts -t "AC-4:"`

| Input or condition | Expected behavior | AC |
|---|---|---|
| Invalid input: a non-integer ID, or not exactly one argument | Usage error on stderr, exit 2 | AC-2 |
| Failure: the browser command exits non-zero | Its stderr printed, exit 1 | AC-4 |
| State conflict: the todo has no link | `todo: todo <id> has no link`, exit 1 | AC-3 |

## Boundaries & Decision Log

Always:

- Run `npm run lint`, `npm run typecheck` and `npm test` before calling the work done, and fix what fails.
- Read todos only through `loadTodos()`.

Ask First:

- Changing `src/store.ts` or the `Todo` type.
- Adding a dependency to `package.json`.

Never:

- Read, print, modify or commit `.env`.
- Skip, weaken or delete a test, or edit an AC, to make the Verification Gate pass.

Decision Log:

- **D-1:** Use the platform's own opener (`open`, `xdg-open`) rather than a package.
  why: the CLI has no runtime dependencies, and both commands ship with the OS.
  rejected: the `open` npm package.
  source: `CLAUDE.md`

## Verification Gate

Per acceptance criterion:

- AC-1: `npm test -- test/commands/open.test.ts -t "AC-1:"`
- AC-2: `npm test -- test/commands/open.test.ts -t "AC-2:"`
- AC-3: `npm test -- test/commands/open.test.ts -t "AC-3:"`
- AC-4: `npm test -- test/commands/open.test.ts -t "AC-4:"`

Whole suite, from Environment & Commands:

- `npm run lint`
- `npm run typecheck`
- `npm test`
