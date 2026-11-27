# `orca-kit:spec-review`: design and roadmap

A skill that reviews a specification before code is written. Review is where intent gets validated: a one-page spec is cheaper to check than a thousand lines of generated diff. LLM reviewers are probabilistic, so the skill pairs **deterministic hard gates** with **specialised advisory reviewers**, and keeps the human on the decisions only a human can make.

## Scope

The skill **reviews specs and reports findings**. It reviews `specs/<slug>.md` files written by `orca-kit:spec`, normally a `draft` that is about to be accepted.

| Step | What runs | Can block? | Output |
|---|---|---|---|
| **Hard gates** | Deterministic scripts: the spec checker, secret and PII scan, schema parsing, traceability, length ceiling | Yes | Pass/fail per gate, with the line |
| **Risk tiering** | A deterministic classifier, plus the risk flags from the advisory reviewers | Only to require human sign-off | A risk tier and the reasons |
| **Advisory review** | Five specialised reviewer subagents in parallel, each in a fresh context with one rubric | No | Typed findings |
| **Revision loop** | The author revises; fresh reviewers re-check. At most 3 passes, blockers only | No | Open-blocker count per pass |
| **Human pause** | Stops and asks when a product decision, high risk, non-convergence or a failed skim test comes up | — | Questions for the user, and the sign-off record |

Trigger phrases: "review the X spec", "is X ready to build", "check X before we accept it", "run spec review".

### Non-goals

- Writing specs, or editing their format. `orca-kit:spec` owns both; this skill hands blockers back to it.
- Accepting a spec. Acceptance stays the user's explicit yes, given through `orca-kit:spec` refine.
- Reviewing code or diffs, and verifying a build. Those are separate future skills.
- Letting an LLM verdict block anything on its own.
- Changing the spec checker (`skills/spec/check`). Graduated rules are proposed for it, not added by this skill.

## Core rules

These come straight from the concepts the skill is built on, and every release must keep them.

1. **Only deterministic checks are hard gates.** The same spec must always get the same pass/fail. An LLM finding never fails a gate.
2. **AI escalates, a human decides.** For risky domains the skill blocks only to require a named human's sign-off; it never makes the final call.
3. **Narrow reviewers in isolated contexts.** One rubric per reviewer, only the context that rubric needs, and never the author's context or reasoning.
4. **Typed findings.** Every finding has a severity (`blocker | nit`, fixed by its rule), a location, a concrete question and a suggested fix. Only blockers loop; nits become comments.
5. **Bounded loops.** At most 3 author–reviewer passes. Open blockers must strictly decrease each pass; if they don't, the loop stops and a human is asked.
6. **No spec bloat.** A revision may not push the spec past its length ceiling. Fixing a blocker by adding paragraphs is a smell, not a fix.
7. **Humans own the why, agents own the how.** Two valid readings of business logic are a question for the user, never a guess.
8. **Graduate repeated findings.** A structural mistake an advisory reviewer keeps catching should become a deterministic rule.

## Findings format

Reviewers return JSON, validated by a script before the skill uses it. A finding that fails validation is dropped and reported, never guessed at.

```json
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
```

- `severity` is `blocker` or `nit`, each mapped to one action. `blocker`: the spec can't be built or tested as written without someone guessing; a `fix` blocker goes back to the author, a `decision` blocker to the user. `nit`: a comment, with no action required. The level is fixed by the rule, never chosen per finding: each reviewer agent's rubric table declares every rule a blocker rule or a nit rule, and the validator rejects a finding whose severity isn't its rule's level, or whose rule isn't in a table.
- `kind` is `fix` (the author can resolve it from the spec and repo) or `decision` (needs the user: two valid interpretations, a tradeoff, missing business context). A `decision` blocker always pauses for the human.
- `rule` is a stable key per reviewer rubric. It is how repeated findings are counted for graduation.
- `risk` is `null` or one of `auth`, `security-boundary`, `data-model`, `migration`, `billing`, `public-api`, `breaking-change`.

Each review writes `specs/reviews/<slug>.json`: the hard-gate results, the risk tier, every pass's findings and open-blocker count, the human questions asked and answered, and the sign-off record. It is committed with the spec.

## The reviewers

Each is an agent in `agents/` with one rubric and a fixed context budget. The skill runs them in parallel and gives each only what its rubric needs.

| Agent | Looks for | Context it gets |
|---|---|---|
| `spec-review-ambiguity` | Weasel words ("fast", "gracefully", "as appropriate"), missing error states, untestable ACs, prose that should be a decision table or state machine | The spec only |
| `spec-review-architecture` | Drift from the codebase's real constraints, ADRs and steering files (`CLAUDE.md`, `AGENTS.md`) | The spec, steering files, ADRs, and the files under `Existing:` |
| `spec-review-security` | Data flows, trust boundaries, auth scopes, failure modes, against the repo's security policy if it has one | The spec, security policy files, and the auth and data code it touches |
| `spec-review-blast-radius` | Downstream services, schemas and contracts the change affects but the spec doesn't mention | The spec and a repo search for every contract it changes |
| `spec-review-slicer` | Specs too large for reliable implementation or review; proposes independently deliverable slices | The spec and its word and AC counts |

## Roadmap

Each release can be used on its own. Bump `.claude-plugin/plugin.json` `version` with each one.

### v0.1: Skeleton and findings format ✅
- [x] `skills/spec-review/SKILL.md` with a description that triggers on the review phrases and states the core rules.
- [x] `skills/spec-review/findings.schema.json` and `skills/spec-review/findings` script (Python 3, stdlib only) that validates reviewer output and prints a summary by severity.
- [x] Failing fixtures for each malformed-finding case and a stdlib test runner: `python3 -m unittest discover -s skills/spec-review/tests`.
- [x] **Done when:** the skill loads as `orca-kit:spec-review`, and malformed findings (bad severity, no location, no concrete question) are rejected with the reason.

### v0.2: Hard gates ✅
- [x] `skills/spec-review/gate` script, called through `${CLAUDE_PLUGIN_ROOT}`, running every gate and exiting non-zero on any failure.
- [x] Gates: the spec checker (`skills/spec/check --as accepted`), a secret and PII scan, every fenced `json` / `yaml` / OpenAPI block parses (and validates when it names a schema), traceability to a ticket when the repo requires it, and a length ceiling.
- [x] Repo settings in `.orca-kit/spec-review.yml` (ticket pattern, length ceiling, extra secret patterns), all optional with defaults.
- [x] Output in the spec checker's format: `<file>:<line>: <severity> [<gate>] <section>: <problem>. Fix: <what to do>.`
- [x] **Done when:** the same spec always gets the same result, and a failing fixture exists for each gate.

### v0.3: Risk tiering and sign-off ✅
- [x] A deterministic classifier in `gate --risk`: paths and terms for auth, permissions, migrations, data models, billing and public or breaking API changes, tunable in `.orca-kit/spec-review.yml`.
- [x] Advisory reviewers can raise a `risk` on a finding; either source puts the spec in the high-risk tier.
- [x] A high-risk spec needs a sign-off record (`signed_off_by`, `signed_off_on`, the risks shown) in `specs/reviews/<slug>.json` before review can pass. The skill asks; only the user's explicit yes fills it in.
- [x] **Done when:** a spec touching a migration can't pass review without a recorded human sign-off, and the skill never records one itself.

### v0.4: Specialised reviewers ✅
- [x] The five agents in `agents/`, each with its rubric, its `rule` keys, a context list, and the findings format.
- [x] The skill runs them in parallel in fresh contexts, passing the spec path and rubric only, never the author's reasoning.
- [x] Findings are validated, deduplicated by location and rule, and written to `specs/reviews/<slug>.json`.
- [x] Non-blocking findings are shown as comments; nothing advisory fails the review. (They were warnings and nits until v0.5; now they are nits.)
- [x] Sample specs with seeded problems in `skills/spec-review/examples/` (a weasel word, a missing error state, an unmentioned downstream contract, an oversized spec).
- [x] **Done when:** each seeded problem is reported by the reviewer that owns it, as a valid typed finding.

### v0.5: Bounded revision loop ✅
- [x] Blockers of kind `fix` go back to the author (the session that drafted the spec, via `orca-kit:spec` refine); reviewers re-run fresh on the revised spec.
- [x] At most 3 passes. The open-blocker count must strictly decrease; a pass that introduces new blockers (oscillation) stops the loop.
- [x] Bloat guard: a revision that exceeds the length ceiling, or grows the spec more than the configured share in one pass, is rejected and counts as non-convergence.
- [x] The hard gates re-run after every revision.
- [x] **Done when:** a seeded spec converges within 3 passes, and an oscillating fixture stops at the pass where blockers rose.

### v0.6: Human-in-the-loop pauses
- [ ] The skill pauses and asks the user, with the evidence and the options, when:
  - a `decision` finding appears (two valid readings of business logic, or a tradeoff not answered in the docs);
  - the loop hits its cap or oscillates;
  - the spec is high risk (v0.3);
  - the skim test fails: the spec is over its length ceiling or the slicer says it should be split, so a human decomposition pass is needed.
- [ ] Every question is one concrete choice; answers are recorded in `specs/reviews/<slug>.json` and passed to the author as context, not written into the spec by the reviewers.
- [ ] Review ends with a summary the user reads before accepting the spec: gates, risk tier, resolved and open findings, sign-off. The skill states that the accepted spec is the single source of truth for code generation.
- [ ] **Done when:** each pause trigger has a fixture, and in none of them does the skill pick an answer itself.

### v0.7: Graduating rules
- [ ] `findings --stats` counts findings by `rule` across every `specs/reviews/*.json` in the repo.
- [ ] A rule seen in several reviews, and mechanical enough to check, is proposed as a deterministic rule, with the matching examples, for the spec checker or the gate config.
- [ ] Proposals are shown to the user; adding the rule is a separate change.
- [ ] **Done when:** seeded review files with a repeated rule produce a graduation proposal, and a judgement-call rule is never proposed.

## Decision log

| Decision | Why |
|---|---|
| A separate skill, not a mode of `orca-kit:spec` | Writing and reviewing are different jobs, and the reviewer must not share the author's context. |
| Reviews `orca-kit:spec` specs and reuses its checker as one hard gate | One place defines the spec format; the gate doesn't re-implement it. |
| No LLM output is ever a hard gate | Identical inputs can give different verdicts, which erodes trust in the gate. |
| Risk tiering blocks only to require a human sign-off | The agent classifies risk; the human makes the call. |
| Five reviewers with one rubric each, run in parallel in fresh contexts | A single "review this spec" prompt degrades through context dilution and competing priorities, and fresh contexts don't inherit the author's assumptions. |
| Findings are JSON validated by a script | Typed findings can be counted, deduplicated, looped on and graduated; free prose can't. |
| `kind: decision` separates product questions from fixes | Agents surface tradeoffs and ask; they never silently pick one. |
| Only blockers loop; nits are comments (warnings were too, until v0.5 removed them) | Looping on everything over-engineers the spec. |
| The loop caps at 3 passes and requires strictly fewer open blockers each pass | Non-convergence by pass 3 means missing business context or conflicting requirements, which more tokens won't fix. |
| A length ceiling is both a hard gate and a loop guard | Oversized specs cause lost-in-the-middle failures downstream and fail the skim test for humans. |
| Review results live in `specs/reviews/<slug>.json`, committed with the spec | They're versioned with what they reviewed, and a JSON file in a subdirectory doesn't trip `check specs/*.md`. |
| Repo settings live in `.orca-kit/spec-review.yml`, all optional | The skill works with no setup; repos tune ticket patterns, ceilings and risk paths as needed. |
| Graduation proposes rules; it doesn't add them | Changing the checker is its own reviewed change. |
| A findings file is a JSON array of finding objects | The smallest shape a reviewer can return; the review record (`specs/reviews/<slug>.json`) can hold these arrays per pass later. |
| Every field is required; only `location.line`, `location.ref` and `risk` may be `null`; unknown fields are rejected | A typed finding with a typo'd or missing field would otherwise slip through. A section is always known, but a line or ID may not be. |
| A missing field is reported under that field's own rule (`finding.location`, `finding.concrete-question`, …) | "No location" reads as a location problem, and rule keys stay one per field. |
| `rule` must be `<reviewer>.<key>`, prefixed by the finding's `reviewer` | Keeps rule keys stable and namespaced, so graduation counts can't mix two rubrics' rules. |
| `concrete_question` must end in `?`, and text fields must be non-empty | A deterministic check that it is a question at all; judging whether it is concrete is a reviewer's job. |
| `id` is lowercase (`[a-z0-9.-]`) and unique within a file | Duplicate or free-form IDs can't be referenced or deduplicated reliably. |
| The validator is written by hand; `findings.schema.json` documents the same format, and a test checks they agree | Stdlib only, no `jsonschema` install, and the two can't silently drift. |
| A file that isn't JSON, or isn't a top-level array, exits 2; a rejected finding exits 1 | Matches the spec checker: 2 is a parse or usage error, 1 a rule failure. |
| Problem lines name the finding as `finding #<n> (<id>)`, at the line of the offending field | The index finds a finding with no valid ID; the line lets an editor jump to it. |
| Gate problems are named `<gate>.<rule>`; the spec checker's own rules pass through as `check.<rule>` | One output format for every gate, and a checker failure keeps the rule name `check --rules` documents. |
| The `check` gate runs `check --as accepted` without `--repo` | The roadmap names that command; `--repo` adds only warnings, which `orca-kit:spec` already reports while writing. |
| Exit 2 when the checker can't parse the spec or the settings file is invalid | Matches the checker and `findings`: 2 is a parse or usage error, 1 a rule failure. |
| The secret and PII scan covers the whole file, frontmatter and code included, with fixed built-in patterns plus the repo's `secret_patterns` | A secret in a code block is still a secret; fixed regexes keep the scan deterministic. |
| Placeholders (`<password>`, `${VAR}`), reserved example domains (`example.com`, `.test`), well-known test cards and international-format-only phone numbers aren't flagged; matched values are masked | Specs legitimately show placeholders and fake data; a gate that flags them gets ignored, and its output mustn't leak what it found. |
| YAML is parsed by a small strict subset parser in the gate; a block using a feature outside it (anchors, tags, multiple documents, multi-line scalars) is a warning and isn't checked | Stdlib has no YAML. Guessing at unparsed YAML would make a pass dishonest, and failing valid YAML would make the gate wrong; the warning says which blocks went unchecked. |
| The settings file is parsed with the same YAML subset, then checked strictly: only `ticket_pattern`, `max_words` and `secret_patterns`, with their types | One parser to document and test; an unknown key or wrong type is a typo, so it is an error, not ignored. |
| An OpenAPI document is a ```` ```openapi ```` block, or a JSON or YAML block with a top-level `openapi` or `swagger` key; only its required top-level fields are checked | Full OpenAPI validation needs its meta-schema and a validator; required fields catch the common broken fragment. |
| "Validates when it names a schema" means a top-level `"$schema"` naming a repo-relative file, checked with a JSON Schema subset; a URL `$schema` or an unsupported keyword is a warning | The gate is offline and deterministic, so it can't fetch schemas, and it says what it didn't check rather than passing it silently. |
| Traceability is required exactly when `ticket_pattern` is set; a match anywhere in the body outside code counts | One setting, no separate on/off flag; the spec format has no ticket field, and this skill doesn't change the format. |
| The length ceiling counts words in the body the way the checker's section budgets do, default 2000 | The example accepted spec is about 1200 words, and the checker's section budgets allow up to 2830; 2000 fails the skim test before the budgets do. |
| The repo is the nearest directory at or above the spec with `.orca-kit/` or `.git`, or `--repo` | Specs live at `specs/<slug>.md`, so the settings are found with no flag; `--repo` covers anything else. |
| Gate fixtures are `tests/fixtures/gate-<case>/`, each a small repo with its own settings and schema files | Each case is self-contained, and the findings fixtures stay as they are. |
| `gate --risk` runs the five gates and then the risk step in one command; without `--risk` the output and exit codes are unchanged | One command is the whole deterministic part of a review, and v0.2 callers and tests see no difference. |
| Risk is not a sixth gate: its reasons are `warning [risk.<risk>]` lines after the gates' result line, a missing or stale sign-off is one `error [risk.sign-off]`, and a `risk …` result line follows | Core rule 2: risk blocks only to require a sign-off. Warnings are the checker format's way to report without failing, and `GATES` and the gates' result line stay as they were. |
| Two tiers, `low` and `high`; any risk from either source makes it `high` | The roadmap names only a high tier and one consequence (sign-off); a medium tier would have no behaviour. |
| Risk terms are lowercase phrases (words joined by space, `-`, `_` or nothing; a trailing `*` for any ending), not regexes; paths are case-insensitive globs against each path-like token with a leading `/` | Risk lists are edited by hand and are long; phrases and globs are easier to read and tune than regexes, and stay deterministic. Ticket and secret patterns stay regexes. |
| The classifier reads the body only, code blocks included, and reports one reason per risk and matching term or glob, at its first line, counting the rest | A migration in a SQL block is still a migration, and the frontmatter repeats the title. Fifteen lines saying "migration" would bury the reasons the user has to read. |
| `risk_terms` / `risk_paths` replace a listed risk's defaults; unlisted risks keep theirs | One rule covers removing a false positive (an empty list) and adding a repo's own paths (copy and extend); defaults are listed in `risk.md` and a test keeps it in step with the code. |
| Defaults lean toward escalating, and "permissions" maps to `auth` | A false high costs one question; a missed high is an unreviewed risky change. The `risk` enum has no separate permissions value. |
| Findings come in as `gate --risk --findings <file>` (repeatable, one spec per run); a finding of any severity or kind with a non-null `risk` raises the tier | No reviewer agents exist until v0.4, so a file is the smallest interface, and it is the same one v0.4 will produce. A nit can still name a risky area. |
| A findings file the validator rejects stops the risk step with exit 2, rather than dropping the bad finding and computing a tier | A dropped finding could be the one carrying the risk; a tier from partial input could pass a risky spec. |
| The review record is `specs/reviews/<slug>.json` next to the spec, with exactly `spec`, `risk` (`tier`, `risks`, `reasons`) and `sign_off` (`null` or `signed_off_by`, `signed_off_on`, `risks`); unknown fields are rejected, and a `record` script validates it | The smallest record that holds the tier, its reasons and the sign-off. Strict like the findings format; v0.4–v0.6 add their fields (gate results, passes, questions) to the same list. |
| A sign-off is valid only when its `risks` equal the current risks as a set; a record that fails `record` is never read as a sign-off (exit 2) | "The risks shown" are what the human agreed to; any change, even a risk going away, is a different spec from the one they signed off. |
| No script writes the record; Claude writes it by hand after the user's explicit yes, with the name the user gives, and a test checks the scripts never write files | Core rule 2, and the v0.3 done criterion: the only path to a sign-off goes through the user. |
| Low-risk specs need no record in v0.3 | Nothing in it would be read yet; v0.6's review summary is where every review gets one. |
| Risk fixtures are `tests/fixtures/risk-<case>/`, each a small repo with `specs/<slug>.md` and, when the case needs one, `specs/reviews/<slug>.json` | The record sits where a real repo keeps it, so the fixtures test the path the gate looks up. |
| The reviewers are plugin agents with read-only tools (`Read`, plus `Grep` and `Glob` for the three that search the repo), and the prompt is only `Spec:` and `Repo root:` lines | Read-only tools enforce "never edits"; the spec-only reviewers can't search at all. The roadmap's "spec path and rubric only": the rubric lives in the agent file, so the prompt carries nothing the author could leak into. |
| The slicer gets its counts as one `Counts:` line from a new `gate --counts` (words as the length gate counts them, the ceiling, `- **AC-n:**` items outside code) | "Its word and AC counts" must be deterministic, not the reviewer's own count; reusing the gate's counter keeps one definition of a word. `gate` without `--counts` is unchanged. |
| The slicer's anchors are more than 10 ACs or more than 75% of the word ceiling, and its findings are always `decision` | The roadmap gives no numbers; 10 ACs is past the accepted example spec's size, and 75% leaves room before the hard length gate fails. How to split a spec is the user's call (v0.6's skim test pause). |
| Each rubric has tiebreaks so one problem gets one rule, and "don't report" lines for what other reviewers own | Stable `rule` keys only count well (v0.7) if the same problem always lands on the same key, and narrow rubrics shouldn't overlap. |
| Dedup is `findings --merge`: same `rule`, same location (section ignoring case and spacing, line, ref ignoring case) and same `risk`; the most severe, then a `decision`, then the first is kept, in the first's place | Deterministic and testable. Including `risk` means a merge can never lower the tier. Findings are never edited or combined by the script. |
| Every reviewer must report at most one finding per rule and location, combining several problems at one spot into one finding | The live run showed blast-radius reporting two consumers at one spec line, which the merge then collapsed, losing one. Making it the reviewer's contract keeps the dedupe rule simple and loss-free. |
| A merge drops and reports a rejected finding, a whole file that isn't a JSON array, or a finding whose id an earlier file used, and goes on; its stdout is always a valid findings array | The findings format's rule (drop and report, never guess), applied per reviewer, so one malformed reply doesn't lose the other four. Its output feeds `gate --risk --findings`, which would otherwise exit 2. |
| The review record gains an optional `passes` list (at most 3 entries of `findings` and `open_blockers`), checked by `record`; a v0.3 record without it stays valid | The roadmap puts every pass's findings and open-blocker count in the record. Optional keeps v0.3 records and tests valid; the cap and count prepare v0.5's loop. |
| In v0.4 a review is one pass, and every review writes a record, low risk included | There is no loop yet, so a new review replaces `passes`. The findings need a committed home whatever the tier; v0.3's "low-risk specs need no record" applied only while a record held nothing but the sign-off. |
| The review's pass/fail is `gate --risk --findings` alone; blockers are reported as open, decisions as questions, nits (and, until v0.5, warnings) as comments | "Nothing advisory fails the review" (core rule 1). Findings reach the result only through `risk`, which can only require a sign-off. |
| The examples are one fake repo (`examples/repo/`) with six specs, two beyond the roadmap's four so architecture and security own a seed too, and `expected.json` outside it | Every reviewer gets a seeded problem to be checked on; the fake repo gives architecture an ADR and blast-radius a consumer to find, and answers outside the repo root can't leak to a reviewer. |
| The live reviewer runs are not committed or unit-tested; the tests check the agents, rules, examples and scripts deterministically | Reviewer output is probabilistic, and a test that calls an LLM would not be deterministic. The live check is rerun when a rubric changes. |
| The loop's verdict is a new script, `converge`, rather than a flag on `gate` or `record` | It needs the record, the spec, the previous spec and the gates together; a separate script keeps `gate` and `record` output and exit codes exactly as they were. It loads `gate` for the word counter, the settings and the gates, so a word and a gate result have one definition. |
| `converge` exits 0 converged, 1 stop, 3 continue, 2 input error, and prints one verdict line after a status line | A caller can branch on the code alone; 0, 1 and 2 keep their meaning across the skill's scripts (ok, a rule stops it, a usage or parse problem), and continue isn't a failure, so it gets its own code. |
| Stop reasons are checked in a fixed order: `bloat-ceiling`, `bloat-growth`, `gate`, `oscillation`, `no-progress`, then converged, `decision`, `cap` | One verdict per input, always the same. Bloat comes first because the revision itself is rejected; a gate failure next because nothing else is trustworthy on a failing spec; `decision` after the count checks, since a pass that oscillated is reported as oscillation. |
| The same blocker across passes is the same `rule` and `location.section` (ignoring case and spacing), counted as a multiset; line, ref, id and wording are ignored | A revision moves lines, and fresh reviewers anchor and word the same problem differently, so the merge's full location would make every surviving blocker look new. Rule plus section still catches a blocker of a new kind or in a new place, and the strict-decrease rule guards the rest. |
| Oscillation is any new blocker, even when the open count fell (superseded below: only a new blocker in a section the revision changed) | The roadmap: "a pass that introduces new blockers (oscillation) stops the loop". A revision that fixes two blockers and creates one is trading problems, not converging. |
| Any `kind: decision` blocker stops the loop (`decision`), even with `fix` blockers beside it, and is never handed to the author | Core rule 7 and the findings format ("a decision blocker always pauses for the human"); the author's fixes may depend on the answer. v0.6 formalises the pause; v0.5 only stops and reports. |
| Every pass must pass the hard gates, pass 1 included: a failing gate stops the loop (`gate`) | Gate failures are deterministic facts that `orca-kit:spec` refine fixes with the user (a `TBD:`, a missing list), not reviewer findings for an LLM loop. One rule covers both "a revision broke a gate" and "the draft never passed". |
| A new optional setting `max_growth` (a number ≥ 0, default 0.25) in `.orca-kit/spec-review.yml`; growth over `max_growth` × the previous words is rejected, exactly at it is allowed | The roadmap's "configured share" needed a key and a default. The example specs are about 600 words; fixing a missing error state adds an AC and an edge-case row, roughly 60–100 words, well under 25%, while a new section isn't. The ceiling is `max_words`, so there is one ceiling. |
| The bloat checks compare the spec with the copy saved before the revision (`--previous`), not with the record's word counts | The previous spec is ground truth; the record's `words` are an audit trail, and `converge` checks they agree with the files given (exit 2 if not), so a verdict is never computed for a different version of the spec. |
| A rejected (bloated) revision is still reviewed and recorded as a pass, and the author puts back the saved copy | One verdict point after each recorded pass keeps the loop simple; the record keeps the evidence of why the loop stopped. |
| Pass entries gain optional `words` (a whole number) and `gates` (`passed` \| `failed`); every v0.4 record stays valid | The loop needs each pass's size and gate result in the record; optional keeps v0.4 records and tests valid. |
| No change to `orca-kit:spec`: the `fix` blockers reach refine as conversation context, with written limits (change only what they name, add no paragraphs, keep `draft`, no interview) | Refine already revises from the conversation and runs the checker; a findings-input hook would change another skill's interface. `loop.md` describes the hand-off. A `fix` blocker that turns out to need the user stays unfixed and stops the loop. |
| The author is the session that drafted the spec, normally the one running the review; a review session that didn't draft it acts as the author through refine | Reviewers must not share the author's context, but the author may see the findings; one session can't be handed to another without Orca orchestration, which this skill doesn't need. |
| The previous spec is saved outside the repo as `$TMPDIR/spec-review/<slug>/pass-<n>/<slug>.md`, under the spec's own name | Next to the reviewers' saved replies, never committed, and `gate` on it gives the same result as on the spec (the checker compares the file name with `id`). |
| Loop fixtures are `tests/fixtures/loop-<case>/`: a small repo with `specs/<slug>.md`, `specs/reviews/<slug>.json` and `previous/<slug>.md`; `test_findings.py` skips them like `gate-*` and `risk-*` | Same pattern as v0.2 and v0.3, which also added their prefix to that one line. |
| The live loop run used general-purpose subagents told to act as each reviewer agent file, since the plugin's agents weren't installed in the building session | The rubric and the prompt (`Spec:`, `Repo root:`, `Counts:`) are the same; tools were limited by instruction rather than by the agent frontmatter. Reviewer output is probabilistic, so the run is evidence, not a test. |
| Severity is two levels, each mapped to one action: `blocker` (the spec can't be built or tested as written without someone guessing; `fix` to the author, `decision` to the user) and `nit` (a comment, no action required). `warning` is removed, and a finding with it is rejected | Severity is the least reliable dimension in defect classification, for human raters and for LLM judges from one run to the next. Live run 3 stopped on false oscillation because a reviewer rated the same problem `warning` in pass 1 and `blocker` in pass 2. A level that maps to no action of its own only gives a judge room to disagree with itself. |
| Severity is fixed by the rule, not chosen per finding: every rule key is declared a blocker rule or a nit rule, and `findings` rejects a finding whose severity isn't its rule's level, or whose rule isn't declared | Category and detection can be made repeatable with explicit criteria; how bad something is, judged per finding, can't. A reviewer decides only whether a rule applies, which is the part a rubric can pin down. |
| The rule table is each agent's `## Rubric` table, `| Rule | Level | Report when |`, and `findings` parses those rows from `agents/spec-review-*.md`; there is no separate `rules.json` | The agent reads its rubric anyway, so a second file would be a copy that can drift. One set of rows is what the agent applies, what the validator enforces and what the tests check. `findings --rules` prints it, and an unreadable or malformed table is exit 2. |
| A problem that is sometimes serious and sometimes not is split into two rules. New nit rules: `ambiguity.vague-prose`, `ambiguity.unstated-detail`, `ambiguity.compound-failure`, `architecture.list-placement`, `security.hardening`, `blast-radius.stale-reference`. Now nits: `ambiguity.needs-table`, `architecture.duplicate-capability`, `slicer.independent-parts`. Every other v0.4 rule is a blocker | Each split follows a case that came up in the live runs: a weasel word in an AC vs. in the Goal, a missing first-order error state vs. a failure inside a failure handler, an `Existing:` path that doesn't exist vs. a planned change written under `Existing:`, an exploitable flaw vs. a cost-free hardening, a consumer that breaks vs. usage text that goes stale. Each rubric gives worked examples for both levels. |
| `ambiguity.weasel-word` keeps its key as the blocker rule (a weasel word in an AC, edge-case row or `New:` contract); it isn't renamed to `untestable-ac`, which stays the blocker rule for an AC untestable for other reasons | Renaming a rule splits its graduation count (v0.7), and the seeded example and `expected.json` use `weasel-word`. The pair is `weasel-word` (blocker) and `vague-prose` (nit). |
| `security.data-flow` covers credentials, personal data and data the spec or policy marks sensitive; ordinary user data in a file with the default mode is `security.hardening` (nit) | Run 3's security reviewer reported the file mode of `archive.json` (todo titles) as a nit in one pass and the same concern under another rule in the next. The line between the two rules has to be one a reviewer can check. |
| Duplicates in `findings --merge` share a rule, so they share a severity; the tie-break is a `decision` over a `fix`, then the first | Severity can no longer differ within a duplicate set. The other tie-breaks are unchanged. |
| The summary and merge lines drop the warning count: `<b> blocker (<d> decision), <k> nit` | A count for a level that can't occur would be noise. This changes `findings`, `--merge` and `record` output, which the redesign requires. |
| Oscillation means the revision caused it: a new blocker (no blocker with its rule and section in the pass before) is oscillation only if its section changed between `--previous` and the spec. A new blocker in an unchanged section was caught late, is a `note [loop.late]` line, and the loop goes on if open blockers strictly fell (otherwise `no-progress`) | Fresh reviewers catch things late or rate them differently. Stopping on a blocker the revision never touched blamed the author for the reviewer's variance, which is what stopped run 3. |
| Sections are compared deterministically: `## ` headings outside code, matched ignoring case and spacing, lines compared with trailing spaces dropped. A section only one file has is changed, and a blocker naming a section the spec doesn't have counts as in a changed section | Plain text comparison, with no similarity threshold to tune. When the section can't be found, the loop errs toward stopping and asking a human. |
| The v0.1 findings fixtures' invented rule `slicer.split` becomes `slicer.independent-parts`, and fixture findings that were warnings become the matching nit rule (`blast-radius.stale-reference`, `security.hardening`, `ambiguity.vague-prose`) | Every fixture rule must now be in the rule table, at its level. The fixtures keep their line numbers, so the tests that point at a field's line still hold. |
