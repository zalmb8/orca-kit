# Update: syncing discoveries into an accepted spec

Update writes what was learned while building an `accepted` spec back into it: new edge cases, new settled decisions and changed contracts. It also trims prose that real types and tests now state. The spec stays `accepted` and keeps passing the checker. Read this file before changing an accepted spec.

Update only records what was learned. It never runs the Verification Gate, never judges whether the build meets the spec, never sets `done` or `superseded`, and never tracks build progress.

## 1. Gather discoveries

A discovery is a fact about the feature that the spec doesn't state yet, with a source you can point to. Collect them from:

| Source | What to look for |
|---|---|
| The conversation | Edge cases or failures hit while building, choices the user made ("pretty-print it"), contracts that changed, things the user said were wrong in the spec. |
| Changes since acceptance | Find the commit that accepted the spec: `git log -1 --format=%H -G '^accepted_on:' -- specs/<slug>.md`. Then read `git log --stat <sha>..HEAD` and `git diff <sha> -- <paths>` for every path the spec links to, the test files its `verify:` lines name, and their directories (which catches new files such as the command itself). Include uncommitted changes (`git status`, `git diff`). If the spec was never committed, use the changes the conversation shows. |
| New or changed tests | Test names and assertions, especially tests named `AC-n: …` that cover a case the edge-case table doesn't list. |
| New or changed types and schemas | Fields, signatures, CLI flags and output formats as the code now defines them. |
| Code paths found while building | Error handling, early returns and fallbacks in the linked code (`loadTodos()` returns no todos for a missing file) that decide an edge case. |

- **Never invent a discovery.** Each one comes from something the user said or a file or diff you read. Don't add edge cases you merely think of; that is refine's job, and adds behavior nobody has checked.
- **Ask when unclear.** If the code and the conversation disagree, or you can't tell whether a change was intended, ask the user. A discovery the user can't settle is left out and reported; it never becomes a `TBD:` line, because an `accepted` spec has none.
- **Code that contradicts an AC** is not a contract update. Don't change the AC to match the code: tell the user, and offer to change the AC (which needs re-acceptance, below) or leave the spec as it is. Whether the build is right is a verification question, not update's.
- **Already in the spec** means it isn't a discovery: an earlier update may have synced it.
- **Nothing to sync** means no change to the file: say so and don't bump `updated`.

## 2. Sort each change: information only, or re-acceptance

| Change | Needs re-acceptance |
|---|---|
| A new edge-case row pointing to an existing AC whose *then* already gives that behavior | No |
| A new Decision Log entry | No |
| Interfaces & Data Contracts brought in line with the code (new files, signatures, output details), where no AC or non-goal depends on what changed | No |
| Trimming prose that a type, schema or test now states (section 4) | No |
| Environment & Commands brought in line with the repo's commands | No, unless an AC's `verify:` line changes |
| Adding an AC (including one a new edge case needs), removing one, or changing one: its Given/When/Then or its `verify:` line | Yes |
| Changing or removing an existing edge-case row | Yes: it changes accepted behavior |
| Adding, removing or changing a Non-goal, or an Always, Ask First or Never rule | Yes |
| A contract change that an AC or non-goal depends on (a new flag when a non-goal rules flags out) | Yes, together with that AC or non-goal |
| Reversing an existing decision | The user's explicit word, as for any decision (section 3); no re-acceptance unless it also changes an AC or guardrail |

## 3. Write the information-only changes

Keep exactly the six template headings, in order. Don't add a changelog, history or "Updates" section: git history records what changed.

- **Edge cases.** Add a row to the edge-case table in the format of `acceptance-criteria.md`, starting with its category (`Invalid input:`, `Failure:`, `State conflict:`, `Empty:`, `Boundary:`) and pointing to the AC that covers it. Say where the behavior comes from when it isn't obvious ("`loadTodos()` returns no todos"). If no existing AC's *then* gives that behavior, the row needs a new AC: propose it, with the next unused ID and a `verify:` line, for re-acceptance. If a `Not applicable:` category now happens, move it from that line into a row.
- **Decisions.** Add an entry in the format of `guardrails.md` with the next unused ID (one higher than the highest ever used; never reuse a removed one) and `why:`, `rejected:` and `source:` lines. Only the user's choice or a choice the repo now settles counts; a choice you'd make yourself is a question. `source:` is `conversation` for a choice the user made while building, plus the repo paths that implement it, or just the paths for a repo choice. `rejected:` lists only alternatives that were really on the table; `none considered` needs the user's word. Never edit or delete an existing entry. If the user reverses one, rewrite that entry under its own ID with the new decision and why, and add the old choice to its `rejected:`.
- **Contracts.** Update Interfaces & Data Contracts so it links to the real files, symbols and signatures, following the linking rule in `repo-scan.md`: link by path and symbol, never copy fields or schemas.
- **Verification Gate.** Rebuild it from the ACs, as `acceptance-criteria.md` says, whenever an AC or the whole-suite commands change.
- **Frontmatter.** Bump `updated` to today. Keep `status: accepted`, `id` and `created`. Change `accepted_by` and `accepted_on` only on a re-acceptance yes.

## 4. Trim prose the code now states

Once a real type, schema or test states something, the spec should link to it instead of saying it again. Specs that stay short stay loaded.

- **Only what a file really states.** Open the file and confirm it states the same thing before trimming. A test file that is only planned doesn't count.
- **Replace, don't delete.** Swap the passage for a link by path and symbol, with a few words on why it matters, as `repo-scan.md` says: `` `test/commands/export.test.ts`: pins the exact output ``.
- **Where.** Interfaces & Data Contracts, and prose in Environment & Commands that a script or config now states. Never trim the ACs, the edge-case table, the Non-goals, the Always / Ask First / Never lists, the Decision Log or the Verification Gate.

## 5. Re-acceptance

An accepted spec was accepted as written. Before writing any change marked "Yes" in section 2:

1. **Show the change.** In one message, list each gated change with its before and after text (the AC, row, non-goal or rule), and the discovery behind it. Write the information-only changes in the same pass; they don't wait for the answer.
2. **Ask for an explicit yes**, per change if there are several. Never infer approval from silence, a thumbs-up on something else, or the user having asked for the update.
3. **On a yes**, write the change, rebuild the Verification Gate if an AC changed, and set `accepted_by` to the user's name or handle and `accepted_on` and `updated` to today.
4. **On a no**, leave that change out and keep every other update. If a new edge-case row depended on a declined AC, leave the row out too and report the discovery as unsynced.
5. **AC IDs stay stable.** A new AC takes the next unused ID. A removed AC's ID is never reused, and the ACs after it keep their numbers.

## 6. Check, then report

1. Keep the spec's text from before the update.
2. After writing, run `${CLAUDE_PLUGIN_ROOT}/skills/spec/check specs/<slug>.md`. It must print `ok (accepted)` and exit 0.
3. Fix what fails: formats, a missing `why:` or `source:` line, the gate, a section over its word budget (trim further, as section 4 allows). Never fix an error by deleting an AC, an edge-case row, a non-goal, a boundary or a decision, or by guessing an answer. Ask the user about anything the spec and repo can't answer.
4. If it still fails, restore the text from step 1, so an accepted spec is never left failing the check, and report why.
5. **Report** the path, each discovery and where it went (with its AC or D ID), what was trimmed, each gated change and the user's answer, any discovery left out and why, and the checker's result.

## Check before saving

- `status` is still `accepted`; `updated` is today; `accepted_by` and `accepted_on` changed only on a re-acceptance yes.
- Exactly the six template headings, in order, and no changelog.
- Every new edge-case row points to an AC whose *then* gives its behavior.
- Every new decision has the next unused ID and `why:`, `rejected:` and `source:` lines from the conversation or the repo.
- No AC, edge-case row, non-goal or Always / Ask First / Never rule changed without the user's explicit yes.
- No AC or decision ID was renumbered or reused.
- Every trim replaced prose with a link to a file that exists and states it.
- No `TBD:` lines and no open questions; the checker exits 0.
