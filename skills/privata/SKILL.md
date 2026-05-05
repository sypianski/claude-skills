---
name: privata
description: >
  Privacy-safe procedure for processing sensitive documents (book proposals,
  drafts, unpublished manuscripts, confidential reports) through an LLM
  without risk of training-data ingestion or Claude Code reading the file
  directly. Quarantines the document in ~/privata/ (Read denied in
  ~/.claude/settings.json), then routes processing through OpenRouter →
  Anthropic via a subprocess script Claude cannot directly invoke on the
  file's contents.
  Use when user says "process privately", "without LLM training",
  "sensitive document", "friend's draft", "confidential proposal", or
  invokes /privata.
---

# privata — privacy-safe document processing

For documents the user wants analyzed by an LLM but **not read by Claude
Code directly** and **not used for model training**.

## Threat model

- **Anthropic API:** does NOT train on commercial-tier inputs. ✓
- **OpenAI API:** does NOT train on API inputs. ✓
- **OpenRouter:** forwards to provider (good) BUT logs prompts unless
  the user enables privacy mode at
  [openrouter.ai/settings/privacy](https://openrouter.ai/settings/privacy).
- **Free web UIs (claude.ai free, ChatGPT free, Gemini free):** may
  train. ✗ Avoid.
- **Claude Code session itself:** every Read/Bash/cat sends content to
  Anthropic as part of the conversation transcript, retained per
  Anthropic policy. We want to AVOID this for sensitive docs — hence
  the quarantine + subprocess pattern below.

## Quarantine setup (one-time)

Two pieces:

### 1. Quarantine directory

```bash
mkdir -p ~/privata
chmod 700 ~/privata
```

### 2. Deny rules in `~/.claude/settings.json`

Block Read + the common shell readers for both `~/privata/*` and the
fully-resolved path. See `settings-deny.example.json` in this skill for
a copy-pasteable snippet (covers `Read`, `cat`, `head`, `tail`, `less`,
`more`, `grep`, `rg`, `find`, `ls`, `cp`, `mv` as bash patterns).

**Limitations.** Bash deny is best-effort. The model can route around
with `python3 -c "open(...)"`, `xxd`, `awk`, `sed`, etc. — not every
interpreter is listed. **Real safety = file perms (700) + the subprocess
discipline below + don't `cd` into `~/privata/` from Claude Code.**

## Procedure

### 1. Get the document into `~/privata/`

Move (don't read) it in:

```bash
mv /path/to/sensitive.docx ~/privata/<short_name>.docx
```

If downloading from email via the [`postero`](../postero) skill:

```bash
himalaya envelope list -a <account> | head -10
himalaya attachment download -a <account> <ID>
mv "/tmp/<original_name>" ~/privata/<short_name>.<ext>
```

### 2. Convert to .md if needed

For `.docx` / `.doc` / `.odt` sources:

```bash
python3 ~/.claude/skills/privata/scripts/docx_to_md.py ~/privata/<file>.docx
# → ~/privata/<file>.md  (+ ~/privata/<file>_media/ for images)
```

The bundled `docx_to_md.py` is a thin pandoc wrapper using `--wrap=none`
(one paragraph per line — easier for LLM ingestion) and extracts
embedded media into a sibling directory.

For `.pdf`: use `pdftotext` first (`pdftotext input.pdf input.txt`),
then feed the `.txt` into the extractor.

### 3. Extract via the bundled subprocess script (NOT via Claude tools)

```bash
python3 ~/.claude/skills/privata/scripts/extract.py ~/privata/<file>.md \
  --prompt ~/.claude/skills/privata/prompts/<your-prompt>.md \
  --out ~/privata-out/findings.jsonl
```

The script:
- Reads the document and a separate prompt file.
- POSTs both to OpenRouter (default model `anthropic/claude-opus-4.7`)
  as a subprocess — Claude Code's Bash tool only sees the script
  invocation, NOT the document text.
- Writes structured output (default: JSONL) to a path you choose,
  outside `~/privata/`.

### 4. Review output

```bash
wc -l ~/privata-out/findings.jsonl
jq -C . ~/privata-out/findings.jsonl | less -R
```

Output lives outside `~/privata/`, so Claude Code can read it normally.
**Caveat:** if your prompt instructs the model to emit verbatim quotes,
the output file is semi-sensitive — keep it out of public/git-tracked
directories.

## Customising the extractor for your domain

The bundled `extract.py` is generic — it takes a separate prompt file
via `--prompt`. Write one `.md` prompt per document type you process.

A prompt should:
- State who the document author/audience is.
- Define the schema you want extracted (recommend strict JSONL — one
  record per line — for easy downstream processing).
- List domain-specific rules ("flag ambiguous Arabic terms", "always
  emit empirical_claim for quantitative claims", etc.).
- Tell the model *not* to invent findings or include prose outside JSON.

Save prompts in `~/.claude/skills/privata/prompts/` (or anywhere — pass
`--prompt` to the script).

## Critical rules for Claude

1. **Never `cat`, `head`, `tail`, `grep`, `read` files in `~/privata/`** —
   deny rules exist but the principle stands even if a path slips
   through.
2. **Never invoke `python3 -c "..."` or similar interpreter inlines that
   would read `~/privata/` contents into Claude's context** — that
   defeats the entire purpose.
3. **The bundled subprocess scripts are the ONLY way to touch
   `~/privata/`.** They run as separate processes; their stdin/stdout
   passes through Claude only as bash-tool result text, but the document
   body never enters Claude's transcript.
4. If a script's output would echo the document content (e.g.
   `--verbose`), suppress it.
5. Output destination: write to a non-quarantined path the user nominates
   (default suggestion: `~/privata-out/`). Flag to user if the prompt
   schema includes verbatim quotes — they may not want the output
   committed to a git-tracked dir.

## Trigger phrases

- "process this privately"
- "don't read it but extract from it"
- "friend's unpublished proposal/draft/manuscript"
- "without using my data for training"
- "/privata"
- explicit mentions of `~/privata/`

## Bundled files

- `scripts/docx_to_md.py` — pandoc wrapper, .docx → .md + media.
- `scripts/extract.py` — OpenRouter-routed extractor, takes a prompt
  file + input doc, emits text/JSONL output.
- `prompts/example.md` — sample prompt skeleton; copy and customise per
  document type.
- `settings-deny.example.json` — copy-paste deny rules for
  `~/.claude/settings.json`.

## Known gotchas

- **OpenRouter privacy mode.** Default OpenRouter logs prompts. Toggle
  it off at openrouter.ai/settings/privacy *before* using this skill,
  or pick a different routing path.
- **Per-key rate caps.** OpenRouter has weekly per-key spend caps. The
  bundled `extract.py` reads `OPENROUTER_API_KEY` (and optional
  `OPENROUTER_API_KEY_FALLBACK`) and falls through to the fallback on
  403.
- **Move target vs source.** `mv ~/privata/* …` is blocked by deny
  rules (source path matches). `mv X ~/privata/` (target) is allowed.
- **`pandoc --wrap=none`** produces no hard wraps; preserves paragraph
  integrity for LLM ingestion.
- **Output may contain verbatim quotes** from the source — treat the
  output file as semi-sensitive (don't commit to public repos).
