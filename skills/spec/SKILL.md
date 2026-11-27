---
name: spec
description: Writes and maintains specifications kept in the repo at specs/<slug>.md, with a status that moves from idea to draft to accepted. Use to capture an idea ("spec this idea", "capture this", "jot down a spec for…"), to refine one into a buildable spec ("refine the X spec", "flesh out X", "make X ready to build"), or to sync discoveries back into an accepted spec ("update the spec with what we learned", "sync the spec").
---

# spec

Writes and maintains specs: short contracts kept in the target repo and versioned with the code, which connect what the user wants to what an agent builds. Done means the spec file exists at `specs/<slug>.md`, its frontmatter is valid, and its content meets the rules for the status it claims.

## Modes

Pick the mode from what the user asked for.

| Mode | Trigger phrases | Starts from | Leaves it at |
|---|---|---|---|
| **capture** | "spec this idea", "capture this", "jot down a spec for…" | nothing | `idea` |
| **refine** | "refine the X spec", "flesh out X", "make X ready to build" | `idea` or `draft` | `draft`, or `accepted` on the user's explicit yes |
| **update** | "update the spec with what we learned", "sync the spec" | `accepted` | `accepted` |

The target repo is the repo being worked on (its git root), not this plugin.

## Capture

Write a new `idea` from what is already in the conversation. Ask no questions and do not scan the repo.

1. **Title and slug.** Take a short title from the conversation. Derive the slug from it: lowercase, replace every run of characters other than `a-z` and `0-9` with one hyphen, trim leading and trailing hyphens, and drop a leading `a`, `an` or `the`. For example, "Export todos as JSON" becomes `export-todos-as-json`.
2. **Never overwrite.** If `specs/<slug>.md` already exists, stop. Do not write anything. Tell the user the path and the existing spec's `status`, and suggest refining it instead.
3. **Write** `specs/<slug>.md` from `${CLAUDE_PLUGIN_ROOT}/skills/spec/template-idea.md`. Set `id` to the slug, `status: idea`, and `created` and `updated` to today.
   - **Goal:** 1–3 sentences on the outcome the user wants, in their terms.
   - **Context:** only what the conversation actually said: the problem, who it affects, and any code, files or decisions it mentioned.
   - **Open Questions:** everything the conversation left undecided or unknown. Record it as a question; never guess an answer. There is always at least one.
4. **Report** the path and list the open questions. Point out that refine is the next step.

## Refine

Turn an `idea` or `draft` into a `draft` with all six sections. Scan the repo first, then ask the user only what the repo can't answer.

1. **Find the spec.** Match the user's words to a file in `specs/` by slug, `id` or `title`. If none matches, say so and list the specs that exist. If the spec is `accepted`, it belongs to update mode; if it is `done` or `superseded`, leave it alone and say so.
2. **Scan the repo** as described in `${CLAUDE_PLUGIN_ROOT}/skills/spec/repo-scan.md`:
   - the exact build, lint and test commands, from package.json scripts, Makefile, pyproject.toml and CI config such as `.github/workflows/`;
   - the critical files and the existing types or schemas relevant to the goal;
   - the protected and generated files: secrets, build output, lockfiles, config, migrations.
   Link to files by path. Never copy their contents into the spec.
3. **List the behaviors and edge cases** as described in `${CLAUDE_PLUGIN_ROOT}/skills/spec/acceptance-criteria.md`: the happy path, then invalid input, failure states (network, IO, corrupt data) and state conflicts, wherever they apply. Take each expected behavior from the conversation, the idea, and how the closest existing code and tests already handle the same case.
4. **Draft the guardrails** as described in `${CLAUDE_PLUGIN_ROOT}/skills/spec/guardrails.md`: propose the non-goals, adapt the default Always / Ask First / Never lists to the commands and paths the scan found, and collect the decisions the conversation made and the choices the repo already settled.
5. **Interview the user about intent only.** In one message, ask only what the spec, the conversation and the scan leave unanswered, and only about:
   - the **goal**: the exact outcome, if the idea is vague or ambiguous;
   - the **non-goals**: show the proposed list and ask the user to confirm or change it;
   - **decisions**: choices that are still open, as concrete options, and why a settled choice was made if no one said;
   - the **boundaries**: show the adapted Always / Ask First / Never lists and ask the user to confirm or change them, never to write them;
   - **expected behavior for edge cases** that the repo and the conversation can't answer, as concrete choices.
   Never ask about commands, files, types or anything else the scan found. Resolve the idea's open questions from the scan where it answers them, and ask about the rest only if they are about intent. If the user doesn't know or skips a question, record it as `TBD` (see below) rather than guessing.
6. **Write the draft.** Rewrite the file in the shape of `${CLAUDE_PLUGIN_ROOT}/skills/spec/template-spec.md`, with all six headings exactly as in the template, in order, and no other `##` headings. Keep everything the idea said: move each piece into the section it informs, and drop nothing.
   - **Goal & Non-Goals:** the idea's Goal, sharpened by the user's answers, then its Context as a short paragraph on why, then the `Non-goals:` list the user confirmed, in the format of `guardrails.md`.
   - **Environment & Commands:** the exact commands the scan found, each with the file it came from.
   - **Interfaces & Data Contracts:** links to the existing types, schemas and critical files, plus the new contracts the goal implies, described in terms of those types.
   - **Behavior & Edge Cases:** every behavior as an acceptance criterion, then the edge-case table, in the format of `acceptance-criteria.md`. Every AC has an ID (`AC-1`, `AC-2`, …), a Given/When/Then description and a `verify:` line naming the exact command or test that checks it. Every edge-case row points to an AC. No behavior is written without an AC.
   - **Boundaries & Decision Log:** the `Always:`, `Ask First:` and `Never:` lists with the user's changes, then the `Decision Log:`, in the format of `guardrails.md`. Each entry has an ID (`D-1`, `D-2`, …), the decision, and `why:`, `rejected:` and `source:` lines. Record only what the user decided and what the repo already settled; never invent a decision.
   - **Verification Gate:** built from the AC list: one entry per AC with its `verify:` command, then the whole-suite commands from Environment & Commands. It lists the checks; it never runs them.

   **TBDs and open questions.** Anything still unresolved goes in the section it affects, as a line starting `TBD:` (for example `TBD: should completed todos be included?`). A section with nothing known yet holds just `TBD.` These are allowed at `draft`. An AC whose check isn't known yet has a `TBD:` line in place of its `verify:` line.

   Before saving, run the checklists at the end of `acceptance-criteria.md` and `guardrails.md`.
7. **Set the frontmatter.** `status: draft`. Keep `id` and `created`; set `updated` to today. Leave `accepted_by` and `accepted_on` empty.
8. **Report** the path, the commands and files found, the number of ACs and decisions, any default boundary dropped because it doesn't apply, and every remaining `TBD` (including each AC still without a `verify:` line).

Refine leaves the spec at `draft`. Move it to `accepted` only if the user explicitly says they accept it and the spec meets every `accepted` rule below, including filled-in Non-goals, boundaries and Decision Log; otherwise say what is missing and keep it at `draft`. On accepting, set `status: accepted`, `accepted_by` to the user's name or handle, and `accepted_on` and `updated` to today.

## Update

Write discoveries made during implementation back into an `accepted` spec and bump `updated`. If the acceptance criteria change, ask the user to accept again.

## Spec files

- One file per spec: `specs/<slug>.md` in the target repo (the repo being worked on, not this plugin). Create `specs/` if it is missing.
- The slug is short, lowercase and hyphenated, and `id` equals it.
- Never write more than one spec per file, and never split one spec across files.
- Keep section headings exactly as in the templates, so agents can load one section instead of the whole file.

## Frontmatter

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

- Dates are `YYYY-MM-DD`. Set `created` and `updated` to today on capture; bump `updated` on every later change.
- Leave `accepted_by` and `accepted_on` empty until the user accepts the spec.

## Status rules

| Status | Set by | Required content |
|---|---|---|
| `idea` | capture | Goal (1–3 sentences), Context, Open Questions. Other sections may be missing. |
| `draft` | refine | All six sections exist. Every behavior is an AC and every edge-case row points to one. Every AC has a `verify:` line or a `TBD:` line. Goal & Non-Goals has a `Non-goals:` list; Boundaries & Decision Log has `Always:`, `Ask First:` and `Never:` lists and a `Decision Log:`. Other TBDs and open questions are allowed. |
| `accepted` | refine, with the user's approval | All six sections are filled in. Every behavior is an AC and every AC has a `verify:` line. The Non-goals and the Always, Ask First and Never lists each have at least one item, and the Decision Log has at least one entry with `why:`, `rejected:` and `source:` lines; none of them has a `TBD:` line. No TBDs and no open questions anywhere. `accepted_by` and `accepted_on` are set. |

- **Only the user can accept a spec.** Set `accepted` only after the user's explicit yes, and record who accepted it (`accepted_by`) and when (`accepted_on`). Never infer approval.
- **This skill never sets `done` or `superseded`.** Other skills, or the user by hand, set those statuses. Leave such specs alone.
- Never move a spec to a status whose required content is missing. If it doesn't qualify, leave it at the lower status and say what is missing.

## Out of scope

- Running verification or writing a verification report.
- Starting implementation, worktrees or agents.
- Tracking build progress.

## Bundled files

- `${CLAUDE_PLUGIN_ROOT}/skills/spec/template-idea.md`: template for an `idea`.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec/template-spec.md`: template for a `draft` or `accepted` spec, with the six sections.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec/repo-scan.md`: where refine looks for commands, critical files and types.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec/acceptance-criteria.md`: the AC format, the edge-case table and how refine builds the Verification Gate.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec/guardrails.md`: the Non-goals, the default Always / Ask First / Never lists and how refine adapts them, and the Decision Log format.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec/examples/`: an `idea`, the `draft` that refining it produces, and the `accepted` spec a second refine produces from that draft.
