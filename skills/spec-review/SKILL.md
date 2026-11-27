---
name: spec-review
description: Reviews a spec written by orca-kit:spec (specs/<slug>.md, normally a draft about to be accepted) before code is written, pairing deterministic hard gates with typed findings from narrow reviewers, and keeping product decisions with the user. Use when the user says "review the X spec", "is X ready to build", "check X before we accept it" or "run spec review", or to run the hard gates on a spec (spec checker, secret and PII scan, block parsing, ticket traceability, length ceiling) or validate a reviewer's findings JSON.
---

# spec-review

Reviews a spec before code is written: a one-page spec is cheaper to check than a thousand lines of generated diff. It reports findings; it never writes, edits or accepts the spec. Done means the hard gates have run and the user has every gate's result with its lines, and every finding the review uses has passed the findings validator.

## Status (v0.2)

Available: the hard gates (`gate`) and the findings format with its validator (`findings`). The steps below are planned (`${CLAUDE_PLUGIN_ROOT}/docs/spec-review/ROADMAP.md`) and **not yet available**:

| Step | Planned in |
|---|---|
| Risk tiering and human sign-off | v0.3 |
| The five reviewer agents (`spec-review-ambiguity`, `-architecture`, `-security`, `-blast-radius`, `-slicer`) | v0.4 |
| Bounded revision loop | v0.5 |
| Human-in-the-loop pauses and the review summary | v0.6 |
| Graduating repeated findings (`findings --stats`) | v0.7 |

When the user asks to review a spec, run the hard gates below and report their results. Say plainly that risk tiering and the advisory reviewers aren't available yet, and don't run a review that imitates them. Passing the gates means only that: never report a spec as reviewed or ready to build.

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
secret_patterns:                            # extra secret regexes
  - 'acme_[a-z0-9]{32}'
```

Patterns are Python regexes; quote them in single quotes. Any other key, or a value of the wrong type, is an error.

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

- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/gate`: the hard gates.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings`: the findings validator.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings.schema.json`: the findings format as JSON Schema; the validator implements the same rules by hand, and its tests check the two agree.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/tests/`: the gate's and validator's tests and fixtures (`gate-*` fixtures are specs); run `python3 -m unittest discover -s skills/spec-review/tests` from the plugin root.
