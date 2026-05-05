# iloskolto — tool scout for Claude Code

`ilo` (tool) + `skolto` (scout) — Esperanto for *tool scout*. A skill
that fires **before** you build a new tool, scouts GitHub + the web for
existing prior art in the background, and surfaces matches without
blocking your build.

## Why

Most "I need a script that…" requests already have a mature
implementation on GitHub. Without recon, agents happily reinvent the
wheel. iloskolto runs the recon in parallel so:

- you don't block waiting for search results,
- if a perfect match exists, you hear about it,
- if nothing exists, no clutter in the conversation.

## What it does

When the user asks for a new skill / CLI / hook / plugin / MCP server
/ wrapper script, the main agent:

1. Spawns a **background** recon agent (`Agent` tool with
   `run_in_background=true`) that searches GitHub via `gh search`
   (with WebSearch fallback), the public web, and local skill
   directories.
2. Continues scaffolding the user's tool **in parallel** — recon never
   blocks.
3. When recon returns, the agent integrates the verdict:

   | Verdict   | Action |
   |-----------|--------|
   | `REUSE`   | Pause; surface to user; ask reuse vs fork vs build anyway. |
   | `ADAPT`   | Mention briefly as a reference, keep building. |
   | `INSPIRE` | Mention briefly, optionally read README, keep building. |
   | `NONE`    | Silent. No clutter. |

## Triggers

Fires on intents like:

- "make/build/create a tool/skill/helper/plugin/CLI"
- "scaffold a CLI for X"
- "write a wrapper for Y"
- "I need a script that …"
- explicit `/iloskolto`
- equivalent phrasings in other languages (Polish, Esperanto, etc.)

Skips on: editing/fixing/refactoring existing tools, one-off shell
commands, project-internal code, throwaway snippets, pure config
changes.

## Install

From the lertaro monorepo root:

```bash
./install.sh iloskolto
```

This copies the skill to `~/.claude/skills/iloskolto/`. Restart Claude
Code or run `/skills` to refresh.

Override the install location with `CLAUDE_SKILLS_DIR=/path ./install.sh
iloskolto`.

## Dependencies

- **Optional but recommended:** [`gh`](https://cli.github.com/) CLI,
  authenticated (`gh auth login`). Without it, the recon falls back to
  WebSearch only.
- No Python deps. No system packages.

## Example

User: *"Build a skill that scrapes recipe PDFs and pushes them to
mealie."*

Main agent (in parallel):

1. Spawns bg recon with keywords `recipe pdf scraper mealie import`.
2. Starts scaffolding `recetageto/` with `SKILL.md`, `scripts/`, etc.

Bg recon returns ~30s later:

```
ADAPT: mealie-recipe-importer — github.com/.../mealie-recipe-importer
  ★ 412 — Python CLI, scrapes recipe sites + PDFs, pushes via mealie API.
  Last commit: 2 weeks ago. Match: partial — does sites well, PDF flow thin.

Verdict: ADAPT
```

Main agent surfaces: *"Found mealie-recipe-importer (★412) — strong on
site scraping, weaker on PDFs. Worth forking for the API layer; I'll
keep building the PDF-first scaffold and reference it."*

## Cost guard

Best-effort: one background recon per "create new tool" intent per
conversation. Multiple tool requests in one turn → batched into a
single recon prompt.

## License

MIT — see the [lertaro LICENSE](../LICENSE).
