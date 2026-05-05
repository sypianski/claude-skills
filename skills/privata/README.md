# privata — privacy-safe document processing

A Claude Code skill for analysing sensitive documents (book proposals,
unpublished manuscripts, confidential reports, friends' drafts) with
an LLM **without** the document body entering Claude Code's
conversation transcript and **without** risk of training-data
ingestion.

## What it does

1. **Quarantines** the document in `~/privata/` (mode 700).
2. **Denies** Claude Code's Read tool and the common Bash readers
   (`cat`, `head`, `tail`, `grep`, `less`, `find`, `ls`, etc.) on that
   directory via `~/.claude/settings.json` rules.
3. **Routes processing** through OpenRouter → Anthropic Claude in a
   subprocess script that the orchestrating agent only invokes — it
   never sees the file's contents, only the script's structured output.

The result: the agent can ask "what does this document say about X?"
by running an extractor, but it cannot read the raw document, so the
text never lands in the conversation transcript.

## Why this matters

- **Anthropic API:** does not train on commercial-tier inputs.
- **Free web UIs (claude.ai free, ChatGPT free, Gemini free):** *may*
  train. Avoid for sensitive material.
- **Claude Code session itself:** every `Read` / `cat` ships content
  into the conversation, retained per Anthropic policy. For genuinely
  sensitive material (someone else's unpublished work, NDA-bound docs)
  you don't want that. privata closes that gap.
- **OpenRouter:** Anthropic doesn't train on inputs, but OpenRouter
  retains prompts unless privacy mode is enabled at
  [openrouter.ai/settings/privacy](https://openrouter.ai/settings/privacy).
  **Toggle it off before using this skill.**

## Threat model — what privata does and does not protect against

✅ **Protects against:**
- accidental Read/grep of a confidential file leaking it into the
  Claude Code conversation transcript;
- LLM training on the document (if you set up OpenRouter privacy mode
  and use Anthropic / OpenAI API endpoints);
- routine LLM-agent footguns ("let me just read the file to see what's
  in it…").

❌ **Does NOT protect against:**
- a determined model bypassing Bash deny via `python3 -c "open(...)"`
  or other interpreter inlines (the deny list isn't exhaustive — file
  perms 700 are the real backstop);
- a malicious actor with shell access on your machine;
- deliberate misuse by you (e.g. running `cat ~/privata/file` outside
  Claude Code).

The skill instructs the agent **never** to invoke interpreter inlines
that would read quarantined files into context.

## Install

From the lertaro monorepo root:

```bash
./install.sh privata
```

The installer creates a virtualenv at `privata/.venv` and installs
`openai` (used as the OpenRouter client). Restart Claude Code or run
`/skills` to refresh.

## One-time setup

1. **Quarantine directory:**
   ```bash
   mkdir -p ~/privata
   chmod 700 ~/privata
   ```

2. **Add deny rules** to `~/.claude/settings.json`. The bundled
   `settings-deny.example.json` has a copy-paste-ready snippet — replace
   `<you>` with your actual username (the rules need both `~/privata/**`
   and the literal-resolved `/home/<you>/privata/**` form, since Claude
   Code does not expand `~` in deny patterns).

3. **OpenRouter privacy mode:** sign in at
   [openrouter.ai/settings/privacy](https://openrouter.ai/settings/privacy)
   and enable "Disable prompt logging". Without this, OpenRouter
   retains your prompts.

4. **OpenRouter API key:**
   ```bash
   export OPENROUTER_API_KEY=sk-or-v1-...
   # optional: export OPENROUTER_API_KEY_FALLBACK=sk-or-v1-... for quota fallback
   ```
   Drop this in your shell rc or a separate sourced file (the bundled
   extractor reads from the environment, not from disk directly).

5. **Write a prompt** for your document type. Copy
   `prompts/example.md` and edit it. The prompt defines the schema you
   want extracted; the bundled extractor is otherwise generic.

## Usage

```bash
# 1. Move the document in (don't read it)
mv /path/to/sensitive.docx ~/privata/proposal.docx

# 2. Convert to markdown if needed
python3 ~/.claude/skills/privata/scripts/docx_to_md.py ~/privata/proposal.docx

# 3. Extract — agent invokes this, but never sees the document body
python3 ~/.claude/skills/privata/scripts/extract.py \
    ~/privata/proposal.md \
    --prompt ~/.claude/skills/privata/prompts/your-prompt.md \
    --out ~/privata-out/findings.jsonl

# 4. Review the structured output (which lives outside ~/privata/)
jq -C . ~/privata-out/findings.jsonl | less -R
```

## Bundled files

| File | Purpose |
|---|---|
| `SKILL.md` | The skill itself — instructions for the agent. |
| `scripts/docx_to_md.py` | Pandoc wrapper, .docx → .md + media. |
| `scripts/extract.py` | OpenRouter-routed extractor; takes a doc + prompt file, emits text/JSONL. |
| `prompts/example.md` | Skeleton prompt — copy and customise per document type. |
| `requirements.txt` | Python deps (`openai`). |
| `settings-deny.example.json` | Copy-paste deny rules for `~/.claude/settings.json`. |

## License

MIT — see the [lertaro LICENSE](../LICENSE).
