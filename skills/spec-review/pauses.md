# Human-in-the-loop pauses and the review summary

Reference for the pauses (v0.6). SKILL.md says when they run. This file covers what makes the review pause, which question comes first, what a question looks like, how an answer is recorded, how the loop resumes after one, and the summary the user reads before accepting the spec.

## Who does what

| Step | Who | Writes |
|---|---|---|
| Decide whether to pause, and print the questions | `pause`, a deterministic script | Nothing |
| Ask the question | Claude, showing `pause`'s question block word for word | Nothing |
| Answer it | **The user**, and only the user | Their reply |
| Record the question and the answer | Claude, by hand, after the user replies | `questions` in `specs/reviews/<slug>.json` |
| Apply the answer to the spec | The author, through `orca-kit:spec` refine | The spec |
| Render the summary | `summary`, a deterministic script | Nothing |

No script writes the record, an answer or a sign-off. The answers are given to the author as context for the next revision, and they are never written into the spec by the reviewers. The reviewers never see them: their prompt stays `Spec:`, `Repo root:` and `Counts:`.

## When the review pauses

Run `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/pause` after every pass, right after `converge`, with the same arguments: `pause specs/<slug>.md` on pass 1, `pause --previous $TMPDIR/spec-review/<slug>/pass-<n-1>/<slug>.md specs/<slug>.md` after that. It runs `converge` itself, reads the record's questions and answers, and computes the risk tier from the spec and the last pass's findings. It asks one **stage** at a time. The first stage that applies is asked, in this order:

| Order | Trigger | When | Options (keys) |
|---|---|---|---|
| 1 | `loop` | `converge` stopped on `bloat-ceiling` or `bloat-growth`: the revision is rejected | `finish`, `refine` |
| 2 | `skim` | Pass 1 is over the length ceiling (`max_words`), or the slicer's `slicer.oversized` blocker is open | `split`, `keep`; over the ceiling, `split`, `trim` |
| 3 | (none) | Any other hard-gate stop (`gate`): nothing to choose. The review ends, and the gates are fixed through refine with the user | none |
| 4 | `loop` | `converge` stopped on `cap`, `oscillation` or `no-progress` | `finish`, `refine` |
| 5 | `decision` | `converge` stopped on `decision`: one question per open decision blocker nobody has answered, in the order of the findings | the reviewer's alternatives `a`, `b`, … (up to `e`), then `other`, `open`; with no lettered alternatives, `other`, `open` |
| 6 | `sign-off` | The loop is done (converged, or finished with blockers open by `finish` or `open`, but not after a bloat stop), the spec is high risk, and it has no current sign-off (v0.3) | yes and a name, or no |

Why this order:

- A rejected revision comes first, because the pass's findings describe a revision that is being put back.
- The skim test comes before everything else. A spec that should be split will be rewritten, so its decisions, its loop verdict and its sign-off would all be asked about text that is going away.
- A gate failure is a fact for refine to fix with the user. It isn't a choice, so it gets no question, the same as in v0.5.
- Decisions come after the loop's own stops. A pass that oscillated is reported as oscillation, the same as in `converge`.
- The sign-off comes last, once no revision is left to change the risks. A sign-off asked mid-loop could go stale on the next pass.

Run `pause` on the spec the last pass reviewed. After a bloat stop, the rejected revision stays in place until `pause` says to render the summary; then the author puts back the saved copy. Put back earlier, the spec no longer matches the record, and `converge` and `pause` exit 2. The summary still renders, with a `Note:` line.

`pause` prints the header line, `<file>: pause: ask <n> question(s) (<trigger>)`, followed by `; then, if the review goes on: decision, sign-off` when later stages are waiting. On `continue` it asks nothing, and the loop goes on. It exits 1 when there are questions to ask, 0 when there are none, and 2 for `converge`'s input errors. `pause --rules` lists the stages.

## A question

Each question is one choice between fixed options. `pause` prints it like this (from the live walk-through on the seeded `organize-todos` spec):

```
Question 2 of 4 [pass-1.ambiguity-6]: a decision for you

   The ambiguity reviewer raised a decision only you can make (ambiguity.two-readings), in Interfaces & Data Contracts, line 47:
   > CLI: `todo list [--tag <tag>] [--project <name>] [--by-priority]`; the flags combine.

   Whichever you choose: In every case `--by-priority` orders the filtered result. Add an AC that combines `--tag`, `--project` and `--by-priority`.

   When flags combine, does `--tag home --project work` list todos matching both (AND) or either (OR), and may `--tag` be given more than once, and if so must a todo have all the tags or any of them?

   1. Filters intersect (AND), `--tag` once only.
   2. Filters intersect and repeated `--tag` requires all tags.
   3. Repeated `--tag` matches any tag.
   4. Give your own answer: say in your own words what the spec should say.
   5. Leave it open: stop the review here, with this blocker listed as open in the summary.

   Reply with 1, 2, 3, 4 or 5, and for 4 add your answer.
```

A reviewer never picks a decision's answer: its `suggested_fix` lists the alternatives, lettered `(a) …; or (b) …`. `pause` turns each one into its own option, in order, and shows any text after the last alternative as "Whichever you choose". When the alternatives aren't lettered, it shows the reviewer's options as context and offers two choices: the user's own answer, or leaving the question open.

- **Show it as printed.** Don't reword it, add options, drop one, reorder them, or say which you would pick. There is no default and no recommendation. If the user asks what you think, explain the tradeoff, then hand the choice back.
- **One question at a time.** When a stage has several, ask them in order, and record each answer before asking the next.
- **Only the user's reply is an answer.** Silence, "whatever you think", "looks fine", or an answer to a different question is not one. Ask again. Never infer a choice from the conversation, git history or the spec. When a reply doesn't match an option ("2" with no words, or an option number that doesn't exist), say so and ask again.
- **Never answer a question yourself**, including when the answer seems obvious. A reviewer's alternative isn't the answer until the user picks it.

The options mean:

| Trigger | Key | Meaning | Then |
|---|---|---|---|
| `decision` | `a`, `b`, `c`, `d`, `e` | One of the reviewer's lettered alternatives | Resolves the blocker; the loop resumes |
| | `other` | The user's own answer, in their words | Resolves the blocker; the loop resumes |
| | `open` | Leave it open | The review ends with it open; the sign-off is still asked if needed |
| `skim` | `split` | Split the spec with `orca-kit:spec` and review each part | The review ends |
| | `keep` | Keep it as one spec (within the ceiling only) | Resolves the slicer's blocker; the review goes on |
| | `trim` | Cut it under the ceiling through refine, then a fresh review (over the ceiling only) | The review ends |
| `loop` | `finish` | Finish with the blockers open | The sign-off if needed, then the summary. After a bloat stop, no sign-off: the summary, then put back the saved copy |
| | `refine` | Work through the blockers with the user in refine, then a fresh review | The review ends; no sign-off, since the spec will change |
| `sign-off` | yes | Sign off on exactly the risks shown, under the name the user gives | Recorded as `sign_off` (risk.md) |
| | no | No sign-off | The spec doesn't pass review; the summary says so |

The sign-off is asked and recorded exactly as `risk.md` says, in `sign_off`. It is not stored in `questions`. On a no, don't ask again in this review: render the summary, which says the sign-off is needed.

## Recording an answer

After the user replies, add one entry to the record's `questions` list. Copy the id, the question and the options exactly as `pause` printed them:

```json
"questions": [
  {
    "id": "pass-1.ambiguity-6",
    "pass": 1,
    "trigger": "decision",
    "finding": "ambiguity-6",
    "question": "When flags combine, does `--tag home --project work` list todos matching both (AND) or either (OR), and may `--tag` be given more than once, and if so must a todo have all the tags or any of them?",
    "options": [
      {"key": "a", "text": "Filters intersect (AND), `--tag` once only."},
      {"key": "b", "text": "Filters intersect and repeated `--tag` requires all tags."},
      {"key": "c", "text": "Repeated `--tag` matches any tag."},
      {"key": "other", "text": "Give your own answer: say in your own words what the spec should say."},
      {"key": "open", "text": "Leave it open: stop the review here, with this blocker listed as open in the summary."}
    ],
    "answer": {"choice": "b", "words": "2", "answered_on": "2026-11-27"}
  }
]
```

| Field | Holds |
|---|---|
| `id` | `pass-<n>.<finding id>` for a decision, `pass-<n>.skim`, `pass-<n>.loop` |
| `pass` | The pass the question was asked after |
| `trigger` | `decision`, `skim` or `loop` |
| `finding` | The decision blocker's id; for `skim`, the `slicer.oversized` blocker's id or `null` (length only); for `loop`, `null` |
| `question`, `options` | As `pause` printed them: the question line, and each option's key and text in order |
| `answer` | `null` until the user replies. Then `choice` (the key of the option they picked), `words` (their reply, word for word) and `answered_on` (the date they replied) |

`record` checks every entry under `record.questions`. It checks that the id matches the pass, trigger and finding, that a `decision` names a decision blocker of that pass, that the option keys are the trigger's, and that the choice is one of them. `questions` is optional and needs `passes`, so every earlier record stays valid. A fresh review, not a continuation, replaces `passes` and drops `questions` with them; `sign_off` is kept as before.

## Resuming after answers

When every open decision of the pass is answered with a lettered alternative, `other` or `keep`, run `converge` again on the same pass. It now says `continue to pass <n+1>: hand <k> fix blocker(s) and <m> answer(s) to the author`, with a `note [loop.answered]` line for each answer. Then run the next pass as `loop.md` says, with one addition to the hand-off: the author gets each answered decision blocker, the question, the option picked and the user's words, alongside the fix blockers. The author applies the answer through refine under the same limits (change only what they name, add no paragraphs). Writing the decision into the spec's Decision Log is the author's job, through refine.

How answers interact with the loop's rules:

- **The pass cap stays at 3.** Answers add no passes. A decision answered after pass 3 has no pass left to apply it, so `converge` stops with `cap`, and `pause` asks the loop question.
- **Strict decrease.** An answered decision still counts as open in the pass it was raised in, so the next pass must have strictly fewer open blockers. The revision that applies the answer is what removes it.
- **A kept spec stays kept.** Once the user answers `keep` to the skim question, the slicer's `slicer.oversized` blocker isn't open again in later passes: it isn't counted, it isn't asked, and `converge` notes it (`was answered in pass <k>`). Fresh slicers flag the same size every pass, so without this, `keep` could never hold. The same-blocker rule is `loop.md`'s: rule and section.
- **Any other decision raised again is asked again.** It may be a new question under the same rule and section. In the live walk-through, the architecture reviewer's pass-2 `architecture.codebase-drift` decision asked where `projects.json` should live, after the pass-1 one in the same section had asked how it is written. Asking again costs the user one question; hiding a new one would be a guess.
- **Endings don't carry.** An answer that ends the review (`open`, `split`, `trim`, `refine`, `finish`) resolves nothing. If the loop were run again, the blocker would be open again.
- **Oscillation and the bloat guard** are unchanged. A new blocker in a section the revision changed still stops the loop, even when the revision was applying an answer.
- With no `questions` in the record, `converge`'s verdicts are exactly v0.5's.

## The review summary

When `pause` says `render the summary`, or the user stops the review, run `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/summary specs/<slug>.md` and show its output as printed. It is rendered from the record alone, checked by `record` first. The spec is read only for its status and word count. It shows:

- **Header.** The spec and its status, the hard gates on the last pass, the risk tier and the sign-off, the open blockers at the last pass, and how many questions were asked and answered.
- **Pass history.** Each pass's open blockers (fix and decision), nits, words and gate result.
- **Resolved since pass 1.** Blockers from an earlier pass with no matching blocker (rule and section) in the last one: fixed by a revision, answered by the user and then revised, or (the slicer's blocker, after `keep`) raised again and not reopened.
- **Open at the last pass.** Every open blocker with its question, marked when it is answered but not yet applied, and every nit as a comment.
- **Questions and answers.** Each question with its options, and the user's choice and words, or "Not answered yet".
- **Sign-off.** Who signed off, when, and for which risks, or that none is recorded.
- **The last line.** Once accepted, the spec is the single source of truth for code generation: build from it, not from the summary, the findings or the conversation. Acceptance is the user's explicit yes, through `orca-kit:spec` refine.

If the spec's words differ from the last pass's, a `Note:` line says the summary describes the spec that pass reviewed, for example after a bloat stop put back the saved copy. The same record and spec always give the same summary. It exits 0, or 2 for a missing or invalid record, a record with no passes, or a usage error. The summary never says a spec is ready to build, and it never accepts one.
