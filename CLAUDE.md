# orca-kit

A Claude Code plugin of personal skills and agents for driving AI software development workflows from Orca.

## Layout

- `.claude-plugin/plugin.json` — plugin manifest. Bump `version` on every user-facing change.
- `.claude-plugin/marketplace.json` — lets this repo be added as its own marketplace.
- `skills/<name>/SKILL.md` — one directory per skill; invoked as `orca-kit:<name>`.
- `agents/<name>.md` — subagent definitions.
- `templates/skill/` — copy this to start a new skill.

## Conventions

- Skill directory name == frontmatter `name`, lowercase and hyphenated.
- `description` says what the skill does *and* when to trigger it; it is the only thing Claude sees before loading.
- Keep SKILL.md focused; put long references or scripts next to it and point to them via `${CLAUDE_PLUGIN_ROOT}`.
- Skills that act in Orca should use the `orca` CLI rather than raw `git worktree` or ad hoc terminals.
