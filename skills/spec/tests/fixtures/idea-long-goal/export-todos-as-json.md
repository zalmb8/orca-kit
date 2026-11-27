---
id: export-todos-as-json
title: Export todos as JSON
status: idea
created: 2026-11-24
updated: 2026-11-24
accepted_by:
accepted_on:
---

## Goal

Let users export their todos as JSON from the `todo` CLI, so they can back them up or use them in other tools. It should be quick. It should be simple. It should be reliable.

## Context

Users keep asking how to get their todos out of the CLI; today they can only view them with `todo list`. The user suggested a new command next to `todo list`.

## Open Questions

- Should the export go to stdout, to a file, or both?
- Should completed todos be included?
- Which fields does the JSON contain?
- Should the JSON be importable back into the CLI?
- What should exporting an empty todo list produce?
