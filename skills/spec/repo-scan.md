# Repo scan for refine

Refine scans the target repo before it asks the user anything. The scan answers every question about *how the repo works*, so the interview can stick to *intent*. Run it from the target repo's git root.

## 1. Commands

Find the exact build, lint and test commands. Copy each one exactly as written, and note the file it came from. Never invent a command or "fix" one you found.

| Source | What to read | How to write the command |
|---|---|---|
| `package.json` | `scripts` (`build`, `lint`, `test`, `typecheck`, `format`, …) | Use the package manager the lockfile implies: `pnpm-lock.yaml` → `pnpm <script>`, `yarn.lock` → `yarn <script>`, `bun.lock` or `bun.lockb` → `bun run <script>`, otherwise `npm run <script>` (`npm test` for `test`). In a monorepo, also read the workspace packages the goal touches. |
| `Makefile` | Targets such as `build`, `lint`, `test`, `check` | `make <target>` |
| `pyproject.toml` | `[project.scripts]`, `[tool.poetry.scripts]`, `[tool.hatch.envs.*.scripts]`, and tool sections such as `[tool.pytest.ini_options]`, `[tool.ruff]`, `[tool.mypy]` | Prefix with the runner the repo uses (`uv run`, `poetry run`, `hatch run`), as its lockfile (`uv.lock`, `poetry.lock`) or docs show. A tool section only tells you the tool is configured; take the actual command from CI or a Makefile if they have one. |
| CI config | `.github/workflows/*.yml` `run:` steps; also `.gitlab-ci.yml` or `.circleci/config.yml` if present | Copy the `run:` lines verbatim, including setup steps such as `npm ci` or `uv sync`. |
| Others, if present | `justfile`, `Taskfile.yml`, `tox.ini`, `noxfile.py`, `Cargo.toml`, `go.mod` | `just <recipe>`, `task <name>`, `tox -e <env>`, `nox -s <session>`, `cargo build` / `cargo test`, `go build ./...` / `go test ./...` |

- **CI wins.** When CI and a local script disagree, list the CI command first: it is what must pass to merge.
- **Setup counts.** Include install or setup steps the commands depend on (`npm ci`, `uv sync`, a required env var named in CI).
- **Nothing found** means `TBD: no <build|lint|test> command found` in Environment & Commands. Don't ask the user about it in the interview.

## 2. Critical files

Find the files an agent will read or change to meet the goal.

- Search for the nouns and verbs in the goal (`grep`/`rg` for names, routes, command names, table names).
- Follow from the entry point the goal touches (a CLI command, route handler, page or job) to the code it calls.
- Note the existing tests for that code: they show the test style and where new tests go.

## 3. Types and schemas

Find the contracts the feature has to respect or extend: TypeScript types and interfaces, zod or other validators, pydantic or dataclass models, JSON Schema, OpenAPI, GraphQL, protobuf, database migrations and ORM models.

## 4. Repo instructions

Read the target repo's `CLAUDE.md` and `AGENTS.md` (at the root, and in the directories the goal touches) for rules agents already follow there: boundaries, commands, style. `guardrails.md` says how they shorten the spec's Always / Ask First / Never lists. Don't copy them into the spec.

## 5. Protected and generated files

Find the paths the Always / Ask First / Never lists adapt to (see `guardrails.md`). Note each path; never open or copy a secret.

| Kind | Where to look |
|---|---|
| Secrets | `.env*`, credential and key files, and the secret files `.gitignore` lists; secrets that CI steps reference (`${{ secrets.* }}`). |
| Generated | Build output (`dist/`, `build/`, `out/`), lockfiles, and files or directories that a header comment, README or `.gitattributes` (`linguist-generated`) marks as generated or vendored. |
| Owned elsewhere | Paths in `CODEOWNERS` that belong to someone else. |
| Config | The package manifest, CI files, and build, lint and typecheck config (`tsconfig.json`, ESLint, ruff, …). |
| Migrations | Migration directories, ORM models, and the module that owns a storage format. |

## Linking, not copying

Interfaces & Data Contracts has two labelled lists, so the checker can verify them:

```markdown
Existing:

- `src/types.ts` (`Todo`): the shape of every todo; the export's fields come from here.

New:

- CLI: `todo export`, no arguments or flags.
- stdout: `Todo[]` as JSON, then a newline; nothing else.
```

- **Existing:** each item starts with the repo-relative path in backticks, then, where it helps, the symbols it defines in backticks inside parentheses: `` `src/types.ts` (`Todo`) `` or `` `src/store.ts:12` ``. Then a few words on why it matters ("the shape every todo has", "where `list` reads todos"). `check --repo` confirms each path exists and contains each symbol.
- **New:** each item states the contract the goal adds *in code*, in terms of the existing types: a signature, a type, a schema, or the CLI usage, in backticks or an indented fenced block in the repo's language. "A JSON array of todos" is prose; `` `Todo[]` as JSON `` is a contract a test and the type checker can hold the build to. A file the build will create goes here, by its future path.
- Never paste a file's contents, a type's fields or a schema into the spec. The file is the source of truth and will change; the link stays right.
- Update mode moves a `New:` item to `Existing:` once its file exists and states it (`update.md`).
