# The revision loop

Reference for the bounded revision loop (v0.5). SKILL.md says when it runs. This file covers who does what in each pass, the hand-off to the author, the verdict `converge` prints, the same-blocker rule, the bloat guard and what the record holds for each pass.

## Who does what

| Role | Who | Sees |
|---|---|---|
| **Author** | The session that drafted the spec, which is normally the one running the review, revising through `orca-kit:spec` refine | Only the `kind: fix` blockers of the last pass, as findings |
| **Reviewers** | The five reviewer agents, launched fresh for every pass exactly as in [Running a review](SKILL.md#running-a-review) | `Spec:`, `Repo root:` and, for the slicer, `Counts:`. Never the author's reasoning, the earlier passes or the blockers handed back |
| **Gates and verdict** | `gate`, `gate --risk` and `converge`, which are deterministic scripts | The files |
| **User** | Anyone the loop stops for | The stop reason and every open blocker |

If the review runs in a session that didn't draft the spec, that session is the author for the loop: it revises through refine the same way, and it still gets nothing from the reviewers but their findings.

## A pass

Pass 1 is the review in SKILL.md, steps 1–6. Its record entry also holds `words` (from `gate --counts`) and `gates` (`passed` when `gate` exited 0, `failed` when it exited 1). Then, for every pass:

1. **Verdict.** Run `${CLAUDE_PLUGIN_ROOT}/skills/spec-review/converge specs/<slug>.md` on pass 1. From pass 2 on, add `--previous $TMPDIR/spec-review/<slug>/pass-<n-1>/<slug>.md`, the copy saved in step 2 of the pass before. It prints the problem lines, a status line and one verdict (below). Show the user the status line every pass.
2. **On `continue`, save and hand back.** Copy the spec as it is now to `$TMPDIR/spec-review/<slug>/pass-<n>/<slug>.md`, outside the repo and under the spec's own name. Then hand the pass's `kind: fix` blockers to the author (see [The hand-off](#the-hand-off)).
3. **Revise.** The author revises the spec through `orca-kit:spec` refine.
4. **Re-review.** Run SKILL.md's review steps 1–6 again on the revised spec: the gates, the counts, the five reviewers in **fresh** contexts, the merge and `gate --risk`. Then **append** a pass to `passes` with its `findings`, `open_blockers`, `words` and `gates`, and set `risk` to what `gate --risk` just reported. Run `record` on the file. The hard gates re-run after every revision because step 4 always runs them.
5. Go back to step 1 with pass n+1.

The loop never runs a fourth pass: `record` rejects a fourth entry, and `converge` stops at pass 3.

## The hand-off

The author gets a list of the last pass's blockers with `kind: fix`. For each one it gets the `rule`, `location`, `evidence`, `concrete_question` and `suggested_fix`, exactly as the merged findings hold them. It gets nothing else:

- no nits, which stay comments and are shown to the user in the report;
- no `decision` blockers, which the loop never hands back (the verdict stops on them);
- no reviewer conversation, because a reviewer returns nothing but its findings.

Refine has no step that takes findings as input, and `orca-kit:spec` isn't changed for the loop. The blockers reach refine as the conversation it already reads, with these limits stated alongside them:

- Change only what each blocker points to. Take the suggested fix or something smaller. Don't rewrite sections the blockers don't name.
- Don't fix a blocker by adding paragraphs. The bloat guard rejects a revision that grows the spec past `max_growth` or the ceiling.
- Keep `status: draft`, and run refine's own check (its step 8). Don't ask for acceptance: that comes after the review, through refine's "Accepting" steps.
- No interview. A `fix` blocker can be resolved from the spec and the repo by definition. If one turns out to need the user (two valid readings, a tradeoff, missing business context), the author doesn't guess. It leaves that blocker unfixed, and the skill stops the loop and reports the blocker as a question for the user.

## The verdict

`converge` reads the record, re-runs the hard gates on the spec, counts its words and those of `--previous`, and prints one verdict. The checks run in this order, and the first that applies is the verdict:

| Verdict | When | Exit | The skill then |
|---|---|---|---|
| stop: `bloat-ceiling` | The revision put the spec over `max_words` | 1 | Rejects the revision: the author puts back the saved copy from the pass before, and the skill reports the stop |
| stop: `bloat-growth` | The revision grew the spec by more than `max_growth` of its previous words | 1 | The same as `bloat-ceiling` |
| stop: `gate` | A hard gate fails on the spec, after a revision or on pass 1 | 1 | Shows `gate`'s failing lines. Gate failures are fixed through refine with the user, outside the loop |
| stop: `oscillation` | The pass has a new blocker (see [The same blocker](#the-same-blocker)) in a section the revision changed, even if the count fell | 1 | Reports the new blockers and the ones still open |
| stop: `no-progress` | The open-blocker count didn't strictly decrease | 1 | Reports the open blockers |
| converged | The pass has no open blockers and the gates pass | 0 | Reports the review as usual, with nits as comments |
| stop: `decision` | An open blocker is `kind: decision` | 1 | Lists every decision blocker as a question for the user, with the options, and never picks one |
| stop: `cap` | Pass 3 still has open blockers | 1 | Reports the open blockers |
| continue | Only `fix` blockers are open, and there is a pass left | 3 | Hands them back (step 2 above) |

Exit 2 is an input problem, not a verdict: a usage error, an unreadable spec, invalid settings, an invalid record or one with no `passes`, pass 2 or 3 without `--previous` (or pass 1 with it), or a record whose last pass's `words` or `gates` (or the previous pass's `words`) don't match the specs given. Fix the input and run it again.

Every stop is non-convergence, and the skill stops there. It reports the reason, `converge`'s problem lines, the open-blocker count of every pass and each open blocker, then leaves the next step to the user. It doesn't run another pass, and it doesn't revise the spec any further. v0.6 turns these stops into formal questions with options. Until then the skill says why the loop stopped and what is open, and nothing more.

## The same blocker

Two blockers in consecutive passes are the same blocker when they have the same `rule` and the same `location.section`, ignoring case and runs of whitespace. Blockers are counted as a multiset: if pass 1 has two `ambiguity.weasel-word` blockers in Behavior & Edge Cases, pass 2 may have up to two there before one counts as new. `line`, `ref`, `id` and the wording are ignored, because a revision moves lines and fresh reviewers anchor and word the same problem differently. A blocker under a rule or in a section the pass before had no blocker for is new.

A new blocker is oscillation only when the revision caused it. `converge` compares the spec with `--previous` section by section: the `## ` headings outside code, matched ignoring case and spacing, with each section's lines compared after dropping trailing spaces. A section that differs, or that only one of the two files has, is changed. A new blocker in a changed section, or in a section the spec doesn't have, is `oscillation`. A new blocker in a section the revision left alone was caught late. A fresh reviewer saw something an earlier one missed, or rated it differently, but the revision didn't cause it. `converge` reports it as a `note [loop.late]` line and treats it like any other open blocker: the loop goes on if open blockers still strictly fell, and stops with `no-progress` if they didn't.

## The bloat guard

Words are counted the way the length gate counts them (`gate --counts`). From pass 2 on:

- **Ceiling.** The revised spec may not be over `max_words` (default 2000). This is the length gate's ceiling. `converge` reports it as `bloat-ceiling` before `gate`, because the revision is what put the spec over.
- **Growth.** The revised spec may not grow by more than `max_growth` of the previous spec's words in one pass: it is rejected when `words - previous > max_growth × previous`. Growing exactly by the share is allowed, and shrinking never counts.

```yaml
# .orca-kit/spec-review.yml
max_words: 2000     # the length ceiling, also the bloat ceiling
max_growth: 0.25    # the most a revision may grow the spec in one pass, as a share
```

`max_growth` is a number of at least 0 (`0` allows no growth at all). The default, 0.25, lets a 600-word spec gain about 150 words in one pass, enough for a missing error state's AC and edge-case row, but not for a new section.

## The record's passes

Each entry in `passes` (format in `risk.md` and `reviewers.md`) may also hold:

| Field | Holds |
|---|---|
| `words` | The spec's word count for that pass, from `gate --counts` |
| `gates` | `passed` when `gate` exited 0 on the spec that pass reviewed, `failed` when it exited 1 |

Both are optional, so every v0.4 record stays valid. The loop writes both for every pass. `converge` checks them against the specs it is given, so a verdict is never computed for a different version of the spec than the one reviewed. A fresh review, not a continuation of the loop, still replaces `passes` with one entry.
