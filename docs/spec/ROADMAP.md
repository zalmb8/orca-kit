# `orca-kit:spec`: design and roadmap

A skill that writes and maintains specifications for agentic development. A spec is a contract kept in the repo and versioned with the code. It connects what the user wants to what an agent builds, and it stays short so it doesn't flood the agent's context.

## Scope

The skill **writes and maintains specs**. It has three modes:

| Mode | Trigger phrases | Starts from | Leaves it at | What it does |
|---|---|---|---|---|
| **capture** | "spec this idea", "capture this", "jot down a spec for…" | nothing | `idea` | Writes `specs/<slug>.md` from what's already in the conversation: a goal, a little context and open questions. No interview and no repo scan. |
| **refine** | "refine the X spec", "flesh out X", "make X ready to build" | `idea` or `draft` | `draft`, or `accepted` once the user approves | Scans the repo for commands, critical files and types, asks the user about whatever the repo can't answer, and fills in all six sections. Sets `accepted` only on the user's explicit yes. |
| **update** | "update the spec with what we learned", "sync the spec" | `accepted` | `accepted` | Writes discoveries made during implementation back into the spec and trims prose that types and tests now cover. If the acceptance criteria change, it asks the user to accept again. |

### Non-goals

- Running verification or writing a verification report. A future verification skill owns this.
- Setting `done` or `superseded`. Other skills may set these statuses; this skill never does.
- Starting implementation, worktrees or agents.
- Tracking progress during the build. Future skills may update the spec for this.

## Spec format

There is one file per spec: `specs/<slug>.md` in the target repo.

### Frontmatter

```yaml
---
id: todo-export            # equals the file name
title: Export todos as JSON
status: idea               # idea | draft | accepted | done | superseded
created: 2026-11-26
updated: 2026-11-26
accepted_by:               # required when accepted
accepted_on:
---
```

Fields for `done` and `superseded` (for example the verification fields and `superseded_by`) are defined by the skills that set those statuses. They are not part of this template.

### Status rules

| Status | Set by | Required content |
|---|---|---|
| `idea` | capture | Goal (1–3 sentences), Context, Open Questions. Other sections may be missing. |
| `draft` | refine | All six sections exist. Every behavior is an AC and every edge-case row points to one. Every AC has a `verify:` line or a `TBD:` line. Other TBDs and open questions are allowed. |
| `accepted` | refine, with the user's approval | All six sections are filled in. Every AC has a `verify:` line. No TBDs and no open questions. `accepted_by` and `accepted_on` are set. |
| `done` | a future verification skill | Out of scope here. |
| `superseded` | another skill, or set by hand | Out of scope here. |

### The six sections

| # | Section | Purpose for the agent |
|---|---|---|
| 1 | Goal & Non-Goals | Keeps the agent focused on the exact outcome and keeps it out of adjacent code. |
| 2 | Environment & Commands | The exact build, lint and test commands, so the agent can check its own work. |
| 3 | Interfaces & Data Contracts | Types, schemas, API signatures and CLI commands that the compiler and tests can check. |
| 4 | Behavior & Edge Cases | The happy path plus explicit error states and invariants. |
| 5 | Boundaries & Decision Log | Always / Ask First / Never rules, and architectural choices already made, with the reasons. |
| 6 | Verification Gate | The tests or checks that must pass before the work is complete. It lists them; it doesn't run them. |

### Design principles

- **Kept in the repo:** specs are versioned in the same commits as the code.
- **Predictable headings:** agents can find and load one section instead of the whole file.
- **Right-sized:** specify the shape of the system, its contracts and invariants, not line-by-line pseudocode. Shrink the prose once types and tests become the source of truth.
- **Testable "done":** acceptance criteria have IDs, a Given/When/Then description and a `verify:` command.
- **Explicit edge cases:** invalid input, failures and conflicts are written down so agents don't invent assumptions.
- **Settled decisions stay settled:** the decision log stops later sessions from reopening choices.
- **Two-way sync:** discoveries made during implementation flow back into the spec.

## Roadmap

Each release can be used on its own. Bump `.claude-plugin/plugin.json` `version` with each one.

### v0.1: Skeleton and templates ✅
- [x] `skills/spec/SKILL.md` with a description that triggers on the capture, refine and update phrases.
- [x] `skills/spec/template-idea.md`: frontmatter, Goal, Context and Open Questions.
- [x] `skills/spec/template-spec.md`: frontmatter and the six sections.
- [x] The status rules documented in SKILL.md.
- [x] **Done when:** the skill loads as `orca-kit:spec` and can write a correctly formatted `idea` file.

### v0.2: Capture and refine modes ✅
- [x] Capture writes an `idea` from the conversation with no questions asked.
- [x] Refine scans the repo (package.json, Makefile, pyproject, CI config) and prefills Environment & Commands.
- [x] Refine finds critical files and existing types and links to them instead of copying them.
- [x] Refine asks the user only about intent: goal, non-goals and decisions already made.
- [x] **Done when:** an `idea` can be refined into a `draft` with every section present.

### v0.3: Acceptance criteria and edge cases ✅
- [x] Each AC has an ID (`AC-n`), a Given/When/Then description and a `verify:` command or test.
- [x] A required edge-case table: input or condition → expected behavior → AC ID.
- [x] Verification Gate is built from the AC list.
- [x] **Done when:** a refined spec has no behavior without an AC, and no AC without a `verify:` line.

### v0.4: Guardrails
- Always / Ask First / Never lists with sensible defaults that the user can edit.
- Decision Log entries: decision, why, and alternatives rejected.
- Explicit Non-Goals.
- **Done when:** refine fills in all three, and accepting a spec requires them.

### v0.5: Checker
- `skills/spec/check` script, called through `${CLAUDE_PLUGIN_ROOT}`.
- Validates frontmatter and the rules for whatever status the spec claims.
- Enforces word budgets per section, to keep specs short.
- Refine runs the checker before asking the user to accept.
- **Done when:** a spec marked `accepted` that has open questions, TBDs or an AC with no `verify:` line fails the check.

### v0.6: Update mode
- Writes new edge cases, decisions and changed contracts back into an `accepted` spec.
- Trims prose that types and tests now cover, and bumps `updated`.
- Asks the user to accept again if the acceptance criteria change.
- **Done when:** a discovery made during implementation can be synced into the spec, and the spec still passes the checker.

### Alongside each release
- Sample specs in `skills/spec/examples/<status>/<slug>.md` (an `idea`, the `draft` refined from it, and later an `accepted`) to use as test fixtures.

## Decision log

| Decision | Why |
|---|---|
| One file per spec at `specs/<slug>.md` | Agents load only the spec they need. |
| Frontmatter `status` sets how much content is required | Makes the difference between a rough idea and an accepted spec explicit and checkable. |
| Only the user can accept a spec | Acceptance is a human decision. The skill records who accepted it and when. |
| Verification and `done` are out of scope | Keeps this skill focused. A separate verification skill will own the check and its report. |
| One skill with three modes | The modes share the template, the status rules and the checker. |
| Section headings in `template-spec.md` are the bare names from the six-sections table (`## Goal & Non-Goals`, …), with no numbers | Exact, predictable headings let agents find a section by name. |
| `template-spec.md` starts at `status: draft`; `template-idea.md` at `status: idea` | Each template matches the status of the mode that first writes it. |
| Capture derives the slug from the title and never overwrites an existing `specs/<slug>.md` | Capture asks no questions, so it can't confirm an overwrite; refine is the way to change an existing spec. |
| In a `draft`, unresolved questions become `TBD:` lines in the section they affect, not an extra `## Open Questions` heading | Keeps exactly the six template headings, and puts each gap next to the content it blocks. |
| Refine moves the idea's Context and Open Questions into the six sections instead of keeping them as headings | Nothing from the idea is lost, and the draft keeps the same predictable headings. |
| The repo scan's sources and linking rules live in `skills/spec/repo-scan.md` | Keeps SKILL.md short; refine loads the details only when it scans. |
| When CI and local scripts disagree, Environment & Commands lists the CI command first | CI is what must pass to merge. |
| Examples live at `skills/spec/examples/<status>/<slug>.md` | Each fixture keeps the real file name, so `id` equals the file name. |
| ACs live in Behavior & Edge Cases; the Verification Gate lists them by ID | A behavior and its AC are one statement, so they stay together; the gate stays a plain checklist; the spec keeps exactly the six template headings. |
| Every behavior in Behavior & Edge Cases is written as an AC, with no free prose about behavior | Makes "no behavior without an AC" checkable by reading the section. |
| AC format: `- **AC-n:** Given …, when …, then ….` with an indented `verify:` line, or `TBD:` in a draft | One predictable pattern that agents and the v0.5 checker can parse. A `TBD:` line follows the v0.2 convention. |
| AC IDs are stable: never renumbered, and a removed AC's ID is never reused | Tests and the Verification Gate refer to ACs by ID. |
| When the test doesn't exist yet, `verify:` names its future file and filters on a test name starting `AC-n:` | The check is exact before the code exists, and the colon keeps `AC-1` from matching `AC-10`. |
| The edge-case table's first cell starts with its category (`Invalid input:`, `Failure:`, `State conflict:`, …); a category that can't happen goes in a `Not applicable:` line under the table | Coverage of the required categories is visible at a glance, and every row still points to an AC. |
| Several edge-case rows may point to the same AC | Conditions with the same expected behavior need one check, not duplicate ACs. |
| Refine takes edge-case behavior from the conversation and the closest existing code first, and asks the user only about the rest; unknown answers become `TBD:` | Extends the v0.2 rule of asking only what the repo can't answer. |
| The Verification Gate copies each AC's `verify:` command exactly, then adds the whole-suite commands from Environment & Commands, without setup steps | A verification skill can load just the gate and run it. |
| A `draft` now requires every behavior to be an AC with a `verify:` or `TBD:` line | This is the v0.3 done criterion, applied at the status where refine leaves a spec. |
| AC, edge-case and gate rules live in `skills/spec/acceptance-criteria.md` | Keeps SKILL.md short; refine loads them when it writes those sections. |
