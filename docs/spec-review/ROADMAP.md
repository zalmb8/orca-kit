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
4. **Typed findings.** Every finding has a severity (`blocker | warning | nit`), a location, a concrete question and a suggested fix. Only blockers loop; warnings and nits become comments.
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

### v0.1: Skeleton and findings format
- [ ] `skills/spec-review/SKILL.md` with a description that triggers on the review phrases and states the core rules.
- [ ] `skills/spec-review/findings.schema.json` and `skills/spec-review/findings` script (Python 3, stdlib only) that validates reviewer output and prints a summary by severity.
- [ ] Failing fixtures for each malformed-finding case and a stdlib test runner: `python3 -m unittest discover -s skills/spec-review/tests`.
- [ ] **Done when:** the skill loads as `orca-kit:spec-review`, and malformed findings (bad severity, no location, no concrete question) are rejected with the reason.

### v0.2: Hard gates
- [ ] `skills/spec-review/gate` script, called through `${CLAUDE_PLUGIN_ROOT}`, running every gate and exiting non-zero on any failure.
- [ ] Gates: the spec checker (`skills/spec/check --as accepted`), a secret and PII scan, every fenced `json` / `yaml` / OpenAPI block parses (and validates when it names a schema), traceability to a ticket when the repo requires it, and a length ceiling.
- [ ] Repo settings in `.orca-kit/spec-review.yml` (ticket pattern, length ceiling, extra secret patterns), all optional with defaults.
- [ ] Output in the spec checker's format: `<file>:<line>: <severity> [<gate>] <section>: <problem>. Fix: <what to do>.`
- [ ] **Done when:** the same spec always gets the same result, and a failing fixture exists for each gate.

### v0.3: Risk tiering and sign-off
- [ ] A deterministic classifier in `gate --risk`: paths and terms for auth, permissions, migrations, data models, billing and public or breaking API changes, tunable in `.orca-kit/spec-review.yml`.
- [ ] Advisory reviewers can raise a `risk` on a finding; either source puts the spec in the high-risk tier.
- [ ] A high-risk spec needs a sign-off record (`signed_off_by`, `signed_off_on`, the risks shown) in `specs/reviews/<slug>.json` before review can pass. The skill asks; only the user's explicit yes fills it in.
- [ ] **Done when:** a spec touching a migration can't pass review without a recorded human sign-off, and the skill never records one itself.

### v0.4: Specialised reviewers
- [ ] The five agents in `agents/`, each with its rubric, its `rule` keys, a context list, and the findings format.
- [ ] The skill runs them in parallel in fresh contexts, passing the spec path and rubric only, never the author's reasoning.
- [ ] Findings are validated, deduplicated by location and rule, and written to `specs/reviews/<slug>.json`.
- [ ] Warnings and nits are shown as comments; nothing advisory fails the review.
- [ ] Sample specs with seeded problems in `skills/spec-review/examples/` (a weasel word, a missing error state, an unmentioned downstream contract, an oversized spec).
- [ ] **Done when:** each seeded problem is reported by the reviewer that owns it, as a valid typed finding.

### v0.5: Bounded revision loop
- [ ] Blockers of kind `fix` go back to the author (the session that drafted the spec, via `orca-kit:spec` refine); reviewers re-run fresh on the revised spec.
- [ ] At most 3 passes. The open-blocker count must strictly decrease; a pass that introduces new blockers (oscillation) stops the loop.
- [ ] Bloat guard: a revision that exceeds the length ceiling, or grows the spec more than the configured share in one pass, is rejected and counts as non-convergence.
- [ ] The hard gates re-run after every revision.
- [ ] **Done when:** a seeded spec converges within 3 passes, and an oscillating fixture stops at the pass where blockers rose.

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
| Only blockers loop; warnings and nits are comments | Looping on everything over-engineers the spec. |
| The loop caps at 3 passes and requires strictly fewer open blockers each pass | Non-convergence by pass 3 means missing business context or conflicting requirements, which more tokens won't fix. |
| A length ceiling is both a hard gate and a loop guard | Oversized specs cause lost-in-the-middle failures downstream and fail the skim test for humans. |
| Review results live in `specs/reviews/<slug>.json`, committed with the spec | They're versioned with what they reviewed, and a JSON file in a subdirectory doesn't trip `check specs/*.md`. |
| Repo settings live in `.orca-kit/spec-review.yml`, all optional | The skill works with no setup; repos tune ticket patterns, ceilings and risk paths as needed. |
| Graduation proposes rules; it doesn't add them | Changing the checker is its own reviewed change. |
