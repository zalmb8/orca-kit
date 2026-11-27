---
id: <slug>
title: <Short title>
status: draft
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
accepted_by:
accepted_on:
---

## Goal & Non-Goals

<The exact outcome in 1–3 sentences, then a short paragraph on why.>

Non-goals:

- <A feature nobody asked for, or adjacent code an agent might be tempted to change, named by command or path. At least one item; confirmed by the user.>

## Environment & Commands

<The exact build, lint and test commands the agent runs to check its own work, plus any setup it needs.>

## Interfaces & Data Contracts

<Types, schemas, API signatures and CLI commands that the compiler and tests can check, in two lists. Link to existing types instead of copying them.>

Existing:

- `<repo-relative path>` (`<Symbol>`): <why it matters for the goal>.

New:

- <The new contract in code, in terms of the existing types: a signature, type, schema or CLI usage in backticks or a fenced block, e.g. CLI: `<command> <args>`.>

## Behavior & Edge Cases

<Every behavior is an acceptance criterion: the happy path first, then one AC per distinct edge-case outcome and invariant. IDs run AC-1, AC-2, … and are never renumbered or reused.>

- **AC-1:** Given <starting state>, when <one action>, then <observable result>.
  example: `<exact input or command>` → <expected result, with literal output in backticks>
  verify: `<exact command or test that checks it>`
- **AC-2:** Given <…>, when <…>, then <…>.
  TBD: <what is unknown about the check; allowed only in a draft>

<Edge cases: cover invalid input, failure states (network, IO, corrupt data, …) and state conflicts wherever they apply. Every row points to an AC above. A category that can't happen goes in a "Not applicable:" line with the reason.>

| Input or condition | Expected behavior | AC |
|---|---|---|
| Invalid input: <…> | <…> | AC-n |
| Failure: <…> | <…> | AC-n |
| State conflict: <…> | <…> | AC-n |

## Boundaries & Decision Log

<Always / Ask First / Never rules for the agent, adapted from the defaults in guardrails.md to the repo's real commands and paths, then the Decision Log. Each list has at least one item.>

Always:

- <Something the agent does every time, e.g. run the whole-suite commands before calling the work done.>

Ask First:

- <A change the agent asks about before making, e.g. adding a dependency to `<manifest>`.>

Never:

- <Something the agent must not do, e.g. edit `<generated path>` by hand.>

Decision Log:

<Only decisions the user made or the repo already settled; never invented. IDs run D-1, D-2, … and are never renumbered or reused.>

- **D-1:** <The decision, in one sentence.>
  why: <the reason>
  rejected: <the alternatives considered and not chosen>
  source: <interview, or the repo paths that show it>

## Verification Gate

<Built from the AC list: one entry per AC, in order, with its verify command copied exactly (or its TBD: line in a draft), then the whole-suite commands from Environment & Commands. List the checks; don't run them here.>

Per acceptance criterion:

- AC-1: `<verify command from AC-1>`
- AC-2: TBD: <TBD line from AC-2>

Whole suite, from Environment & Commands:

- `<lint command>`
- `<test command>`
