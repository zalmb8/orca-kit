# todo

A small TypeScript todo CLI (`todo`), built with npm.

- One command per file in `src/commands/<name>.ts`, registered in `src/cli.ts`.
- One test file per command in `test/commands/<name>.test.ts` (vitest).
- Run `npm run lint`, `npm run typecheck` and `npm test` before calling work done.
- Architecture decisions are recorded in `docs/adr/`; follow them, or write a new ADR that supersedes one.
- No runtime dependencies: the CLI uses only Node's standard library.
