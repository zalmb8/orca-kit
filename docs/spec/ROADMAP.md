# `orca-kit:spec`: design and roadmap

A skill that writes and maintains specifications for agentic development. A spec is a contract kept in the repo and versioned with the code. It connects what the user wants to what an agent builds, and it stays short so it doesn't flood the agent's context.

## Scope

The skill **writes and maintains specs**. It has three modes:

| Mode | Trigger phrases | Starts from | Leaves it at | What it does |
|---|---|---|---|---|
| **capture** | "spec this idea", "capture this", "jot down a spec for…" | nothing | `idea` | Writes `specs/<slug>.md` from what's already in the conversation: a goal, a little context and open questions. No interview and no repo scan. |
| **refine** | "refine the X spec", "flesh out X", "make X ready to build" | `idea` or `draft` | `draft`, or `accepted` once the user approves | Scans the repo for commands, critical files and types, asks the user about whatever the repo can't answer, and fills in all six sections. Sets `accepted` only on the user's explicit yes. |
| **update** | "update the spec with what we learned", "sync the spec", or before the final commit of a build | `accepted` | `accepted` | Writes discoveries made during implementation back into the spec and trims prose that types and tests now cover. If the acceptance criteria change, it asks the user to accept again. |

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
| `draft` | refine | All six sections exist. Every behavior is an AC and every edge-case row points to one. Every AC has a `verify:` line or a `TBD:` line. Goal & Non-Goals has a `Non-goals:` list; Interfaces & Data Contracts has `Existing:` and `New:` lists; Boundaries & Decision Log has `Always:`, `Ask First:` and `Never:` lists and a `Decision Log:`. The Verification Gate has one entry per AC copying its `verify:` or `TBD:` line, and its whole-suite commands come from Environment & Commands. Other TBDs and open questions are allowed. |
| `accepted` | refine, with the user's approval | All six sections are filled in. Every AC has a `verify:` line. The edge-case table covers invalid input, failure and state conflict, or says why one can't happen. `Existing:` and `New:` have at least one item between them. The Non-goals and the Always, Ask First and Never lists each have at least one item, and the Decision Log has at least one entry with `why:`, `rejected:` and `source:` lines; none of them has a `TBD:` line. No TBDs and no open questions anywhere. `accepted_by` and `accepted_on` are set. |
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

### v0.4: Guardrails ✅
- [x] Always / Ask First / Never lists with sensible defaults that the user can edit.
- [x] Decision Log entries: decision, why, and alternatives rejected.
- [x] Explicit Non-Goals.
- [x] **Done when:** refine fills in all three, and accepting a spec requires them.

### v0.5: Checker ✅
- [x] `skills/spec/check` script, called through `${CLAUDE_PLUGIN_ROOT}`.
- [x] Validates frontmatter and the rules for whatever status the spec claims.
- [x] Enforces word budgets per section, to keep specs short.
- [x] Refine runs the checker before asking the user to accept.
- [x] Failing fixtures in `skills/spec/tests/fixtures/` and a stdlib test runner: `python3 -m unittest discover -s skills/spec/tests`.
- [x] **Done when:** a spec marked `accepted` that has open questions, TBDs or an AC with no `verify:` line fails the check.

### v0.6: Update mode ✅
- [x] Writes new edge cases, decisions and changed contracts back into an `accepted` spec.
- [x] Trims prose that types and tests now cover, and bumps `updated`.
- [x] Asks the user to accept again if the acceptance criteria change.
- [x] **Done when:** a discovery made during implementation can be synced into the spec, and the spec still passes the checker.

### v0.7: Closing the gaps with the spec concepts ✅
A review against the foundational concepts for agentic specs found the shape right but several properties described in prose instead of checked.
- [x] The checker enforces what was mechanical but left to refine's checklists: the Verification Gate matching the ACs (`gate.matches-acs`), whole-suite commands coming from Environment & Commands (`gate.suite`), edge-case category coverage (`edge.categories`), and a warning when no non-goal names a path (`nongoal.path`).
- [x] Concrete examples: an optional `example:` line under an AC (`` `<input>` → <expected output> ``), required by refine whenever the output is exact and known, and asserted literally by the AC's test.
- [x] Typed contracts: Interfaces & Data Contracts splits into `Existing:` (`` `path` (`Symbol`) ``) and `New:` (contracts in code) lists; update moves `New:` items to `Existing:` once their files land.
- [x] `check --repo <root>`: `Existing:` paths and symbols exist (`repo.paths`), named scripts, make targets and just recipes exist (`repo.commands`), and an accepted spec isn't older than the code it links to (`repo.stale`). Warnings only. A `verify:` runner missing from Environment & Commands warns without `--repo` (`verify.runner`).
- [x] Two-way sync: update runs before the final commit of a build, the spec is committed with the code, and every spec's `Always:` list carries that rule. Update handles acceptance and code in one commit.
- [x] Repo-wide boundaries live once: refine reads the repo's `CLAUDE.md` / `AGENTS.md`, drops `repo` defaults already stated there, and can offer to move them there.
- [x] `check --section "<heading>"` prints one section, so agents load only what they need.
- [x] **Done when:** the examples pass with no warnings, including `--repo` against a matching repo, and a failing fixture exists for each new rule.

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
| Non-goal, boundary and Decision Log rules live in `skills/spec/guardrails.md` | Same pattern as `repo-scan.md` and `acceptance-criteria.md`; refine loads them when it writes those sections. |
| The three guardrails sit under labelled lists (`Non-goals:`, `Always:`, `Ask First:`, `Never:`, `Decision Log:`) inside their sections, not under extra headings | Keeps exactly the six template headings, matches the existing `Non-goals:` and `Per acceptance criterion:` labels, and gives the v0.5 checker fixed labels to look for. |
| Refine adapts a fixed set of default boundaries to the repo's real commands and paths, and the user only confirms or changes them | The user never writes boundaries from scratch, and every rule names something real. A default with nothing to adapt to is dropped and reported. |
| The repo scan also finds protected and generated files (secrets, build output, lockfiles, config, migrations, `CODEOWNERS`) | The Never and Ask First defaults need real paths to adapt to. |
| Decision Log format: `- **D-n:** <decision>.` with indented `why:`, `rejected:` and `source:` lines | Mirrors the AC pattern, so agents and the checker can parse it. `source:` shows each decision came from the interview or the repo. |
| Decision IDs are stable, like AC IDs | Later sessions and update mode can refer to a decision by ID. |
| A Decision Log entry is only what the user decided or what the repo already settled; a choice refine would make itself becomes an interview question | Settled decisions must really be settled, or later sessions will rightly reopen them. |
| `rejected:` lists only alternatives that were on the table; `none considered` needs the user's word | Stops refine from inventing straw-man alternatives. |
| At least one non-goal names adjacent code by path | A vague non-goal doesn't stop an agent from refactoring nearby code. |
| A `draft` must already have all three guardrails, and `accepted` requires them filled in with no `TBD:` lines | This is the v0.4 done criterion: refine always writes them, and acceptance depends on them. |
| If the user skips the boundaries question, the adapted defaults stay, and accepting the spec confirms them | The interview stays one message, and acceptance is still the user's explicit decision. |
| Examples gain `examples/accepted/export-todos-as-json.md`, refined again from the draft | A fixture that meets every `accepted` rule, for the v0.5 checker. |
| The checker is one Python 3 script using only the standard library, with no file extension | No install step and no dependencies; it runs anywhere `python3` does, and `check` reads like a command. |
| The frontmatter parser accepts only flat `key: value` lines with plain or quoted single-line values, plus blank and `#` comment lines; anything else is a parse error (exit 2) | The frontmatter is deliberately simple, so a small strict parser is enough, and anything it can't read for certain is reported rather than guessed. |
| Every status is checked against the same seven frontmatter fields; unknown fields are allowed | Future skills add their own fields for `done` and `superseded`, and the checker mustn't reject them. |
| `done` and `superseded` are checked only against this skill's `accepted` rules, including `accepted_by` and `accepted_on` | Both statuses come after `accepted`, and their own rules belong to the skills that set them. |
| `idea` and `draft` fail if `accepted_by` or `accepted_on` is set | Only the user's yes fills them in, so a value at a lower status is a mistake. |
| `accepted` is checked against every `draft` rule as well as its own, including the edge-case table and the AC format (ID and Given/When/Then) from v0.3 | An accepted spec is a finished draft; the AC format is what makes "every behavior is an AC" checkable. |
| The checker enforces the status rules table, the v0.3 and v0.4 rules it names, and, from v0.7, every checklist rule that is mechanical: the gate matching the ACs, edge-case category coverage, a non-goal naming a path. Rules that stay judgement calls (whether an AC needs an `example:`) remain in refine's checklists. Earlier, all three were left to the checklists | Those three were never judgement calls: a string comparison, a prefix lookup and a path pattern. The checker still never fails a spec on a real judgement call; heuristics are warnings. |
| A TBD is the word `TBD` and an open question is a `?` ending a word, or an `Open Questions` heading or label, anywhere outside code spans and fences | Simple to find and explain; code may legitimately contain both. |
| Word budgets per section live in one table at the top of `check`, set at about twice the accepted example's size | One place to tune them, with room for larger features. |
| Word budgets warn at `idea`, `draft`, `done` and `superseded`, and fail at `accepted` | An accepted spec is what an agent loads, so it must stay short; earlier statuses are still being written, and this skill doesn't edit later ones. |
| `check --as accepted` checks a draft against the `accepted` rules, skipping `accepted_by` and `accepted_on` | Refine can find out whether a spec is ready before asking the user to accept it, without faking the acceptance record. |
| Refine fixes the errors the spec and repo answer, turns the rest into interview questions, asks for acceptance only once `check --as accepted` exits 0, and checks again after the yes | The user is never asked to accept a spec that fails the check, and refine never guesses an answer to make it pass. |
| Output is one line per problem, `<file>:<line>: <severity> [<rule>] <section>: <problem>. Fix: <what to do>.`; exit 0 pass, 1 rule failure, 2 usage or parse error | Editors and agents can jump to the line, and the rule ID maps back to the status rules table (`check --rules`). |
| Failing fixtures live in `skills/spec/tests/fixtures/<case>/<id>.md`, beside the passing examples | Each fixture keeps the real file name, as the examples do, and each breaks one rule. |
| Update runs only on an `accepted` spec; on `idea` or `draft` it points to refine, and it leaves `done` and `superseded` alone | Refine owns specs that aren't accepted yet, and this skill never touches the statuses other skills set. |
| Update gathers discoveries from the conversation and from `git log` and `git diff` since the commit that accepted the spec, on the files the spec links to, the tests its `verify:` lines name, and their directories | Those are the places a build changes, and the directories catch new files such as the command itself. Every discovery has a source. |
| A discovery that stays unclear after asking is left out and reported, never written as `TBD:` | An `accepted` spec has no TBDs, and update never guesses. |
| Code that contradicts an AC is reported to the user, not synced into the AC | Changing the AC would need re-acceptance, and whether the build is right is a verification question. |
| Re-acceptance is needed to add, remove or change an AC (its Given/When/Then or its `verify:` line), to change or remove an existing edge-case row, and to change the Non-goals or the Always, Ask First or Never lists | These are what the user accepted. A `verify:` line is how the AC is checked, and an edge-case row states accepted behavior. |
| Adding a decision, an edge-case row under an AC whose *then* already covers it, contract details that match the code, and trims need no re-acceptance | They only add information or replace prose with a link; the accepted behavior stays the same. |
| A gated change is shown before and after and needs the user's explicit yes; a yes refreshes `accepted_by` and `accepted_on`, a no drops only that change | Acceptance stays the user's decision, and declining one change doesn't block the rest of the sync. |
| Existing Decision Log entries are never edited by update, except to rewrite one under its own ID when the user reverses it, with the old choice added to `rejected:` | Settled decisions stay settled, and IDs stay stable for later references. |
| Update's `source:` for a choice the user made while building is `conversation`, followed by the paths that implement it | It distinguishes a build-time choice from the refine interview and still points to the code. |
| Trims apply only to Interfaces & Data Contracts and to Environment & Commands prose, and only once the linked file exists and states the same thing; ACs, the edge-case table, Non-goals, guardrails, the Decision Log and the Verification Gate are never trimmed | The spec shrinks only where the code has become the source of truth, and the contract parts stay intact. |
| Update adds no changelog section | Git history records what changed; a changelog would break the six-heading rule and grow every spec. |
| Update runs the checker after every update; if the spec can't be made to pass, it restores the spec's text from before the update | An accepted spec is never left failing the check. |
| Update's rules live in `skills/spec/update.md` | Same pattern as the other guidance files; update loads it when it runs. |
| The updated example lives at `examples/updated/export-todos-as-json.md`, an exception to `examples/<status>/` | Its status is `accepted`, and `accepted/` already holds the spec it was updated from; the file keeps its real name. |
| The updated example's test compares it with the accepted example: same frontmatter except `updated`, same ACs and guardrail lists, one new edge-case row under an existing AC, one new decision with the next ID, one trimmed passage | This proves the v0.6 done criterion and the re-acceptance split, not just that the file passes the checker. The checker itself is unchanged. |
| Rules that aren't always errors get a per-status severity in one `RULE_SEVERITY` table in `check`; `edge.categories` follows the word budgets (warn before `accepted`, fail at it) and heuristics are warnings everywhere | One place to see and tune how strict each rule is, generalising the v0.5 budget table. |
| `gate.matches-acs` compares each gate entry with its AC's `verify:` line character for character, and skips when the ACs themselves don't parse | The gate is a copy, so any difference is drift; skipping avoids reporting one broken AC twice. |
| An AC's `example:` line is `` `<input>` → <expected> `` with a code span before the arrow; the checker checks the format, refine decides when one is required | Format is mechanical; whether output is "exact and known" is a judgement. |
| Adding, changing or removing an `example:` line needs re-acceptance | An example pins accepted behavior as much as the *then* does. |
| Interfaces & Data Contracts has `Existing:` and `New:` labelled lists, like the guardrails; a section that is only `TBD.` skips the label rules | Gives the checker and `--repo` fixed places to look, while a draft can still leave the section open. |
| `New:` items must contain code (a span or fenced block) | The checker can't judge whether a contract is typed, but it can refuse one stated only in prose. |
| `--repo` rules are warnings, and run only when the flag is given | The checker stays runnable on a spec alone (in CI for this plugin, or before the code exists), and a repo-specific quirk never blocks acceptance. |
| `repo.stale` compares commits, not dates: any commit after the spec's last commit that touches its linked files; it skips when the spec has uncommitted changes or git isn't there | Dates are only day-precise; an uncommitted spec means a sync is in progress. |
| `repo.stale` runs only at `accepted` | A draft isn't built against yet, and `done`/`superseded` belong to other skills. |
| Update runs before the final commit of a build, and the spec is committed with the code; the rule sits in every spec's `Always:` list | The building agent reads the spec, not necessarily this skill, so the rule has to travel with the spec. |
| When the accepting commit also changes code, update diffs from its parent | Acceptance and the first build commit can be one commit once specs are committed with code. |
| Defaults are marked `repo` or `spec` scope; `repo` ones already stated in `CLAUDE.md`/`AGENTS.md` are dropped from the spec, with one `Follow the repo rules` item instead; `spec` ones always stay | Repo-wide rules stop being copied into every spec, and every list keeps at least one item. |
| Refine edits the repo's `CLAUDE.md` only to append an `## Agent boundaries` section, and only on the user's yes | A boundary file Claude Code already loads beats a new file type in `specs/`, which `check specs/*.md` would also trip over. |
| `check --section` lives in the checker, not a separate script | It reuses the same parser, so a section is found exactly as the checker finds it. |
| Specs written before v0.7 are brought into the format by update as an information-only change, except the new sync rule, which is shown to the user | The content stays the same; only the new boundary is something the user didn't accept. |
