# Risk tiering and the review record

Reference for `gate --risk` and `record` (v0.3; the record's `passes` are v0.4, their `words` and `gates` v0.5, its `questions` v0.6; risks that stay raised and the shared open count v0.8). SKILL.md says when to run them; this file has the classifier's defaults, its settings, the review record's format, and how a sign-off is recorded.

## Tiers

There are two tiers. A spec is **high** risk when it has at least one risk, from either source; otherwise it is **low**.

- **The classifier** reads the spec body (not the frontmatter), code blocks included, line by line. On each line, for each risk, it tries that risk's paths and then its terms; the first match is a reason. A glob or term that matches again on a later line is counted on the first reason, not repeated.
- **Findings**: every finding in a `--findings` file with a non-null `risk` is a reason, whatever its severity or kind, at the finding's `location` (line 1 when `line` is null). The file must pass the findings validator first; if it doesn't, the tier isn't computed and the gate exits 2, because a dropped finding could be the one carrying the risk.
- **Earlier passes** (v0.8): every finding with a non-null `risk` in the review record's `passes` is a reason too, saying which pass raised it (`finding blast-radius-1 (blocker fix from blast-radius) raised it in pass 1, and it stays raised for this review`). A finding also given with `--findings` is listed once. The record is read for every tier, so an invalid record is exit 2 even for a spec that would otherwise be low.

**A raised risk stays raised.** A risk a finding raised in any pass stays raised for the rest of that review, until a sign-off covers it. A revision that fixes the finding fixes how the spec describes the change, not the change: in the first hands-on review, pass 1's blast-radius findings raised `breaking-change`, pass 2's fresh reviewers had nothing left to report, the tier went to low, and the sign-off was never asked. A fresh review replaces `passes`, so it starts over. The classifier's terms and paths are still read from the spec as it is now: they are the text itself, and a revision that removes one is an edit anyone reading the diff sees.

The risks are the findings format's `risk` values: `auth` (also permissions and roles), `security-boundary`, `data-model`, `migration`, `billing`, `public-api`, `breaking-change`.

## Defaults

Terms are lowercase words matched case-insensitively as whole words; the words of a term may be joined by a space, `-`, `_` or nothing (`sign in` matches `sign-in` and `signin`), and a word ending in `*` matches any ending (`migrat*` matches `migration`, `migrated`). Paths are globs matched case-insensitively against every path-like token on the line with a `/` put in front, where `*` also matches `/`: `*/migrations/*` matches `db/migrations/0007.sql`.

| Risk | Terms | Paths |
|---|---|---|
| `auth` | `auth`, `authn`, `authz`, `authenticat*`, `authoriz*`, `authoris*`, `login*`, `log in`, `logout`, `log out`, `sign in`, `sign up`, `oauth*`, `saml`, `sso`, `openid`, `oidc`, `mfa`, `2fa`, `access control*`, `rbac`, `acl`, `acls`, `permission check*`, `permission model*`, `user role*`, `roles and permissions`, `password*`, `credential*`, `api key*`, `access token*`, `session token*`, `session cookie*` | `*/auth/*`, `*/auth.*`, `*/authn/*`, `*/authz/*`, `*/permissions/*`, `*/permissions.*`, `*/rbac/*`, `*/acl/*`, `*/login/*`, `*/login.*` |
| `security-boundary` | `trust boundar*`, `security boundar*`, `sandbox*`, `cors`, `csrf`, `xss`, `ssrf`, `sql injection`, `encrypt*`, `decrypt*`, `tls`, `secret store*`, `secrets manager*`, `personal data`, `pii`, `untrusted input*` | `*/security/*`, `*/crypto/*`, `*/secrets/*`, `*/sandbox/*`, `*/cors.*`, `*/csp.*` |
| `data-model` | `data model*`, `database schema*`, `db schema*`, `schema change*`, `new table*`, `new column*`, `add column*`, `drop column*`, `drop table*`, `rename column*`, `foreign key*`, `primary key*`, `orm`, `entity relationship*` | `*/models/*`, `*/model/*`, `*/entities/*`, `*.prisma`, `*/schema.rb`, `*/schema.sql` |
| `migration` | `migrat*`, `backfill*`, `alter table*`, `schema version*`, `data conversion*` | `*/migrations/*`, `*/migrate/*`, `*/alembic/*`, `*/flyway/*`, `*/liquibase/*` |
| `billing` | `billing`, `invoic*`, `payment*`, `subscription*`, `pricing`, `price change*`, `refund*`, `chargeback*`, `credit card*`, `stripe`, `paddle` | `*/billing/*`, `*/payments/*`, `*/payment/*`, `*/invoices/*`, `*/subscriptions/*`, `*/stripe/*` |
| `public-api` | `public api*`, `rest api*`, `http api*`, `graphql`, `grpc`, `api endpoint*`, `http endpoint*`, `rest endpoint*`, `webhook*`, `sdk`, `sdks`, `api version*`, `api contract*` | `*/openapi.*`, `*/swagger.*`, `*.proto`, `*.graphql`, `*/api/*`, `*/routes/*` |
| `breaking-change` | `breaking change*`, `backward* incompatib*`, `not backward* compatib*`, `no longer backward* compatib*`, `deprecat*` | (none) |

The defaults lean toward escalating: a false high costs one question to the user, a missed high costs an unreviewed risky change.

## Settings

In `.orca-kit/spec-review.yml`, next to the gate's other settings. `risk_terms` and `risk_paths` map a risk to a list; **a listed risk's list replaces its defaults**, risks not listed keep theirs, and an empty list turns that source off for that risk. To add to a default list, copy it from the table above.

```yaml
risk_terms:
  migration: ['migrat*', 'backfill*', 'alter table*', 'flyway']  # adds flyway
  billing: []                                                    # this repo has no billing
risk_paths:
  data-model: ['*/src/types.ts']
```

A risk that isn't in the list above, a term that isn't lowercase words (with optional `*`), or an empty glob is a settings error (exit 2).

## The review record

`specs/reviews/<slug>.json`, next to the spec it reviews; the record and its pass snapshots (`loop.md`) belong with the spec, versioned together, so the review can be rechecked against what it reviewed. `record <file>` validates it.

```json
{
  "spec": "add-due-dates",
  "risk": {
    "tier": "high",
    "risks": ["migration"],
    "reasons": [
      "specs/add-due-dates.md:43: warning [risk.migration] Interfaces & Data Contracts: names the path \"src/migrations/0002-add-due.ts\", which matches \"*/migrations/*\" (and on 7 more lines)."
    ]
  },
  "sign_off": {
    "signed_off_by": "Sam Rivera",
    "signed_off_on": "2026-11-27",
    "risks": ["migration"]
  }
}
```

| Field | Holds |
|---|---|
| `spec` | The spec's slug; the file must be named `<spec>.json`. |
| `risk.tier` | `low` or `high`, as `gate --risk` last reported it. |
| `risk.risks` | The risks it reported, each once; empty exactly when the tier is `low`. |
| `risk.reasons` | Its `risk.*` warning lines, each without the `Fix:` part; non-empty for a high tier. |
| `sign_off` | `null` until the user signs off. Then `signed_off_by` (the name the user gave), `signed_off_on` (the date they said yes, `YYYY-MM-DD`) and `risks` (exactly the risks shown to them). |
| `passes` | Optional (v0.4). One entry per review pass, at most 3: `{"findings": [...], "open_blockers": <n>}`, the array `findings --merge` printed and its open-blocker count (its blockers, less a `slicer.oversized` blocker the user answered `keep` to in an earlier pass, v0.8), plus optional `words` and `gates` (v0.5, `loop.md`). Every risk a finding in any pass names must be in `risk.risks`. `reviewers.md` has the rules. |
| `questions` | Optional (v0.6), and needs `passes`. One entry per question `pause` printed and the skill asked: its id, pass, trigger, finding, question and options, and the user's `answer` (`null` until they reply). `pauses.md` has the format and the rules. |

`spec`, `risk` and `sign_off` are required, `sign_off` may be `null`, `passes` and `questions` may be left out (so every v0.3 and v0.5 record stays valid), and unknown fields are rejected. The sign-off is asked as a pause too (`pauses.md`), but it is recorded here in `sign_off`, never in `questions`.

## Sign-off

`gate --risk` passes a high-risk spec only when the record holds a sign-off whose `risks` equal the current risks as a set. Any change, a risk added or removed, makes the sign-off stale: the gate says what it covers and what the risks are now, and fails until the user signs off again. A record that fails `record` is never read as a sign-off (exit 2).

No script writes the record. Claude writes it, by hand, under these rules:

1. Show the user the risks and every reason line, and ask one question: whether they sign off on exactly those risks, and under what name.
2. Only an explicit yes counts. Silence, "looks fine", a yes to something else, an earlier sign-off, or a name taken from git config or the spec's `accepted_by` does not. If the user doesn't give a name, ask for it; never fill one in.
3. On that yes, write `sign_off` with the name they gave, today's date and the risks shown (every risk the review raised, including one an earlier pass raised and a revision fixed), and set `risk` to what `gate --risk` just reported. Change nothing else.
4. Run `record` on the file and `gate --risk` again; both must pass.
5. On no, leave `sign_off` as it is, and tell the user the spec can't pass review until the risk is removed from the spec or they sign off.
