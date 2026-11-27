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

- **capture**: write a new spec from what is already in the conversation, using `${CLAUDE_PLUGIN_ROOT}/skills/spec/template-idea.md`. Fill in a goal, a little context and open questions. Do not interview the user or scan the repo.
- **refine**: rewrite the spec using `${CLAUDE_PLUGIN_ROOT}/skills/spec/template-spec.md` so all six sections exist, keeping what the idea already said. Ask the user about anything the conversation and repo can't answer. Set `accepted` only when the user explicitly approves.
- **update**: write discoveries made during implementation back into an `accepted` spec and bump `updated`. If the acceptance criteria change, ask the user to accept again.

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
| `draft` | refine | All six sections exist. TBDs and open questions are allowed. |
| `accepted` | refine, with the user's approval | All six sections are filled in. Every AC has a `verify:` line. No TBDs and no open questions. `accepted_by` and `accepted_on` are set. |

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
