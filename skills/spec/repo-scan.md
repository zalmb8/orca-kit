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

## Linking, not copying

- Link each file by repo-relative path, adding a symbol or line where it helps: `` `src/types.ts` (`Todo`) `` or `` `src/store.ts:12` ``.
- Add a few words on why it matters ("the shape every todo has", "where `list` reads todos").
- Never paste a file's contents, a type's fields or a schema into the spec. The file is the source of truth and will change; the link stays right.
