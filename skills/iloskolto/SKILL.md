---
name: iloskolto
description: >
  Tool-scout (iloskolto). MUST run BEFORE building any new skill,
  slash-command, hook, CLI tool, helper script, plugin, MCP server, or
  reusable utility. Spawns a background agent that searches GitHub and
  the public web for existing similar projects so the user can reuse
  instead of reinventing. The main conversation continues building the
  requested tool in parallel — iloskolto never blocks. Findings are
  integrated only after the background agent returns.

  Auto-triggers semantically on intents like "make/build/create/scaffold
  a tool/skill/helper/plugin/CLI/wrapper/hook/command", "I need a script
  that …", "write me a utility for X", or invocation of /iloskolto.
  Also fires on equivalent phrasings in other languages (e.g. Polish
  "stwórz/zrób/napisz", Esperanto "kreu ilon").

  Does NOT trigger for: editing/fixing/refactoring an existing tool,
  one-off shell commands, project-internal code, throwaway snippets,
  pure config changes.
---

# iloskolto — tool scout

`ilo` (tool) + `skolto` (scout) in Esperanto. Runs reconnaissance for
existing tools before you build a new one. Reuse beats reinvention.

## When to fire

Fire on **reusable, standalone tooling** the user wants created from
scratch:

- Claude Code skills (`SKILL.md` projects)
- Slash commands, hooks, MCP servers, plugins
- CLI utilities, wrapper scripts, helper libraries
- Browser extensions, bots, daemons

Skip on:

- editing/extending an existing tool the user already has
- bug fixes, refactors, renames
- ad-hoc one-liners, project-internal glue, throwaway scripts
- pure config changes (dotfiles, settings, env)

If unsure → fire. Background, non-blocking, cheap to be wrong.

## Procedure

When the trigger fires, the main agent does TWO things **in parallel**:

### 1. Spawn the recon (background, non-blocking)

Use the `Agent` tool with `subagent_type=general-purpose` (web access
needed) and `run_in_background=true`. Pass a self-contained prompt like:

```
Recon for an existing tool that solves: <one-sentence summary of what
the user wants to build>.

Search:
1. GitHub: if `gh` CLI is available and authenticated, run
   `gh search repos <keywords> --limit 10 --sort stars` and
   `gh search code <keywords> --limit 10`.
   Otherwise WebSearch "<keywords> site:github.com".
2. Web: WebSearch "<keywords> github", "<keywords> claude code skill",
   "<keywords> CLI tool", "<keywords> awesome list".
3. Local: check ~/.claude/skills/, ~/.claude/plugins/, and any
   user-configured skill directories for an existing match.

For each candidate report: name, URL, ★ stars (if known), one-line
summary, last activity date, and how closely it matches the user's
intent (exact / partial / tangential).

Verdict line at the end:
  REUSE: <name> — <url>          (mature, fits exactly)
  ADAPT: <name> — <url>          (close, may need a fork/wrapper)
  INSPIRE: <name> — <url>        (worth reading before writing)
  NONE                           (no useful prior art found)

Keep the report under 300 words.
```

### 2. Continue building the user's tool

Do NOT wait for recon. Begin scaffolding/implementing immediately. The
user explicitly asked to build it; recon is advisory.

## When recon returns

The background agent finishes via a system notification. Then:

- **REUSE** → pause implementation, surface to user with: name, link,
  why it fits. Ask "use this instead / fork it / build anyway?"
- **ADAPT** → mention briefly, keep building, note the prior art as a
  reference the user might fork later.
- **INSPIRE** → mention briefly, keep building, optionally read the
  candidate's README for ideas.
- **NONE** → silent. No clutter. Continue.

If the implementation is already finished by the time recon returns and
the verdict is REUSE/ADAPT, still surface — user may want to delete and
switch.

## Keyword extraction

When forming search keywords, drop:

- generic words: "tool", "skill", "script", "helper", "utility"
- non-English framing if present (translate to English for search)
- the user's project-specific names

Keep: domain nouns, verbs describing the action, target file types,
target services/APIs.

Example — user says: "build a skill that scrapes recipe PDFs and
imports them to mealie". Keywords: `recipe pdf scraper mealie import`.

## Cost guard

Best-effort: one bg recon per "create new tool" intent per
conversation. If the user asks for several tools in sequence, batch
them into a single recon prompt rather than spawning N agents.
