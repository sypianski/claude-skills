# claude-skills

A collection of [Claude Code](https://docs.claude.com/en/docs/claude-code) skills I use day-to-day, sanitised and shared.

Each skill is a single `SKILL.md` in `skills/<name>/`. Drop it into `~/.claude/skills/<name>/` and Claude Code will pick it up next session.

## Skills

| Skill | Description |
|---|---|
| [`himalaya`](skills/himalaya/) | Read, search, and draft email via the [himalaya](https://pimalaya.org/himalaya/) CLI across multiple IMAP accounts. **Drafts only — never sends.** Replies thread correctly via `In-Reply-To` / `References`. Bodies are `multipart/alternative` with markdown rendered to HTML, so `**bold**` shows up bold in your recipient's mail client. |

## Install

Pick one skill and drop it in:

```bash
git clone https://github.com/<your-user>/claude-skills.git /tmp/claude-skills
cp -r /tmp/claude-skills/skills/himalaya ~/.claude/skills/himalaya
```

Or symlink, if you prefer to track upstream:

```bash
git clone https://github.com/<your-user>/claude-skills.git ~/src/claude-skills
ln -s ~/src/claude-skills/skills/himalaya ~/.claude/skills/himalaya
```

Then restart Claude Code (or start a new session) so the skill list reloads.

## Verify

In a Claude Code session:

```
/help
```

The skill should appear in the available-skills list. To invoke it explicitly:

```
/himalaya check inbox
```

## Per-skill setup

Some skills need external tools or per-machine config. Read the skill's own `SKILL.md` — required commands, env vars, and config files are listed there.

For `himalaya` specifically: you need the [`himalaya`](https://pimalaya.org/himalaya/) CLI configured at `~/.config/himalaya/config.toml` with at least one IMAP account, plus `python3 -m markdown` (or `pandoc`) for the markdown→HTML rendering step.

## Skills published elsewhere

Some of my skills live in their own repos rather than this collection:

- [`taskestro`](https://github.com/sypianski/taskestro) — parallel-task orchestration: parses `TODO.md`, creates a git worktree per task in `.worktrees/<slug>`, launches a tmux window running Claude Code per worktree, with a fish-side `task-monitor` companion for live status. Skill name in `~/.claude/skills/` is `task-orchestrator`.

## Contributing

Issues and PRs welcome. Sanitise before pushing — no real email addresses, secrets, or hostnames.

## License

[MIT](LICENSE).
