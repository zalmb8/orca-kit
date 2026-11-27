# orca-kit

A Claude Code plugin with the skills and agents an engineer needs to drive AI software development workflows from [Orca](https://github.com/stablyai/orca).

## Install

```text
/plugin marketplace add zalmb8/orca-kit
/plugin install orca-kit@orca-kit
```

For local development, point Claude Code at a checkout instead:

```text
claude --plugin-dir ~/Projects/orca-kit
```

## Skills

Add one by copying `templates/skill/` to `skills/<name>/`.

| Skill | What it does |
| ----- | ------------ |
| `orca-kit:spec` | Writes and maintains specs at `specs/<slug>.md`: captures an idea, refines it into a draft or accepted spec, and syncs discoveries back. See [`docs/spec/ROADMAP.md`](docs/spec/ROADMAP.md). |

## License

MIT
