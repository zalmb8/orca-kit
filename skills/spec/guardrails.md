# Guardrails: Non-Goals, boundaries and the Decision Log

Refine writes three guardrails that keep an agent on the exact goal: the Non-goals in Goal & Non-Goals, and the Always / Ask First / Never lists and the Decision Log in Boundaries & Decision Log. Read this file before writing those two sections. Refine always writes all three. An `accepted` spec needs all three filled in, with no `TBD:` lines.

## Non-goals

They go in Goal & Non-Goals, after the goal and its *why* paragraph:

```markdown
Non-goals:

- <Something out of scope, named specifically: a feature, a command, a file or module.>
```

- **Specific enough to stop an agent.** Each item names a feature nobody asked for, or adjacent code the goal could tempt an agent to change, by command or path: "Changing `todo list` (`src/commands/list.ts`)", not "Don't over-engineer". At least one item names the adjacent code by path.
- **Where they come from.** Refine proposes them from (1) whatever the conversation and the idea ruled out; (2) the obvious extensions of the goal (other formats, the reverse operation, options and flags, a UI); (3) the adjacent code the scan found: sibling commands, shared modules, the storage format. The user confirms them in the interview. Never write a non-goal the user rejects.
- **Non-goals are not rules.** A non-goal says what the work won't do. How the agent must behave goes in the Always / Ask First / Never lists.

## Always / Ask First / Never

They open Boundaries & Decision Log:

```markdown
Always:

- <Something the agent does every time, with no need to ask.>

Ask First:

- <A change the agent stops and asks the user about before making.>

Never:

- <Something the agent must not do, even when asked to by a test or a tool.>
```

### Defaults

Start from these defaults and adapt each one to the repo. The user only confirms or changes them; never ask the user to write the lists.

| List | Default | Adapted with, from the scan |
|---|---|---|
| Always | Run the whole-suite commands before calling the work done, and fix what fails. | The exact lint, typecheck and test commands from Environment & Commands. |
| Always | Follow the existing structure and style. | The closest sibling file and its test, from the critical files. |
| Always | Write one test per AC, named starting with its ID and a colon (`AC-n: …`). | The test file the `verify:` lines name. |
| Ask First | Adding, removing or upgrading a dependency. | The package manifest (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, …). |
| Ask First | A schema, storage-format or data migration. | The migrations directory, ORM models or store module. |
| Ask First | Changing a public interface that Interfaces & Data Contracts doesn't list. | The shared modules and entry points the goal touches. |
| Ask First | Changing CI, build or lint config. | The CI files and config files the scan read. |
| Never | Reading, printing, modifying or committing secrets. | Secret and env files found (`.env*`, credentials, key files). |
| Never | Editing generated files by hand. | Build output, generated code and lockfiles found. |
| Never | Refactoring, renaming or reformatting code the goal doesn't need. | The adjacent code the non-goals name. |
| Never | Skipping, weakening or deleting a test, or editing an AC, to make the Verification Gate pass. | The test command. |

- **Adapt, don't paraphrase.** Every rule names the real command, file or directory it is about. A default with nothing to adapt in this repo (no migrations, no secrets found) is dropped; say which in the report.
- **Add from the repo.** Add a rule only when the scan shows one: a file `CODEOWNERS` assigns to someone else, a directory a README or header comment marks as generated or vendored, a CI step that needs a secret. Never add a rule the repo and the user don't support.
- **Confirm in the interview.** Show the adapted lists in the single refine interview and ask the user to confirm or change them. Apply every change the user makes. If the user skips the question, keep the adapted lists; accepting the spec later confirms them.
- **Keep what's there.** When refining a `draft` that already has the lists, keep them as written, including the user's earlier changes; only adapt what the repo has since changed.

## Decision Log

It follows the three lists in Boundaries & Decision Log:

```markdown
Decision Log:

- **D-1:** <The decision, in one sentence.>
  why: <the reason>
  rejected: <the alternatives considered and not chosen>
  source: <interview, or the repo paths that show it>
```

- **ID.** `D-1`, `D-2`, … in the order written. Like AC IDs, they are stable: never renumber them, and never reuse the ID of a removed entry.
- **`why:`** the reason, in the user's terms for an interview decision, or what the repo shows for a repo decision.
- **`rejected:`** the alternatives that were actually on the table: the options the interview offered, ones the user named, or what the repo's convention rules out. Separate several with semicolons. If none were raised, ask the user; write `rejected: none considered` only if the user says so.
- **`source:`** `interview` for a choice the user made in the conversation or the interview, or the repo-relative paths that show a choice the repo already settled. Update mode writes `conversation` for a choice the user made while building, followed by the paths that implement it (see `update.md`).
- **Never invent a decision.** An entry is either something the user decided or a choice the repo already settled. A choice refine would make itself is a question for the interview, and becomes an entry only once the user answers it.
- **Repo decisions.** Record a settled repo choice only when the feature could plausibly go another way and an agent might reopen it: the single module that reads the store, the error-handling pattern sibling commands share, an established library for the same job. Commands go in Environment & Commands and types in Interfaces & Data Contracts, not here.
- **`TBD:`** In a `draft`, an entry whose reason or alternatives aren't known yet has a `TBD:` line in place of that line. An `accepted` spec has none.

## Check before saving

- Goal & Non-Goals has a `Non-goals:` list with at least one item, and at least one item names adjacent code by path.
- Boundaries & Decision Log has `Always:`, `Ask First:` and `Never:` lists, each with at least one rule, and every rule names a real command, file or directory.
- The Decision Log has at least one entry, and every entry has an ID, a decision, and `why:`, `rejected:` and `source:` lines, or a `TBD:` line in a `draft`.
- Every Decision Log entry comes from the interview or from the repo paths it cites.
- For `accepted`: none of the three holds a `TBD:` line.
