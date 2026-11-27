# ADR 0001: All store access goes through src/store.ts

Status: accepted

## Context

Todos are kept in one JSON file, `~/.todos.json` (or `$TODO_STORE`). Early
commands each read and wrote the file themselves, and a crash during a write
left a truncated store that no command could load.

## Decision

- Commands read the store only with `loadTodos()` and write it only with
  `saveTodos()`, both in `src/store.ts`.
- `saveTodos()` writes to a temporary file next to the store and renames it
  over the old one, so the store is always either the old or the new version.
- No other module opens, writes or renames the store file.

## Consequences

Changing the file format, or how it is written, is a change to `src/store.ts`
only.
