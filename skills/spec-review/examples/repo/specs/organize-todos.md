---
id: organize-todos
title: Organize todos with tags, projects and priorities
status: draft
created: 2026-11-25
updated: 2026-11-26
accepted_by:
accepted_on:
---

## Goal & Non-Goals

Users can organize todos three ways: tag them (`todo tag`), group them into projects (`todo project`, `todo move`), and give them a priority (`todo priority`); `todo list` gains `--tag`, `--project` and `--by-priority` to use all three.

Why: users with more than a few dozen todos can't find anything in one flat list, and each of the three has been requested separately.

Non-goals:

- Nested projects or tag hierarchies.
- Due-date reminders or notifications.
- Sharing projects between users.
- Changing `todo add` (`src/commands/add.ts`) beyond what the store needs.

## Environment & Commands

Run from the repo root. CI (`.github/workflows/ci.yml`) runs, in order:

- `npm ci`
- `npm run lint` (`eslint .`, from `package.json`)
- `npm run typecheck` (`tsc --noEmit`, from `package.json`)
- `npm test` (`vitest run`, from `package.json`)

## Interfaces & Data Contracts

Existing:

- `src/types.ts` (`Todo`): gains `tags: string[]`, `project: string | null` and `priority: "high" | "normal" | "low"`.
- `src/store.ts` (`loadTodos()`, `saveTodos()`): `loadTodos()` fills in `tags: []`, `project: null` and `priority: "normal"` for todos stored without them.
- `src/commands/list.ts` (`list`): gains the three flags.
- `src/cli.ts`: registers `tag`, `untag`, `project`, `move` and `priority`.

New:

- CLI: `todo tag <id> <tag>`, `todo untag <id> <tag>`; a tag is lowercase letters, digits and `-`.
- CLI: `todo project add <name>`, `todo project list`, `todo project remove <name>`, `todo move <id> <project|none>`.
- CLI: `todo priority <id> <high|normal|low>`.
- CLI: `todo list [--tag <tag>] [--project <name>] [--by-priority]`; the flags combine.
- Projects file: `projects.json` next to the store, a JSON array of project names.
- Tests: `test/commands/tag.test.ts`, `test/commands/project.test.ts`, `test/commands/priority.test.ts` and `test/commands/list.test.ts`, one test per acceptance criterion, each named starting with its ID (`AC-1: …`).

## Behavior & Edge Cases

- **AC-1:** Given todo 1 exists, when the user runs `todo tag 1 home`, then todo 1's tags include `home` once, and the command exits 0.
  verify: `npm test -- test/commands/tag.test.ts -t "AC-1:"`
- **AC-2:** Given todo 1 is tagged `home`, when the user runs `todo untag 1 home`, then `home` is removed and the command exits 0.
  verify: `npm test -- test/commands/tag.test.ts -t "AC-2:"`
- **AC-3:** Given a tag with characters other than lowercase letters, digits and `-`, when the user runs `todo tag 1 "Home Stuff"`, then `todo: invalid tag` is printed to stderr, nothing changes, and the command exits 2.
  example: `todo tag 1 "Home Stuff"` → `todo: invalid tag` on stderr, exit 2
  verify: `npm test -- test/commands/tag.test.ts -t "AC-3:"`
- **AC-4:** Given no project `work` exists, when the user runs `todo project add work`, then `work` is appended to `projects.json` and the command exits 0.
  verify: `npm test -- test/commands/project.test.ts -t "AC-4:"`
- **AC-5:** Given a project `work` already exists, when the user runs `todo project add work`, then `todo: project work exists` is printed to stderr and the command exits 1.
  verify: `npm test -- test/commands/project.test.ts -t "AC-5:"`
- **AC-6:** Given projects `home` and `work`, when the user runs `todo project list`, then stdout is `home` and `work`, one per line, in the order they were added.
  verify: `npm test -- test/commands/project.test.ts -t "AC-6:"`
- **AC-7:** Given project `work` exists, when the user runs `todo move 1 work`, then todo 1's project is `work`; `todo move 1 none` sets it back to null.
  verify: `npm test -- test/commands/project.test.ts -t "AC-7:"`
- **AC-8:** Given no project `garden` exists, when the user runs `todo move 1 garden`, then `todo: no project garden` is printed to stderr, nothing changes, and the command exits 1.
  verify: `npm test -- test/commands/project.test.ts -t "AC-8:"`
- **AC-9:** Given todos are in project `work`, when the user runs `todo project remove work`, then `work` is removed from `projects.json` and those todos' project becomes null.
  verify: `npm test -- test/commands/project.test.ts -t "AC-9:"`
- **AC-10:** Given todo 1 exists, when the user runs `todo priority 1 high`, then its priority is `high` and the command exits 0.
  verify: `npm test -- test/commands/priority.test.ts -t "AC-10:"`
- **AC-11:** Given a priority other than high, normal or low, when the user runs `todo priority 1 urgent`, then `usage: todo priority <id> <high|normal|low>` is printed to stderr and the command exits 2.
  verify: `npm test -- test/commands/priority.test.ts -t "AC-11:"`
- **AC-12:** Given todos tagged `home` and others not, when the user runs `todo list --tag home`, then only the todos tagged `home` are listed, in the usual format.
  verify: `npm test -- test/commands/list.test.ts -t "AC-12:"`
- **AC-13:** Given todos in several projects, when the user runs `todo list --project work`, then only todos in `work` are listed.
  verify: `npm test -- test/commands/list.test.ts -t "AC-13:"`
- **AC-14:** Given todos of every priority, when the user runs `todo list --by-priority`, then high todos come first, then normal, then low, each group in store order.
  verify: `npm test -- test/commands/list.test.ts -t "AC-14:"`
- **AC-15:** Given a store written before this change, when any command loads it, then every todo has `tags: []`, `project: null` and `priority: "normal"`, and the store file isn't rewritten until a command saves it.
  verify: `npm test -- test/commands/list.test.ts -t "AC-15:"`

| Input or condition | Expected behavior | AC |
|---|---|---|
| Invalid input: a tag with other characters | `todo: invalid tag`, exit 2 | AC-3 |
| Invalid input: an unknown priority | Usage error, exit 2 | AC-11 |
| Failure: moving to a project that doesn't exist | `todo: no project <name>`, exit 1 | AC-8 |
| State conflict: adding a project that exists | `todo: project <name> exists`, exit 1 | AC-5 |
| State conflict: removing a project that has todos | Their project becomes null | AC-9 |
| Old store: todos without the new fields | Defaults filled in on load | AC-15 |

## Boundaries & Decision Log

Always:

- Run `npm run lint`, `npm run typecheck` and `npm test` before calling the work done, and fix what fails.
- Read and write the store only through `loadTodos()` and `saveTodos()`.

Ask First:

- Any change to `src/store.ts` beyond filling in the defaults.
- Adding a dependency to `package.json`.

Never:

- Read, print, modify or commit `.env`.
- Skip, weaken or delete a test, or edit an AC, to make the Verification Gate pass.

Decision Log:

- **D-1:** Projects are listed in their own `projects.json`, so an empty project can exist.
  why: users create a project before moving todos into it.
  rejected: deriving projects from the todos' `project` fields.
  source: interview
- **D-2:** Missing fields get defaults on load instead of a store version bump.
  why: old stores keep working without a one-off rewrite.
  rejected: a versioned rewrite of the store.
  source: interview
- **D-3:** Priority has three fixed levels.
  why: users asked to separate "now" from "someday", not for a scale.
  rejected: a number from 1 to 5.
  source: interview

## Verification Gate

Per acceptance criterion:

- AC-1: `npm test -- test/commands/tag.test.ts -t "AC-1:"`
- AC-2: `npm test -- test/commands/tag.test.ts -t "AC-2:"`
- AC-3: `npm test -- test/commands/tag.test.ts -t "AC-3:"`
- AC-4: `npm test -- test/commands/project.test.ts -t "AC-4:"`
- AC-5: `npm test -- test/commands/project.test.ts -t "AC-5:"`
- AC-6: `npm test -- test/commands/project.test.ts -t "AC-6:"`
- AC-7: `npm test -- test/commands/project.test.ts -t "AC-7:"`
- AC-8: `npm test -- test/commands/project.test.ts -t "AC-8:"`
- AC-9: `npm test -- test/commands/project.test.ts -t "AC-9:"`
- AC-10: `npm test -- test/commands/priority.test.ts -t "AC-10:"`
- AC-11: `npm test -- test/commands/priority.test.ts -t "AC-11:"`
- AC-12: `npm test -- test/commands/list.test.ts -t "AC-12:"`
- AC-13: `npm test -- test/commands/list.test.ts -t "AC-13:"`
- AC-14: `npm test -- test/commands/list.test.ts -t "AC-14:"`
- AC-15: `npm test -- test/commands/list.test.ts -t "AC-15:"`

Whole suite, from Environment & Commands:

- `npm run lint`
- `npm run typecheck`
- `npm test`
