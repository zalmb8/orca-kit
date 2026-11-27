---
name: spec-review
description: Reviews a spec written by orca-kit:spec (specs/<slug>.md, normally a draft about to be accepted) before code is written, pairing deterministic hard gates with typed findings from narrow reviewers, and keeping product decisions with the user. Use when the user says "review the X spec", "is X ready to build", "check X before we accept it" or "run spec review", or to run the hard gates on a spec (spec checker, secret and PII scan, block parsing, ticket traceability, length ceiling), tier its risk (auth, migrations, data models, billing, public or breaking API changes) and require a human sign-off for a high-risk spec, or validate a reviewer's findings JSON or a review record.
---

# spec-review

Reviews a spec before code is written: a one-page spec is cheaper to check than a thousand lines of generated diff. It reports findings; it never writes, edits or accepts the spec. Done means the hard gates and the risk step have run, the user has every result with its lines, a high-risk spec has the user's own sign-off or is reported as not passing, and every finding the review uses has passed the findings validator.

## Status (v0.3)

Available: the hard gates (`gate`), risk tiering with the human sign-off (`gate --risk`, the review record and its validator `record`), and the findings format with its validator (`findings`). The steps below are planned (`${CLAUDE_PLUGIN_ROOT}/docs/spec-review/ROADMAP.md`) and **not yet available**:

| Step | Planned in |
|---|---|
| The five reviewer agents (`spec-review-ambiguity`, `-architecture`, `-security`, `-blast-radius`, `-slicer`) | v0.4 |
| Bounded revision loop | v0.5 |
| Human-in-the-loop pauses and the review summary | v0.6 |
| Graduating repeated findings (`findings --stats`) | v0.7 |

When the user asks to review a spec, run `gate --risk` (below) and report the gates' and the risk step's results; if the spec is high risk and not signed off, ask for the sign-off as [Risk and sign-off](#risk-and-sign-off) says. Say plainly that the advisory reviewers, the revision loop and the review summary aren't available yet, and don't run a review that imitates them. Passing `gate --risk` means only that: never report a spec as reviewed or ready to build.

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
risk_terms:                                 # replaces a risk's default terms
  billing: []                               # (risk.md lists the defaults)
risk_paths:                                 # replaces a risk's default paths
  migration: ['*/migrations/*', '*/db/changes/*']
```

Patterns are Python regexes; quote them in single quotes. Risk terms are lowercase words (a trailing `*` matches any ending) and risk paths are globs. Any other key, or a value of the wrong type, is an error.

## Risk and sign-off

`${CLAUDE_PLUGIN_ROOT}/skills/spec-review/gate --risk [--repo ROOT] [--findings <findings.json> ...] specs/<slug>.md` runs the gates, then puts the spec in a risk tier. It is deterministic and only reads files. The classifier's defaults, the settings, the record format and the sign-off rules are in `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/risk.md`; read it before recording a sign-off.

- **Tier.** A spec is **high** risk when it names a path or term for `auth`, `security-boundary`, `data-model`, `migration`, `billing`, `public-api` or `breaking-change`, or when a finding passed with `--findings` has a non-null `risk`. Otherwise it is **low**, and needs no sign-off.
- **Output.** After the gates' result line: one `warning [risk.<risk>]` line per reason, then `<file>: risk low`, or `<file>: risk high: <risks>;` followed by `signed off by <name> on <date>`, `sign-off needed` or `sign-off stale (signed for <risks>)`, with a `risk.sign-off` error for the last two.
- **Exit.** 0 when the gates pass and the spec is low risk or signed off; 1 when a gate fails or a sign-off is missing or stale; 2 for the gate's own exit-2 cases, a findings file the validator rejects (the tier isn't computed from partial findings), or a review record that `record` rejects.
- **Findings.** Pass every reviewer findings file with `--findings` (one spec per run). Until the reviewer agents exist (v0.4), that is only a findings file the user gives you.
- **Sign-off.** A high-risk spec passes only with a sign-off in `specs/reviews/<slug>.json` whose risks equal the current risks; a changed risk set makes an old sign-off stale. No script ever writes that file. **Only the user's explicit yes fills it in**: show them the risks and every reason line, ask whether they sign off on exactly those risks and under what name, and only on a clear yes write the record as risk.md says (their name, today's date, the risks shown). Never sign off yourself, never reuse an earlier yes for a different risk set, and never take a name from git config or the spec. On a no, the spec doesn't pass; say what would change that.
- **Tuning.** A repo can replace any risk's terms or paths in `.orca-kit/spec-review.yml` (`risk_terms`, `risk_paths`); a false high is a settings change for the user to make, never a reason to skip the sign-off.
- If `python3` isn't available, say the risk step didn't run; never call a spec low risk on a by-hand reading.

`${CLAUDE_PLUGIN_ROOT}/skills/spec-review/record specs/reviews/<slug>.json` validates a review record: `<file>:<line>: error [record.<rule>] <field>: <problem>. Fix: …`, then `<file>: ok, risk high (migration), signed off by <name> on <date>`. It exits 0 when valid, 1 on a rule failure, 2 for a usage error or a file that isn't a JSON object. `--rules` lists its rules. Run it after writing a record.

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
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/record`: the review record validator.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/risk.md`: the risk classifier's defaults and settings, the review record format, and how to record a sign-off.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/findings.schema.json`: the findings format as JSON Schema; the validator implements the same rules by hand, and its tests check the two agree.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/tests/`: the gate's and validators' tests and fixtures (`gate-*` fixtures are specs, `risk-*` fixtures are small repos with `specs/` and review records); run `python3 -m unittest discover -s skills/spec-review/tests` from the plugin root.
