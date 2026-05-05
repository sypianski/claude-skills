# claude-skills

A collection of [Claude Code](https://docs.claude.com/en/docs/claude-code) skills I use day-to-day, sanitised and shared.

Each skill lives in `skills/<name>/`. Simple skills are a single `SKILL.md`; skills with Python dependencies also include a `scripts/` directory and `requirements.txt`.

## Skills

| Skill | Description |
|---|---|
| [`postero`](skills/postero/) | Read, search, and draft email via the [himalaya](https://pimalaya.org/himalaya/) CLI across multiple IMAP accounts. **Drafts only — never sends.** Replies thread correctly via `In-Reply-To` / `References`. Bodies are `multipart/alternative` with markdown rendered to HTML. |
| [`ocr`](skills/ocr/) | Extract text from PDF files (scanned or digital). Auto-routes across `pdftotext`, `tesseract`, `ocrmypdf`, and Claude Vision based on confidence. Parallelizes pages across CPU cores. |
| [`iloskolto`](skills/iloskolto/) | Tool-scout. Before building a new skill/CLI/plugin, spawns a background agent searching GitHub and the web for prior art so you can reuse instead of reinventing. Non-blocking. |
| [`privata`](skills/privata/) | Privacy-safe document processing. Quarantines sensitive docs in `~/privata/` (Read denied), routes analysis through OpenRouter → Anthropic via a subprocess so the document body never enters Claude Code's transcript. |

## Install

```bash
git clone https://github.com/sypianski/claude-skills ~/claude-skills
cd ~/claude-skills
chmod +x install.sh

./install.sh postero          # SKILL.md only — no deps
./install.sh ocr              # installs Python venv automatically
./install.sh iloskolto privata ocr   # multiple at once
```

Override the destination with `CLAUDE_SKILLS_DIR=/path/to/skills ./install.sh <skill>`.

For skills with a `requirements.txt`, the installer provisions a self-contained virtualenv at `~/.claude/skills/<skill>/.venv` and rewrites Python script shebangs to use it — no system-wide `pip` pollution.

> On Debian/Ubuntu, `python3 -m venv` may need `sudo apt install python3-venv python3-full`.

System dependencies are skill-specific — see each skill's `SKILL.md`.

## Manual install (single skill, no script)

```bash
cp -r skills/postero ~/.claude/skills/postero
```

Or symlink to track upstream:

```bash
ln -s "$PWD/skills/postero" ~/.claude/skills/postero
```

Then restart Claude Code (or start a new session).

## Verify

In a Claude Code session:

```
/help
```

The skill should appear in the available-skills list.

## Uninstall

```bash
rm -rf ~/.claude/skills/<skill-name>
```

## Skills published elsewhere

Some skills live in their own repos:

- [`taskestro`](https://github.com/sypianski/taskestro) — parallel-task orchestration: parses `TODO.md`, creates a git worktree per task, launches a tmux window running Claude Code per worktree, with a Fish-side `task-monitor` companion for live status. Skill name in `~/.claude/skills/` is `task-orchestrator`.

## Contributing

Issues and PRs welcome. Sanitise before pushing — no real email addresses, secrets, or hostnames.

## License

[MIT](LICENSE).
