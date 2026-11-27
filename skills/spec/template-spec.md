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

<The exact outcome in 1–3 sentences, then what is explicitly out of scope, so the agent stays out of adjacent code.>

## Environment & Commands

<The exact build, lint and test commands the agent runs to check its own work, plus any setup it needs.>

## Interfaces & Data Contracts

<Types, schemas, API signatures and CLI commands that the compiler and tests can check. Link to existing types instead of copying them.>

## Behavior & Edge Cases

<Every behavior is an acceptance criterion: the happy path first, then one AC per distinct edge-case outcome and invariant. IDs run AC-1, AC-2, … and are never renumbered or reused.>

- **AC-1:** Given <starting state>, when <one action>, then <observable result>.
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

<Always / Ask First / Never rules for the agent, and the architectural choices already made, each with the reason.>

## Verification Gate

<Built from the AC list: one entry per AC, in order, with its verify command copied exactly (or its TBD: line in a draft), then the whole-suite commands from Environment & Commands. List the checks; don't run them here.>

Per acceptance criterion:

- AC-1: `<verify command from AC-1>`
- AC-2: TBD: <TBD line from AC-2>

Whole suite, from Environment & Commands:

- `<lint command>`
- `<test command>`
