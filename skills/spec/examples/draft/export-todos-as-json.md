---
id: export-todos-as-json
title: Export todos as JSON
status: draft
created: 2026-11-24
updated: 2026-11-26
accepted_by:
accepted_on:
---

## Goal & Non-Goals

A new `todo export` command writes every todo, open and completed, to stdout as a JSON array, so users can back up their todos or use them in other tools.

Why: users keep asking how to get their todos out of the CLI; today they can only view them with `todo list`.

Non-goals:

- Importing JSON back into the CLI.
- Any format other than JSON (CSV, Markdown, …).
- Filtering or sorting flags on `todo export`.
- Writing to a file directly; users redirect stdout.
- Changing `todo list` or the storage format.

## Environment & Commands

Run from the repo root. CI (`.github/workflows/ci.yml`) runs, in order:

- `npm ci`
- `npm run lint` (`eslint .`, from `package.json`)
- `npm run typecheck` (`tsc --noEmit`, from `package.json`)
- `npm test` (`vitest run`, from `package.json`)

Build locally with `npm run build` (`tsc -p tsconfig.json`, from `package.json`).

## Interfaces & Data Contracts

Existing code to build on:

- `src/types.ts` (`Todo`): the shape of every todo; the export's fields come from here.
- `src/store.ts` (`loadTodos()`): reads all todos from the store.
- `src/cli.ts`: where commands are registered; `export` is added here.
- `src/commands/list.ts`: the closest existing command, to follow for structure and output.
- `test/commands/list.test.ts`: the test style to follow for the new command.

New contract:

- CLI: `todo export`, no arguments or flags.
- Output: a JSON array of `Todo` objects on stdout, with each todo's fields exactly as `Todo` defines them, followed by a newline. Nothing else is written to stdout.

## Behavior & Edge Cases

- Happy path: `todo export` loads every todo with `loadTodos()`, open and completed alike, prints them as a JSON array, and exits 0.
- If the store can't be read, print the error to stderr, write nothing to stdout, and exit non-zero, as `todo list` does.
- Fields added to `Todo` later appear in the export automatically.
- TBD: what should exporting an empty todo list produce (`[]`, or nothing)?

## Boundaries & Decision Log

- Decision: output goes to stdout only. Why: users can redirect it to a file or pipe it to another tool, and the command stays simple.
- Decision: the JSON mirrors the `Todo` type rather than a separate export schema. Why: the export stays in sync with the type without extra code.
- Decision: completed todos are included. Why: the export is meant as a full backup.
- TBD: boundaries for the agent.

## Verification Gate

- `npm run lint`, `npm run typecheck` and `npm test` pass, as in CI.
- New tests for `todo export`, next to `test/commands/list.test.ts`, cover open and completed todos, the JSON shape, and a store read failure.
