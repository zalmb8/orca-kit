# `todo list` output

One line per todo, in store order:

```
- [ ] <title>
- [x] <title>
```

`[x]` marks a completed todo. Nothing else is printed. Scripts may parse this
output; `integrations/standup/digest.ts` does.
