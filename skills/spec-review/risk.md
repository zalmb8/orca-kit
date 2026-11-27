# Risk tiering and the review record

Reference for `gate --risk` and `record` (v0.3). SKILL.md says when to run them; this file has the classifier's defaults, its settings, the review record's format, and how a sign-off is recorded.

## Tiers

There are two tiers. A spec is **high** risk when it has at least one risk, from either source; otherwise it is **low**.

- **The classifier** reads the spec body (not the frontmatter), code blocks included, line by line. On each line, for each risk, it tries that risk's paths and then its terms; the first match is a reason. A glob or term that matches again on a later line is counted on the first reason, not repeated.
- **Findings**: every finding in a `--findings` file with a non-null `risk` is a reason, whatever its severity or kind, at the finding's `location` (line 1 when `line` is null). The file must pass the findings validator first; if it doesn't, the tier isn't computed and the gate exits 2, because a dropped finding could be the one carrying the risk.

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

`specs/reviews/<slug>.json`, next to the spec it reviews and committed with it. `record <file>` validates it.

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

Every field is required, `sign_off` may be `null`, and unknown fields are rejected. Later releases add their own fields (gate results, each pass's findings and open-blocker count, the questions asked and answered) to this format and to `record`.

## Sign-off

`gate --risk` passes a high-risk spec only when the record holds a sign-off whose `risks` equal the current risks as a set. Any change, a risk added or removed, makes the sign-off stale: the gate says what it covers and what the risks are now, and fails until the user signs off again. A record that fails `record` is never read as a sign-off (exit 2).

No script writes the record. Claude writes it, by hand, under these rules:

1. Show the user the risks and every reason line, and ask one question: whether they sign off on exactly those risks, and under what name.
2. Only an explicit yes counts. Silence, "looks fine", a yes to something else, an earlier sign-off, or a name taken from git config or the spec's `accepted_by` does not. If the user doesn't give a name, ask for it; never fill one in.
3. On that yes, write `sign_off` with the name they gave, today's date and the risks shown, and set `risk` to what `gate --risk` just reported. Change nothing else.
4. Run `record` on the file and `gate --risk` again; both must pass.
5. On no, leave `sign_off` as it is, and tell the user the spec can't pass review until the risk is removed from the spec or they sign off.
