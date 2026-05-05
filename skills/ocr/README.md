# ocr — Claude Code skill

Extract text from PDF files (scanned or digital) with smart routing across
four engines. Pages are processed in parallel.

## Why

Different PDFs need different tools:

- **Digital PDFs** (born-digital, with a text layer) — `pdftotext` extracts
  perfectly, instantly, free.
- **Clean scans** — `ocrmypdf` (tesseract under the hood, with deskew /
  preprocessing) is fast and free.
- **Damaged scans, historical type, weird layouts** — `tesseract` struggles;
  Claude Vision is accurate but costs money per page.

This skill auto-detects which path each PDF needs. By default it tries the
cheapest viable engine and only escalates when quality drops below a
configurable threshold.

## Engines

| Engine | Cost | Speed | When |
|--------|------|-------|------|
| `pdftotext` | free | instant | PDF has a usable text layer |
| `ocrmypdf` | free | fast | scan, but tesseract handles it (high probe confidence) |
| `tesseract` | free | fast | manual override; raw per-page tesseract without ocrmypdf preprocessing |
| `claude` | paid | slower | scan that local OCR can't read; needs `ANTHROPIC_API_KEY` |

`--engine auto` (default) picks for you. Force a specific engine with
`--engine pdftotext|ocrmypdf|tesseract|claude` to skip routing.

## Install

```bash
git clone https://github.com/sypianski/lertaro ~/lertaro
cd ~/lertaro
./install.sh ocr
```

The installer copies this directory into `~/.claude/skills/ocr/`, creates a
self-contained virtualenv at `~/.claude/skills/ocr/.venv` for the Python
dependencies, and rewrites the `scripts/ocr.py` shebang to use it. No
system-wide `pip` install.

### System dependencies

Required for every engine: `pdftoppm`, `pdfinfo`, `pdftotext`, `tesseract`.
Required additionally for the `ocrmypdf` engine: `ocrmypdf`.

| OS | Command |
|----|---------|
| Debian / Ubuntu | `sudo apt install tesseract-ocr ocrmypdf poppler-utils` |
| macOS (Homebrew) | `brew install tesseract ocrmypdf poppler` |
| Arch / Manjaro | `sudo pacman -S tesseract tesseract-data-eng ocrmypdf poppler` |

Add language packs as needed (e.g. `tesseract-ocr-pol`, `tesseract-ocr-deu`).
List installed languages with `tesseract --list-langs`.

### API key (only for the Claude Vision tier)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Not needed for `pdftotext`, `ocrmypdf`, or `tesseract` engines.

## Usage

```bash
ocr.py <input.pdf> [options]
```

See [`SKILL.md`](./SKILL.md) for the full flag list. Quick examples:

```bash
# auto-routing, default markdown output
ocr.py book.pdf

# Polish scan, JSON output, 8 parallel workers
ocr.py book.pdf --lang pol+eng --format json --jobs 8

# Force Claude Vision for a damaged historical scan
ocr.py manuscript.pdf --engine claude --lang lat+grc

# Subset of pages, one markdown file per page
ocr.py book.pdf --pages 50-60 --per-page

# Force pure pdftotext (skip OCR completely on a digital PDF)
ocr.py form.pdf --engine pdftotext
```

## How auto-routing works

```
            input.pdf
                │
                ▼
    sample N pages (default 3: first / middle / last)
                │
                ▼
    pdftotext yields ≥ 80 chars on majority of samples?
        ┌───────────┴───────────┐
       yes                      no
        │                       │
        ▼                       ▼
   pdftotext            pdftoppm split → tesseract probe
   (fast, free)         compute mean per-word confidence
                                │
                    ┌───────────┴───────────┐
              conf ≥ threshold        conf < threshold
                    │                       │
                    ▼                       ▼
                ocrmypdf             Claude Vision
           (--jobs N parallel)     (thread pool, ≤4)
                    │                       │
                    └───────► merge ◄───────┘
                                │
                                ▼
                          txt / md / json
```

The `--threshold` (default 70) is on the tesseract per-word confidence scale
(0-100). Lower it to keep more PDFs on the free local path; raise it to
escalate more aggressively to Claude Vision.

## Cost notes

The Claude Vision tier runs roughly $0.003–0.015 per page depending on image
size and model. Default model is `claude-sonnet-4-6`. Use
`--model claude-haiku-4-5` for cheaper / faster runs at slightly lower
accuracy, or `--model claude-opus-4-7` for the highest quality.

For the local engines (`pdftotext`, `ocrmypdf`, `tesseract`) there is zero
per-page cost.

## Troubleshooting

- **"missing required binaries: …"** — install system deps (see table above).
  The error names the binary and prints an OS-specific install hint.
- **"ANTHROPIC_API_KEY environment variable is required"** — export the key
  or pick a non-Claude engine.
- **Probe confidence is high but output is garbage** — the probe sample may
  not be representative; force `--engine claude` or lower `--threshold`.
- **Rate-limit errors during Claude path** — the thread pool is already
  capped at 4 workers, but bursts can still trip API rate limits. Retries
  with exponential backoff are built in; for persistent issues reduce
  `--jobs` further.
- **Output for a forced `--engine ocrmypdf` on a digital PDF looks weird**
  — `ocrmypdf` re-rasterizes and re-OCRs the page (`--redo-ocr`); for digital
  PDFs prefer `--engine pdftotext` or just let `--engine auto` route.

## License

MIT — see the repository [LICENSE](../LICENSE).
