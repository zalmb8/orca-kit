---
id: orca-orchestration-skill
title: Orca orchestration skill
status: idea
created: 2026-11-27
updated: 2026-11-27
accepted_by:
accepted_on:
---

## Goal

A separate orca-kit skill, one level above `orca-kit:spec` and `orca-kit:spec-review`, that drives work through Orca and owns every git and GitHub call: commit, push, PR, merge and cleanup. The lower skills stay narrow and never make those calls.

## Context

The `spec-review` v0.1–v0.7 build did this by hand for each release:
- an Orca worktree and worker per release;
- the diff and tests checked;
- the PR merged;
- the worktree and branches removed;
- workers that hit a usage limit or network error restarted on the same worktree.

Git and GitHub calls are outward-facing and hard to undo, so their policy belongs in one place. The first merge was blocked until the user authorized merging.

The lower skills owe this layer contracts, not git calls: state kept in files, scripts with repeatable results, a done signal, and what belongs together (a spec with its review record). The review `summary` could be the PR body.

Two existing rules move here:
- `spec-review` v0.7's "offer a PR" for an approved graduation;
- `spec`'s "commit the spec with the code".

## Open Questions

- What are its name and trigger phrases?
- Which steps does it cover (spec, review, acceptance, build, verify, ship), and which other skills does it only call?
- Does it always use Orca workers, or the current session for small work?
- Who authorizes merging: once per run, per PR, or a repo setting?
- What must pass before a merge: local tests, CI, an independent diff review?
- How does it recover a stalled worker without losing uncommitted work?
- What does it clean up after a merge?
- How are branches and worktrees named?
- How do `spec-review` questions and sign-offs reach the user from a worker?
- Does it keep its own run record, or rely on Orca state and git history?
