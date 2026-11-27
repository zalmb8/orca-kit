# orca-kit

A Claude Code plugin of personal skills and agents for driving AI software development workflows from Orca.

## Layout

- `.claude-plugin/plugin.json` — plugin manifest. Bump `version` on every user-facing change.
- `.claude-plugin/marketplace.json` — lets this repo be added as its own marketplace.
- `skills/<name>/SKILL.md` — one directory per skill; invoked as `orca-kit:<name>`.
- `agents/<name>.md` — subagent definitions.
- `templates/skill/` — copy this to start a new skill.
- `docs/<skill>/` — design and implementation plan for each skill (e.g. `docs/spec/ROADMAP.md`).
- `skills/spec/check` and `skills/spec/tests/` — the spec checker and its tests: `python3 -m unittest discover -s skills/spec/tests`.
- `skills/spec-review/gate`, `skills/spec-review/findings`, `skills/spec-review/record` and `skills/spec-review/tests/` — the hard gates and risk tiering (`gate --risk`), the findings and review-record validators, and their tests: `python3 -m unittest discover -s skills/spec-review/tests`.

## Conventions

- Skill directory name == frontmatter `name`, lowercase and hyphenated.
- `description` says what the skill does *and* when to trigger it; it is the only thing Claude sees before loading.
- Keep SKILL.md focused; put long references or scripts next to it and point to them via `${CLAUDE_PLUGIN_ROOT}`.
- Skills that act in Orca should use the `orca` CLI rather than raw `git worktree` or ad hoc terminals.
