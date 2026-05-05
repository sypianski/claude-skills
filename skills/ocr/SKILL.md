---
name: ocr
description: >
  Extract text from PDF files (scanned or digital) with auto-routing across
  four engines: pdftotext (digital text layer), tesseract, ocrmypdf, and
  Claude Vision. The router first checks for a usable text layer; if absent,
  it probes tesseract confidence on a page sample and either runs ocrmypdf
  locally or escalates to Claude Vision. Parallelizes pages across CPU cores.
  Output formats: txt, md, json. Per-page or merged.

  Use when the user asks to "OCR this PDF", "extract text from a scan",
  "read this PDF", "convert PDF to markdown / text", or invokes /ocr.
  Auto-triggers when the user supplies a PDF and asks for its text content.
---

# OCR skill

Extract text from PDF documents. The skill picks the cheapest engine that
gets the job done:

1. If the PDF has a usable text layer, use `pdftotext` (free, instant).
2. Otherwise sample a few pages with tesseract, measure confidence, and either
3. continue with `ocrmypdf` (free, fast) for clean scans, or
4. escalate to Claude Vision (paid, accurate) for damaged / low-quality scans.

## Usage

```
python3 SCRIPT_DIR/scripts/ocr.py <input.pdf> [options]
```

`SCRIPT_DIR` is `~/.claude/skills/ocr` after install. The script is
self-contained — invoke it directly. Common options:

| Flag | Meaning |
|------|---------|
| `--out DIR` | Output directory (default: `./<basename>-ocr/`) |
| `--lang CODES` | Tesseract language codes, e.g. `pol+eng` (default: `eng`) |
| `--jobs N` | Parallelism (default: `nproc`) |
| `--engine MODE` | `auto` \| `pdftotext` \| `tesseract` \| `ocrmypdf` \| `claude` (default: `auto`) |
| `--threshold INT` | Probe confidence threshold 0-100 (default: 70) |
| `--format FMT` | `txt` \| `md` \| `json` (default: `md`) |
| `--per-page` | Write one file per page instead of merging |
| `--pages RANGE` | e.g. `5-20` or `5,7,10` |
| `--probe-sample N` | Pages to probe (default: 3) |
| `--keep-temp` | Keep extracted PNGs for debugging |
| `--model NAME` | Claude model for vision tier (default: `claude-sonnet-4-6`) |

## How routing works

1. Sample N pages (default 3: first / middle / last).
2. Run `pdftotext` on each sample. If the majority yield ≥ 80 chars,
   the PDF is treated as digital → use `pdftotext` end-to-end.
3. Otherwise: split selected pages to PNG at 300 DPI via `pdftoppm`, probe
   the same sample with tesseract, compute mean per-word confidence (0-100).
4. If `--engine auto`:
   - mean ≥ `--threshold` → run `ocrmypdf` for the whole PDF
     (its `--jobs` parallelizes pages natively; `--redo-ocr` ignores any
     stale text layer so the sidecar always reflects fresh OCR).
   - mean < `--threshold` → fan out per-page PNGs to Claude Vision via a
     thread pool (capped at 4 workers for API rate limits, with retries on
     transient errors).
5. Merge output according to `--format`.

If `--engine` is set to a specific engine, both the digital-detection and
probe steps are skipped.

## Examples

```bash
# auto-routing, defaults
ocr.py book.pdf

# Polish + English scan, output JSON, 8 workers
ocr.py book.pdf --lang pol+eng --format json --jobs 8

# Force Claude Vision for an old scan
ocr.py oldscan.pdf --engine claude --lang lat+grc

# Force pdftotext (skip OCR entirely, for digital PDFs)
ocr.py form.pdf --engine pdftotext

# Force ocrmypdf locally (will re-OCR even if a text layer exists)
ocr.py form.pdf --engine ocrmypdf

# Subset of pages, per-page markdown output
ocr.py book.pdf --pages 50-60 --format md --per-page
```

## Requirements

System binaries (always required: `pdftoppm`, `pdfinfo`, `pdftotext`,
`tesseract`. Additionally `ocrmypdf` for the auto / ocrmypdf engines):

- Debian/Ubuntu: `sudo apt install tesseract-ocr ocrmypdf poppler-utils`
- macOS: `brew install tesseract ocrmypdf poppler`
- Arch: `sudo pacman -S tesseract tesseract-data-eng ocrmypdf poppler`

Plus the language packs you need (e.g. `tesseract-ocr-pol`, `tesseract-ocr-deu`).

Python:

```
pip install -r requirements.txt   # anthropic, pillow
```

Environment (only required for the Claude Vision tier):

```
export ANTHROPIC_API_KEY=sk-ant-...
```

The `auto`, `tesseract`, and `ocrmypdf` engines work without an API key.

## Boundaries

- **PDF input only** in v1. For raw images, convert first
  (`img2pdf img.jpg -o img.pdf`).
- **Whole-PDF routing**, not per-page. A PDF that mixes clean and damaged
  pages is routed by the digital-detection / probe sample average.
- **No batch directory mode** — pass one file at a time.
- The Claude Vision tier costs money. The router only escalates when local
  OCR confidence is below the threshold; force `--engine pdftotext` or
  `--engine ocrmypdf` if you never want to call the API.
