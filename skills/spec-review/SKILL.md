---
name: spec-review
description: Reviews a spec written by orca-kit:spec (specs/<slug>.md, normally a draft about to be accepted) before code is written, pairing deterministic hard gates with typed findings from narrow reviewers, and keeping product decisions with the user. Use when the user says "review the X spec", "is X ready to build", "check X before we accept it" or "run spec review", or to validate a reviewer's findings JSON.
---

# spec-review

Reviews a spec before code is written: a one-page spec is cheaper to check than a thousand lines of generated diff. It reports findings; it never writes, edits or accepts the spec. Done means every finding the review uses has passed the findings validator, and the user has the findings by severity.

## Status (v0.1)

Only the findings format and its validator exist so far. The steps below are planned (`${CLAUDE_PLUGIN_ROOT}/docs/spec-review/ROADMAP.md`) and **not yet available**:

| Step | Planned in |
|---|---|
| Hard gates (`gate` script: spec checker, secret and PII scan, block parsing, traceability, length ceiling) | v0.2 |
| Risk tiering and human sign-off | v0.3 |
| The five reviewer agents (`spec-review-ambiguity`, `-architecture`, `-security`, `-blast-radius`, `-slicer`) | v0.4 |
| Bounded revision loop | v0.5 |
| Human-in-the-loop pauses and the review summary | v0.6 |
| Graduating repeated findings (`findings --stats`) | v0.7 |

When the user asks to review a spec, say plainly that the gates and reviewers aren't available yet, and don't run a review that imitates them. What you can do now is validate findings JSON that already exists, as below. Never report a spec as reviewed or ready to build.

## Core rules

Every release keeps these.

1. **Only deterministic checks are hard gates.** The same spec always gets the same pass/fail. An LLM finding never fails a gate.
2. **AI escalates, a human decides.** For risky domains, block only to require a named human's sign-off; never make the final call.
3. **Narrow reviewers in isolated contexts.** One rubric per reviewer, only the context that rubric needs, never the author's context or reasoning.
4. **Typed findings.** Every finding has a severity (`blocker | warning | nit`), a location, a concrete question and a suggested fix. Only blockers loop; warnings and nits become comments.
5. **Bounded loops.** At most 3 author–reviewer passes. Open blockers must strictly decrease each pass; if they don't, stop and ask a human.
6. **No spec bloat.** A revision may not push the spec past its length ceiling. Fixing a blocker by adding paragraphs is a smell, not a fix.
7. **Humans own the why, agents own the how.** Two valid readings of business logic are a question for the user, never a guess.
8. **Graduate repeated findings.** A structural mistake a reviewer keeps catching should become a deterministic rule.

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
- `severity` is `blocker`, `warning` or `nit`. Only blockers loop.
- `kind` is `fix` (the author can resolve it from the spec and repo) or `decision` (needs the user: two valid readings, a tradeoff, missing business context). A `decision` blocker always goes to the user.
- `rule` is `<reviewer>.<key>`, a stable key from the reviewer's rubric; it is how repeated findings are counted.
- `concrete_question` is one question, ending in `?`.
- `risk` is `null` or one of `auth`, `security-boundary`, `data-model`, `migration`, `billing`, `public-api`, `breaking-change`.
- `id` is lowercase and unique in the file.

## Validator

`${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings <findings.json> [...]` validates findings files. It needs only `python3`.

- Run it on every reviewer's output before using any of it. A finding it rejects is **dropped and reported**, never repaired or guessed at; tell the user which ones and why.
- It prints one line per problem, `<file>:<line>: error [<rule>] finding #<n> (<id>): <problem>. Fix: <what to do>.`, then a summary of the findings that passed: `<file>: ok, 4 findings: 2 blocker (1 decision), 1 warning, 1 nit`, or `<file>: 1 rejected, 3 kept: …` when any were dropped.
- It exits 0 when every finding is valid, 1 when any is rejected, and 2 for a usage error or a file that isn't a JSON array.
- `--rules` lists the rules it checks.
- If `python3` isn't available, check each finding by hand against the list above and tell the user the validator didn't run.

## Non-goals

- Writing specs or editing their format: `orca-kit:spec` owns both, and this skill hands blockers back to it.
- Accepting a spec: that stays the user's explicit yes, through `orca-kit:spec` refine.
- Reviewing code or diffs, or verifying a build.
- Letting an LLM verdict block anything on its own.
- Changing the spec checker (`${CLAUDE_PLUGIN_ROOT}/skills/spec/check`).

## Bundled files

- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings`: the findings validator.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings.schema.json`: the findings format as JSON Schema; the validator implements the same rules by hand, and its tests check the two agree.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/tests/`: the validator's tests and fixtures; run `python3 -m unittest discover -s skills/spec-review/tests` from the plugin root.
