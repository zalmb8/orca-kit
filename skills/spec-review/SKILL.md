---
name: spec-review
description: Reviews a spec written by orca-kit:spec (specs/<slug>.md, normally a draft about to be accepted) before code is written, pairing deterministic hard gates with typed findings from narrow reviewers, and keeping product decisions with the user. Use when the user says "review the X spec", "is X ready to build", "check X before we accept it" or "run spec review", or to run the hard gates on a spec (spec checker, secret and PII scan, block parsing, ticket traceability, length ceiling), tier its risk (auth, migrations, data models, billing, public or breaking API changes) and require a human sign-off for a high-risk spec, run the bounded revision loop that hands fix blockers back to the author until the spec converges or the loop stops, pause to ask the user one concrete choice at a time (a decision finding, a stopped loop, a high-risk sign-off, a spec that fails the skim test) and resume with their answers, render the review summary the user reads before accepting, validate a reviewer's findings JSON or a review record, or count findings by rule across a repo's reviews (findings --stats) and propose graduating a repeated, mechanical rule into the spec checker or the gate config.
---

# spec-review

Reviews a spec before code is written: a one-page spec is cheaper to check than a thousand lines of generated diff. It reports findings; it never writes, edits or accepts the spec. Done means the hard gates and the risk step have run, the user has every result with its lines, every question the review raised has been asked and the user's answers are recorded, a high-risk spec has the user's own sign-off or is reported as not passing, every finding the review uses has passed the findings validator, and the user has the review summary.

## Status (v0.7)

Available: the hard gates (`gate`), risk tiering with the human sign-off (`gate --risk`, the review record and its validator `record`), the findings format with its validator (`findings`), the five advisory reviewers with their merge (`findings --merge`), the bounded revision loop with its verdict script (`converge`), the human-in-the-loop pauses (`pause`), resuming after answers, the review summary (`summary`), and graduating repeated findings (`findings --stats`). Every release in `${CLAUDE_PLUGIN_ROOT}/docs/spec-review/ROADMAP.md` is built.

When the user asks to review a spec, the whole review runs end to end:

1. Run the [review](#running-a-review): the hard gates, the five reviewers, the merge, the review record and the risk step, in that order.
2. After every pass, run `converge` and then `pause` ([Pauses](#pauses-and-the-summary)).
3. When `pause` prints questions, ask them, record each answer, and run `converge` and `pause` again on the same pass.
4. When the verdict is `continue`, run the next pass of the [revision loop](#revision-loop), handing the author the fix blockers and the user's answers.
5. When `pause` says to render the summary, run `summary` and show it.

Never answer a question yourself, and never say which option you would pick. A review never reports a spec as ready to build: it reports what the gates, the risk step, the reviewers, the loop and the user's answers came to. [Graduating rules](#graduating-rules) is a separate step, run when the user asks which findings keep coming back, not part of a review.

## Core rules

Every release keeps these.

1. **Only deterministic checks are hard gates.** The same spec always gets the same pass/fail. An LLM finding never fails a gate.
2. **AI escalates, a human decides.** For risky domains, block only to require a named human's sign-off; never make the final call.
3. **Narrow reviewers in isolated contexts.** One rubric per reviewer, only the context that rubric needs, never the author's context or reasoning.
4. **Typed findings.** Every finding has a severity (`blocker | nit`, fixed by its rule), a location, a concrete question and a suggested fix. Only blockers loop; nits become comments.
5. **Bounded loops.** At most 3 author–reviewer passes. Open blockers must strictly decrease each pass; if they don't, stop and ask a human.
6. **No spec bloat.** A revision may not push the spec past its length ceiling. Fixing a blocker by adding paragraphs is a smell, not a fix.
7. **Humans own the why, agents own the how.** Two valid readings of business logic are a question for the user, never a guess.
8. **Graduate repeated findings.** A structural mistake a reviewer keeps catching should become a deterministic rule.

## Hard gates

`${CLAUDE_PLUGIN_ROOT}/skills/spec-review/gate [--repo ROOT] specs/<slug>.md` runs every gate and needs only `python3`. Every gate is deterministic: the same spec and settings always get the same result, so a gate failure is a fact, not an opinion.

| Gate | Fails when |
|---|---|
| `check` | `${CLAUDE_PLUGIN_ROOT}/skills/spec/check --as accepted` reports an error; its rules keep their names (`check.no-tbd`, …) |
| `secrets` | The file holds a credential (private key, cloud or API token, JWT, password in a URL or assignment, a repo pattern) or personal data (email, SSN, card number, phone number); values are masked in the output |
| `blocks` | A fenced `json`, `yaml`/`yml` or `openapi` block doesn't parse, an OpenAPI document lacks its required fields, or a block naming a local `"$schema"` file doesn't match it |
| `trace` | The repo sets `ticket_pattern` and the spec names no matching ticket outside code |
| `length` | The body is over the word ceiling (`max_words`, default 2000) |

- It prints problems in the spec checker's format, `<file>:<line>: <error|warning> [<gate>.<rule>] <section>: <problem>. Fix: <what to do>.`, then `<file>: gates ok: …` or `<file>: gates failed: <gate> (<n>), …; passed: …`.
- It exits 0 when every gate passes, 1 when any fails, and 2 for a usage error, an unreadable spec, a spec the checker can't parse, or an invalid settings file. Warnings (a YAML block outside the parsed subset, a remote `$schema`) never fail a gate; tell the user those blocks weren't checked.
- Show the user every failing line. A failure is fixed in the spec through `orca-kit:spec`, never by this skill; a `check.*` failure is the spec checker's rule. Re-run the gate after the spec changes.
- `--gates` lists every rule. `--help` documents the settings file and the YAML subset it parses.
- If `python3` isn't available, say the gates didn't run; never pass a spec on a by-hand reading.

Repo settings are optional, in `<repo>/.orca-kit/spec-review.yml` (the repo is the nearest directory above the spec with `.orca-kit/` or `.git`, or `--repo`):

```yaml
ticket_pattern: '\b[A-Z][A-Z0-9]+-[0-9]+\b'  # set = every spec must name a ticket
max_words: 2000                             # length ceiling
max_growth: 0.25                            # revision loop: most a spec may grow in one pass
graduate_after: 3                           # findings --stats: specs a rule must be seen in to be proposed
secret_patterns:                            # extra secret regexes
  - 'acme_[a-z0-9]{32}'
risk_terms:                                 # replaces a risk's default terms
  billing: []                               # (risk.md lists the defaults)
risk_paths:                                 # replaces a risk's default paths
  migration: ['*/migrations/*', '*/db/changes/*']
```

Patterns are Python regexes; quote them in single quotes. Risk terms are lowercase words (a trailing `*` matches any ending) and risk paths are globs. `max_growth` is a share of the spec's words (loop.md). `graduate_after` is a whole number of at least 2 ([Graduating rules](#graduating-rules)). Any other key, or a value of the wrong type, is an error.

## Risk and sign-off

`${CLAUDE_PLUGIN_ROOT}/skills/spec-review/gate --risk [--repo ROOT] [--findings <findings.json> ...] specs/<slug>.md` runs the gates, then puts the spec in a risk tier. It is deterministic and only reads files. The classifier's defaults, the settings, the record format and the sign-off rules are in `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/risk.md`; read it before recording a sign-off.

- **Tier.** A spec is **high** risk when it names a path or term for `auth`, `security-boundary`, `data-model`, `migration`, `billing`, `public-api` or `breaking-change`, or when a finding passed with `--findings` has a non-null `risk`. Otherwise it is **low**, and needs no sign-off.
- **Output.** After the gates' result line: one `warning [risk.<risk>]` line per reason, then `<file>: risk low`, or `<file>: risk high: <risks>;` followed by `signed off by <name> on <date>`, `sign-off needed` or `sign-off stale (signed for <risks>)`, with a `risk.sign-off` error for the last two.
- **Exit.** 0 when the gates pass and the spec is low risk or signed off; 1 when a gate fails or a sign-off is missing or stale; 2 for the gate's own exit-2 cases, a findings file the validator rejects (the tier isn't computed from partial findings), or a review record that `record` rejects.
- **Findings.** Pass the merged reviewer findings (`findings --merge`) with `--findings` (repeatable, one spec per run), as [Running a review](#running-a-review) does; a findings file the user gives you works the same way.
- **Sign-off.** A high-risk spec passes only with a sign-off in `specs/reviews/<slug>.json` whose risks equal the current risks; a changed risk set makes an old sign-off stale. No script ever writes that file. **Only the user's explicit yes fills it in**: show them the risks and every reason line, ask whether they sign off on exactly those risks and under what name, and only on a clear yes write the record as risk.md says (their name, today's date, the risks shown). Never sign off yourself, never reuse an earlier yes for a different risk set, and never take a name from git config or the spec. On a no, the spec doesn't pass; say what would change that.
- **Tuning.** A repo can replace any risk's terms or paths in `.orca-kit/spec-review.yml` (`risk_terms`, `risk_paths`); a false high is a settings change for the user to make, never a reason to skip the sign-off.
- If `python3` isn't available, say the risk step didn't run; never call a spec low risk on a by-hand reading.

`${CLAUDE_PLUGIN_ROOT}/skills/spec-review/record specs/reviews/<slug>.json` validates a review record: `<file>:<line>: error [record.<rule>] <field>: <problem>. Fix: …`, then `<file>: ok, risk high (migration), signed off by <name> on <date>`. It exits 0 when valid, 1 on a rule failure, 2 for a usage error or a file that isn't a JSON object. `--rules` lists its rules; a record's optional `passes` (v0.4) is checked under `record.passes`, and its optional `questions` (v0.6, `pauses.md`) under `record.questions`. Run it after writing a record.

## Running a review

1. **Gates.** Run `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/gate specs/<slug>.md`. If it exits 2, stop and report why. A gate failure is reported, and the reviewers still run: their findings help the author fix it.
2. **Counts.** Run `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/gate --counts specs/<slug>.md` and keep its one line for the slicer.
3. **Reviewers.** Launch all five as subagents **in parallel, in one message**, each in a fresh context: `orca-kit:spec-review-ambiguity`, `orca-kit:spec-review-architecture`, `orca-kit:spec-review-security`, `orca-kit:spec-review-blast-radius` and `orca-kit:spec-review-slicer`. The prompt is exactly `Spec: specs/<slug>.md` and `Repo root: <absolute repo root>` on two lines, plus `Counts: <the counts line>` for the slicer. Nothing else: no summary, no conversation, no reason the spec was written, no hint about what to look for. Each agent holds its own rubric, rule keys and context list (`${CLAUDE_PLUGIN_ROOT}/skills/spec-review/reviewers.md` lists them).
4. **Save and merge.** Save each reply exactly as returned to its own file outside the repo, such as `$TMPDIR/spec-review/<slug>/<reviewer>.json`; never edit a reply. Run `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings --merge <the five files> > $TMPDIR/spec-review/<slug>/merged.json`. It validates every file, drops and reports each rejected finding (and every finding of a reply that isn't a bare JSON array), drops duplicates by rule and location, and prints the merged array. Tell the user each finding that was dropped as invalid and why; a duplicate drop needs no mention. If a reviewer's whole reply was rejected, you may re-run that one reviewer once, fresh; say so.
5. **Risk.** Run `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/gate --risk --findings $TMPDIR/spec-review/<slug>/merged.json specs/<slug>.md`. Its exit code is the review's result: 0 passes, 1 means a gate failed or a sign-off is needed (see [Risk and sign-off](#risk-and-sign-off)). Findings change only the risk tier, through their `risk`.
6. **Record.** Write `specs/reviews/<slug>.json` (format in `risk.md`): `spec`, `risk` as step 5 reported it, `sign_off` kept from an existing record (or `null`), and `passes` with one entry, `{"findings": <the merged array>, "open_blockers": <its blocker count>, "words": <words from step 2>, "gates": "passed" | "failed"}` (`gates` from step 1's exit code). A new review replaces any earlier `passes`. A pass of the [revision loop](#revision-loop) appends one instead. Run `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/record` on it and fix only what you wrote wrongly; then re-run step 5, which reads the record for the sign-off. Writing the findings never writes a sign-off.
7. **Report.** Show the gates' and the risk step's lines, then the findings grouped by severity, each with its reviewer, rule, location, evidence, question and suggested fix:
   - **Blockers** are open problems. The `fix` ones go back to the author through the [revision loop](#revision-loop). The `decision` ones are asked as `pause` prints them ([Pauses](#pauses-and-the-summary)); never pick an answer.
   - **Nits** are comments: show them, never loop on them.
   - Nothing advisory fails the review: an LLM finding never turns a pass into a fail, and the result is step 5's exit code alone. Say how many blockers are open.

If subagents can't be launched, say the reviewers didn't run and report only the gates and the risk step; never write findings yourself in a reviewer's place. The loop doesn't run either.

## Revision loop

After the first pass, `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/converge` decides the next step. Read `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/loop.md` before running it: it has the steps of a pass, the hand-off, the verdicts, the same-blocker rule and the bloat guard.

- **Run** `converge specs/<slug>.md` after pass 1, and `converge --previous $TMPDIR/spec-review/<slug>/pass-<n-1>/<slug>.md specs/<slug>.md` after each later pass. It reads the record's `passes`, re-runs the hard gates and counts words. It is deterministic and only reads files.
- **Verdicts.** `converged` (exit 0): no open blockers and the gates pass. `continue` (exit 3): only `fix` blockers and answered decisions are open, fewer than before, and a pass is left. `stop` (exit 1), with one reason: `bloat-ceiling`, `bloat-growth`, `gate`, `oscillation` (a blocker the pass before didn't have, in a section the revision changed), `no-progress` (open blockers didn't strictly decrease), `decision` or `cap` (pass 3 still has blockers). A new blocker in a section the revision didn't change was caught late: a `note [loop.late]` line, not oscillation. Exit 2 is an input error.
- **On continue**, save a copy of the spec outside the repo, then hand **only the `kind: fix` blockers and the decisions the user answered, with their answers,** to the author: this session, revising through `orca-kit:spec` refine. Change only what the blockers and answers point to, add no paragraphs, and don't interview the user. Then run a full pass again: the gates, the five reviewers **fresh** (never the earlier reviewers' contexts, never the author's reasoning or the blockers handed back), the merge, `gate --risk`, and a new entry appended to `passes`. At most 3 passes.
- **Nits** are never handed back. They stay comments.
- **On a stop**, don't run another pass or revise further. Run `pause`: it turns the stop into a question for the user ([Pauses](#pauses-and-the-summary)). On a bloat stop, the revision is rejected, and the author puts back the saved copy.
- If `python3` isn't available, don't run the loop: report pass 1 and say the loop didn't run.

## Pauses and the summary

The review pauses to ask the user, with the evidence and the options, when a `decision` blocker is open, when the loop stops (`cap`, `oscillation`, `no-progress`, a bloat stop), when a spec fails the skim test (over its length ceiling, or the slicer's `slicer.oversized` blocker), and when a high-risk spec needs its sign-off. Read `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/pauses.md` before the first pause: it has the triggers and their order, every option, the record's `questions`, how the loop resumes and the summary.

- **Run** `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/pause` after `converge`, with the same arguments. It runs `converge`, reads the record's answers and the risk tier, and prints the questions due now, one stage at a time: a rejected revision, then the skim test, then the loop's stop, then decisions, and the sign-off once the loop is done. A gate failure asks nothing: it is fixed through refine. Exit 1 means ask; 0 means nothing to ask, and its last line says what comes next (`continue to pass <n>`, or `render the summary`); 2 is an input error.
- **Ask** each question exactly as printed, one at a time. Every question is one concrete choice between numbered options. Never add, drop, reorder or recommend an option, and never answer one yourself. Only the user's own reply is an answer; on anything else, ask again.
- **Record** each answer as `pauses.md` says, in the record's `questions`: the id, question and options as printed, then the user's choice, their words verbatim and the date. Run `record` on the file. A sign-off is recorded in `sign_off`, as [Risk and sign-off](#risk-and-sign-off) says, not in `questions`. On a no, don't ask again.
- **Resume.** Run `converge` and `pause` again on the same pass. Once every open decision is answered, the verdict is `continue`, and the answers go to the author with the fix blockers, as context. The author applies them through refine. The reviewers never see the answers and never write them into the spec. Answers add no passes: the cap stays at 3, and an answered decision still counts as open in its own pass.
- **Summary.** When `pause` says `render the summary`, or the user ends the review, run `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/summary specs/<slug>.md` and show it as printed. It is rendered from the record: the gates, the risk tier and sign-off, the resolved and open findings, the questions and answers, and the pass history. Its last line states that the accepted spec is the single source of truth for code generation. Then leave acceptance to the user, through `orca-kit:spec` refine.
- If `python3` isn't available, don't pause by hand: report the last pass's decision blockers as open and say the pauses and the summary didn't run.

## Graduating rules

Core rule 8: a structural mistake reviewers keep catching should become a deterministic rule. Run this when the user asks which findings keep recurring, or whether a rule should graduate; it reads every review in the repo and is never part of reviewing one spec.

- **Run** `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings --stats [--repo ROOT]` (the repo defaults to the nearest directory above the current one with `.orca-kit/` or `.git`). It checks every `specs/reviews/*.json` with `record`, reports each invalid record with its problems and doesn't count it, then prints a table: per rule, its level, its Graduates value, its findings over every pass, and the number of specs it was seen in. It is deterministic and only reads files. Exit 0 when every record is valid, 1 or 2 when one isn't (it was reported and not counted), 2 for a usage error or invalid settings.
- **What is proposed.** A rule is proposed only when its rubric row marks it a candidate (the Graduates column: `check` for the spec checker, `secret_patterns` or `risk_terms` for the gate config) **and** it was seen in at least `graduate_after` specs (default 3). The column is fixed in each agent's rubric, not judged per run: a `no` rule, such as `ambiguity.two-readings`, is a judgement call and is never proposed, however often it is seen. One spec reviewed many times counts once, so one noisy review can't make a proposal.
- **Each proposal** (`graduate <n>: …`) gives the rule, its level, its counts, where it would be enforced, one example per spec (the record, pass, finding id, location and evidence), and, when the evidence shares a literal phrase across enough specs, a draft: the terms with their spec counts, plus a regex for the checker or a settings snippet for the config. Otherwise it says there is no draft.
- **Show** the table and every proposal to the user as printed. Say what the draft would catch, and that it is a starting point: the terms come from the evidence, so the user should trim any that aren't the mistake (a word the specs merely share). Never present a proposal as decided.
- **On the user's yes**, offer the rule as a **separate change**, never made during a review and never by a script: for this plugin, a PR touching `${CLAUDE_PLUGIN_ROOT}/skills/spec/check` (the `orca-kit:spec` skill's checker, with its tests); for a config target, an edit to the repo's `.orca-kit/spec-review.yml`, which the user reviews. Make it only if the user asks for it, in its own branch or commit. On a no, change nothing.
- No script edits the checker, the settings, the agents or a record. Changing a rule's Graduates value is a change to its agent file, like any rubric change.

## Findings

Reviewers return a JSON array of findings in the format of `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings.schema.json`:

```json
[
  {
    "id": "ambiguity-3",
    "reviewer": "ambiguity",
    "severity": "blocker",
    "kind": "fix",
    "rule": "ambiguity.weasel-word",
    "location": { "section": "Behavior & Edge Cases", "line": 42, "ref": "AC-3" },
    "evidence": "then the export fails gracefully",
    "concrete_question": "What exactly happens on a write error: exit code, message, partial file?",
    "suggested_fix": "Replace 'fails gracefully' with: exits 1, prints `cannot write <path>`, leaves no file.",
    "risk": null
  }
]
```

- Every field is required. `location.line`, `location.ref` and `risk` may be `null`; nothing else may, and no other fields are allowed.
- `severity` is `blocker` or `nit`, each mapped to one action. `blocker`: the spec can't be built or tested as written without someone guessing; a `fix` blocker goes back to the author, a `decision` blocker to the user. `nit`: a comment, with no action required. The level is fixed by the rule, never chosen per finding: each reviewer agent's rubric table declares every rule a blocker rule or a nit rule, and the validator rejects a finding whose severity isn't its rule's level, or whose rule isn't in a table. Only blockers loop. `findings --rules` prints the rule table, and `reviewers.md` lists it.
- `kind` is `fix` (the author can resolve it from the spec and repo) or `decision` (needs the user: two valid readings, a tradeoff, missing business context). A `decision` blocker always goes to the user.
- `rule` is `<reviewer>.<key>`, a stable key from the reviewer's rubric; it is how repeated findings are counted.
- `concrete_question` is one question, ending in `?`.
- `risk` is `null` or one of `auth`, `security-boundary`, `data-model`, `migration`, `billing`, `public-api`, `breaking-change`.
- `id` is lowercase and unique in the file.

## Validator

`${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings <findings.json> [...]` validates findings files. It needs only `python3`.

- Run it on every reviewer's output before using any of it. A finding it rejects is **dropped and reported**, never repaired or guessed at; tell the user which ones and why.
- It prints one line per problem, `<file>:<line>: error [<rule>] finding #<n> (<id>): <problem>. Fix: <what to do>.`, then a summary of the findings that passed: `<file>: ok, 4 findings: 2 blocker (1 decision), 2 nit`, or `<file>: 1 rejected, 3 kept: …` when any were dropped.
- It exits 0 when every finding is valid, 1 when any is rejected, and 2 for a usage error or a file that isn't a JSON array.
- `--rules` lists the rules it checks.
- `--merge <file> ...` combines reviewers' files into one validated, deduplicated array on stdout, with every drop reported on stderr; `reviewers.md` has the exact duplicate rule.
- `--stats [--repo ROOT]` counts findings by rule across the repo's review records and prints graduation proposals ([Graduating rules](#graduating-rules)).
- If `python3` isn't available, check each finding by hand against the list above and tell the user the validator didn't run.

## Non-goals

- Writing specs or editing their format: `orca-kit:spec` owns both, and this skill hands blockers back to it.
- Accepting a spec: that stays the user's explicit yes, through `orca-kit:spec` refine.
- Reviewing code or diffs, or verifying a build.
- Letting an LLM verdict block anything on its own.
- Changing the spec checker (`${CLAUDE_PLUGIN_ROOT}/skills/spec/check`).

## Bundled files

- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/gate`: the hard gates, the risk step (`gate --risk`) and the slicer's counts (`gate --counts`).
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings`: the findings validator, the merge (`findings --merge`) and the graduation counts and proposals (`findings --stats`).
- `${CLAUDE_PLUGIN_ROOT}/agents/spec-review-*.md`: the five reviewer agents, invoked as `orca-kit:spec-review-<reviewer>`.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/reviewers.md`: the reviewers' context and rule keys, the merge's duplicate rule, the record's `passes`, and the seeded examples.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/examples/`: a small fake repo with six specs, each seeding one problem, and `expected.json` naming the reviewer and rule that should catch it.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/record`: the review record validator.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/converge`: the revision loop's verdict (converged, continue or stop with a reason), counting the user's answered decisions.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/pause`: whether the review pauses for the user, and the questions it asks, in order.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/summary`: the review summary, rendered from the record.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/pauses.md`: the pause triggers and their order, the options, the record's `questions`, resuming after answers, and the summary.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/loop.md`: the revision loop: a pass, the hand-off to `orca-kit:spec` refine, the verdicts, the same-blocker rule, the bloat guard (`max_growth`) and the record's per-pass `words` and `gates`.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/risk.md`: the risk classifier's defaults and settings, the review record format, and how to record a sign-off.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings.schema.json`: the findings format as JSON Schema; the validator implements the same rules by hand, and its tests check the two agree.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/tests/`: the gate's and validators' tests and fixtures (`gate-*` fixtures are specs, `risk-*` fixtures are small repos with `specs/` and review records, `loop-*` fixtures add `previous/<slug>.md`, the spec before its last revision, `pause-*` fixtures are loop fixtures with questions and answers, one per pause trigger, and `stats-*` fixtures are repos of review records for `findings --stats`); run `python3 -m unittest discover -s skills/spec-review/tests` from the plugin root.
