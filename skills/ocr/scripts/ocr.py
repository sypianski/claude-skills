#!/usr/bin/env python3
"""
ocr — extract text from PDF with auto-routing between local OCR
(tesseract/ocrmypdf) and Claude Vision.

Part of the lertaro skills monorepo. See SKILL.md for full docs.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as futures
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


# -- system dependency detection ---------------------------------------------

INSTALL_HINTS = {
    "Linux": (
        "Debian/Ubuntu: sudo apt install tesseract-ocr ocrmypdf poppler-utils\n"
        "  Arch:           sudo pacman -S tesseract tesseract-data-eng ocrmypdf poppler"
    ),
    "Darwin": "brew install tesseract ocrmypdf poppler",
}


def require_binaries(*names: str) -> None:
    missing = [n for n in names if shutil.which(n) is None]
    if not missing:
        return
    hint = INSTALL_HINTS.get(platform.system(), "install via your package manager")
    sys.exit(
        f"error: missing required binaries: {', '.join(missing)}\n"
        f"install with:\n  {hint}"
    )


# -- page range parsing ------------------------------------------------------

def parse_pages(spec: str | None, total: int) -> list[int]:
    """Parse '5-20' or '5,7,10' or '5-7,12' into a sorted list of 1-indexed pages."""
    if not spec:
        return list(range(1, total + 1))
    out: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            for i in range(int(a), int(b) + 1):
                out.add(i)
        else:
            out.add(int(chunk))
    pages = sorted(p for p in out if 1 <= p <= total)
    if not pages:
        sys.exit(f"error: --pages '{spec}' resolved to no valid pages (1..{total})")
    return pages


# -- pdf operations ----------------------------------------------------------

def pdf_page_count(pdf: Path) -> int:
    out = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
    m = re.search(r"^Pages:\s+(\d+)", out, flags=re.MULTILINE)
    if not m:
        sys.exit(f"error: could not determine page count of {pdf}")
    return int(m.group(1))


def split_pdf(pdf: Path, pages: list[int], dpi: int, tmpdir: Path) -> dict[int, Path]:
    """Render selected pages to PNG via pdftoppm. Returns {page_num: png_path}."""
    out: dict[int, Path] = {}
    contiguous_groups: list[tuple[int, int]] = []
    start = pages[0]
    prev = pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            contiguous_groups.append((start, prev))
            start = p
            prev = p
    contiguous_groups.append((start, prev))

    for first, last in contiguous_groups:
        prefix = tmpdir / "page"
        subprocess.run(
            [
                "pdftoppm",
                "-r", str(dpi),
                "-f", str(first),
                "-l", str(last),
                "-png",
                str(pdf),
                str(prefix),
            ],
            check=True,
            capture_output=True,
        )

    width = max(3, len(str(max(pages))))
    for p in pages:
        candidates = [
            tmpdir / f"page-{str(p).zfill(width)}.png",
            tmpdir / f"page-{p}.png",
        ]
        for c in candidates:
            if c.exists():
                out[p] = c
                break
        else:
            existing = sorted(tmpdir.glob("page-*.png"))
            if existing:
                pat = re.compile(r"page-0*(\d+)\.png$")
                for f in existing:
                    m = pat.search(f.name)
                    if m and int(m.group(1)) == p:
                        out[p] = f
                        break
        if p not in out:
            sys.exit(f"error: pdftoppm did not produce a PNG for page {p}")
    return out


# -- probe / confidence ------------------------------------------------------

def probe_confidence(png: Path, lang: str) -> float:
    """Run tesseract in TSV mode and return mean per-word confidence (0-100)."""
    try:
        proc = subprocess.run(
            ["tesseract", str(png), "-", "-l", lang, "tsv"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"warning: tesseract failed on {png.name}: {e.stderr.strip()}",
              file=sys.stderr)
        return 0.0

    confs: list[int] = []
    for line in proc.stdout.splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) < 12:
            continue
        try:
            c = int(cols[10])
            text = cols[11]
        except (ValueError, IndexError):
            continue
        if c >= 0 and text.strip():
            confs.append(c)
    if not confs:
        return 0.0
    return sum(confs) / len(confs)


def probe_sample_indices(pages: list[int], n: int) -> list[int]:
    if len(pages) <= n:
        return list(pages)
    if n == 1:
        return [pages[len(pages) // 2]]
    if n == 2:
        return [pages[0], pages[-1]]
    step = (len(pages) - 1) / (n - 1)
    idxs = sorted({round(i * step) for i in range(n)})
    return [pages[i] for i in idxs]


# -- engines -----------------------------------------------------------------

@dataclass
class PageResult:
    page: int
    text: str
    confidence: float
    engine: str


def detect_digital(pdf: Path, sample_pages: list[int], min_chars: int = 80) -> bool:
    """Heuristic: does the PDF have an extractable text layer on most sample pages?"""
    hits = 0
    for p in sample_pages:
        proc = subprocess.run(
            ["pdftotext", "-f", str(p), "-l", str(p), str(pdf), "-"],
            capture_output=True, text=True,
        )
        if proc.returncode == 0 and len(proc.stdout.strip()) >= min_chars:
            hits += 1
    return hits * 2 > len(sample_pages)


def run_pdftotext(pdf: Path, pages: list[int]) -> list[PageResult]:
    results: list[PageResult] = []
    for p in pages:
        proc = subprocess.run(
            ["pdftotext", "-layout", "-f", str(p), "-l", str(p), str(pdf), "-"],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            results.append(PageResult(p, "", 0.0, "pdftotext"))
            continue
        results.append(PageResult(p, proc.stdout.rstrip() + "\n", -1.0, "pdftotext"))
    return results


def run_tesseract_pages(
    pngs: dict[int, Path], lang: str, jobs: int
) -> list[PageResult]:
    def worker(item: tuple[int, Path]) -> PageResult:
        page, png = item
        proc = subprocess.run(
            ["tesseract", str(png), "-", "-l", lang],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            return PageResult(page, "", 0.0, "tesseract")
        return PageResult(page, proc.stdout.rstrip() + "\n", -1.0, "tesseract")

    results: list[PageResult] = []
    with futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        for r in ex.map(worker, sorted(pngs.items())):
            results.append(r)
    results.sort(key=lambda x: x.page)
    return results


def run_ocrmypdf(
    pdf: Path, pages: list[int], total_pages: int, lang: str, jobs: int, tmpdir: Path
) -> list[PageResult]:
    sidecar = tmpdir / "sidecar.txt"
    cmd = [
        "ocrmypdf",
        "--jobs", str(jobs),
        "--language", lang,
        "--sidecar", str(sidecar),
        "--output-type", "none",
        "--redo-ocr",  # always run OCR; ignore any existing text layer
        "--quiet",
    ]
    if pages != list(range(1, total_pages + 1)):
        cmd += ["--pages", ",".join(str(p) for p in pages)]
    cmd += [str(pdf), "-"]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    # exit 0 = ok; 6 = invalid input pdf; 10 = ok but warnings
    if proc.returncode not in (0, 10):
        sys.exit(
            f"error: ocrmypdf failed (exit {proc.returncode}):\n{proc.stderr}"
        )
    if not sidecar.exists():
        sys.exit("error: ocrmypdf did not produce a sidecar text file")

    raw = sidecar.read_text(encoding="utf-8", errors="replace")
    chunks = raw.split("\f")
    # ocrmypdf emits one chunk per PDF page (all pages, even skipped).
    # Strip "[OCR skipped on page(s) ...]" markers added for non-targeted pages.
    skip_re = re.compile(r"\[OCR skipped on page\(s\)[^\]]*\]\s*")
    cleaned = [skip_re.sub("", c).rstrip() for c in chunks]

    results: list[PageResult] = []
    if len(cleaned) >= total_pages:
        # Sidecar is aligned to full PDF: index by page number.
        for p in pages:
            text = cleaned[p - 1] if p - 1 < len(cleaned) else ""
            results.append(PageResult(p, text + "\n", -1.0, "ocrmypdf"))
    elif len(cleaned) == len(pages):
        for p, text in zip(pages, cleaned):
            results.append(PageResult(p, text + "\n", -1.0, "ocrmypdf"))
    else:
        # Fallback: dump everything into the first requested page.
        joined = "\n\n".join(c for c in cleaned if c).rstrip() + "\n"
        results.append(PageResult(pages[0], joined, -1.0, "ocrmypdf"))
        for p in pages[1:]:
            results.append(PageResult(p, "", -1.0, "ocrmypdf"))
    return results


# -- Claude Vision (inline; lazy-imported deps) ------------------------------

class ClaudeVisionOCR:
    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, model: str | None = None):
        try:
            import anthropic  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError as e:
            sys.exit(
                "error: Claude Vision tier requires the 'anthropic' and 'pillow' "
                f"packages. Install with: pip install -r requirements.txt\n  ({e})"
            )
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit(
                "error: ANTHROPIC_API_KEY environment variable is required for the "
                "Claude Vision tier. Export it or pick a non-claude engine."
            )
        import anthropic
        self.client = anthropic.Anthropic()
        self.model = model or self.DEFAULT_MODEL

    def ocr_image(self, png: Path, lang_hint: str | None = None) -> str:
        from PIL import Image

        with Image.open(png) as img:
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            data = base64.standard_b64encode(buf.getvalue()).decode("ascii")

        prompt = (
            "Extract all text from this image exactly as it appears. "
            "Preserve formatting, line breaks, and structure. "
            "Include all visible text. "
        )
        if lang_hint:
            prompt += f"The text is in {lang_hint}. "
        prompt += "\n\nProvide ONLY the extracted text, no commentary."

        last_err: Exception | None = None
        for attempt in range(3):
            try:
                msg = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": data,
                                    },
                                },
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                )
                return "".join(
                    block.text for block in msg.content if hasattr(block, "text")
                )
            except Exception as e:
                last_err = e
                time.sleep(1.5 * (2 ** attempt))
        raise RuntimeError(f"Claude Vision failed after 3 retries: {last_err}")


def lang_hint_from_codes(codes: str) -> str:
    mapping = {
        "eng": "English", "pol": "Polish", "deu": "German", "fra": "French",
        "rus": "Russian", "ara": "Arabic", "grc": "Ancient Greek",
        "lat": "Latin", "lit": "Lithuanian", "bel": "Belarusian",
        "spa": "Spanish", "ita": "Italian", "nld": "Dutch", "por": "Portuguese",
    }
    parts = [mapping.get(c, c) for c in codes.split("+")]
    return " and ".join(parts)


def run_claude_pages(
    pngs: dict[int, Path], lang: str, jobs: int, model: str | None
) -> list[PageResult]:
    engine = ClaudeVisionOCR(model=model)
    hint = lang_hint_from_codes(lang)
    workers = max(1, min(jobs, 4))

    def worker(item: tuple[int, Path]) -> PageResult:
        page, png = item
        try:
            text = engine.ocr_image(png, lang_hint=hint)
        except Exception as e:
            print(f"warning: Claude Vision failed on page {page}: {e}",
                  file=sys.stderr)
            text = ""
        return PageResult(page, text.rstrip() + "\n", -1.0, "claude")

    results: list[PageResult] = []
    with futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(worker, sorted(pngs.items())):
            results.append(r)
    results.sort(key=lambda x: x.page)
    return results


# -- output ------------------------------------------------------------------

def write_output(
    results: list[PageResult],
    out_dir: Path,
    fmt: str,
    per_page: bool,
    pdf_stem: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    if per_page:
        for r in results:
            ext = "json" if fmt == "json" else ("md" if fmt == "md" else "txt")
            path = out_dir / f"page-{r.page:04d}.{ext}"
            if fmt == "json":
                path.write_text(json.dumps(_result_dict(r), ensure_ascii=False, indent=2))
            elif fmt == "md":
                path.write_text(f"## Page {r.page}\n\n{r.text}\n")
            else:
                path.write_text(r.text)
        return

    if fmt == "json":
        path = out_dir / f"{pdf_stem}.json"
        path.write_text(
            json.dumps([_result_dict(r) for r in results], ensure_ascii=False, indent=2)
        )
    elif fmt == "md":
        path = out_dir / f"{pdf_stem}.md"
        body = "\n\n".join(f"## Page {r.page}\n\n{r.text.rstrip()}" for r in results)
        path.write_text(body + "\n")
    else:  # txt
        path = out_dir / f"{pdf_stem}.txt"
        path.write_text("\f".join(r.text for r in results))
    print(f"wrote: {path}")


def _result_dict(r: PageResult) -> dict:
    d = {"page": r.page, "text": r.text, "engine": r.engine}
    if r.confidence >= 0:
        d["confidence"] = round(r.confidence, 1)
    return d


# -- main --------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        prog="ocr",
        description="Extract text from PDF with auto-routing between local OCR and Claude Vision.",
    )
    ap.add_argument("pdf", type=Path, help="Input PDF path")
    ap.add_argument("--out", type=Path, default=None,
                    help="Output directory (default: ./<basename>-ocr/)")
    ap.add_argument("--lang", default="eng",
                    help="Tesseract language codes, e.g. pol+eng (default: eng)")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--engine",
                    choices=["auto", "pdftotext", "tesseract", "ocrmypdf", "claude"],
                    default="auto")
    ap.add_argument("--threshold", type=int, default=70,
                    help="Probe confidence threshold 0-100 (default: 70)")
    ap.add_argument("--format", dest="fmt",
                    choices=["txt", "md", "json"], default="md")
    ap.add_argument("--per-page", action="store_true")
    ap.add_argument("--pages", default=None,
                    help="Page range, e.g. 5-20 or 5,7,10 (default: all)")
    ap.add_argument("--probe-sample", type=int, default=3)
    ap.add_argument("--keep-temp", action="store_true")
    ap.add_argument("--model", default=None,
                    help=f"Claude model (default: {ClaudeVisionOCR.DEFAULT_MODEL})")
    ap.add_argument("--dpi", type=int, default=300,
                    help="Render DPI for split (default: 300)")
    args = ap.parse_args()

    pdf = args.pdf.expanduser().resolve()
    if not pdf.is_file():
        sys.exit(f"error: file not found: {pdf}")

    require_binaries("pdftoppm", "pdfinfo", "pdftotext", "tesseract")
    if args.engine in ("auto", "ocrmypdf"):
        require_binaries("ocrmypdf")

    total = pdf_page_count(pdf)
    pages = parse_pages(args.pages, total)
    print(f"PDF: {pdf.name} ({total} pages, processing {len(pages)})")

    out_dir = args.out or Path.cwd() / f"{pdf.stem}-ocr"

    tmpdir = Path(tempfile.mkdtemp(prefix="ocr-"))
    try:
        if args.engine == "auto":
            sample = probe_sample_indices(pages, args.probe_sample)
            print(f"checking text layer on {len(sample)} sample page(s) ...")
            if detect_digital(pdf, sample):
                engine = "pdftotext"
                print(f"router → pdftotext (digital text layer detected)")
            else:
                print(f"splitting at {args.dpi} DPI ...")
                pngs = split_pdf(pdf, pages, args.dpi, tmpdir)
                print(f"probing {len(sample)} sample page(s) with tesseract ...")
                confs = [probe_confidence(pngs[p], args.lang) for p in sample]
                mean = sum(confs) / len(confs) if confs else 0.0
                print(f"probe: {[round(c, 1) for c in confs]}  mean={mean:.1f}")
                engine = "ocrmypdf" if mean >= args.threshold else "claude"
                print(f"router → {engine} (threshold={args.threshold})")
        else:
            engine = args.engine
            print(f"engine: {engine} (forced)")

        if engine == "pdftotext":
            results = run_pdftotext(pdf, pages)
        elif engine == "ocrmypdf":
            results = run_ocrmypdf(pdf, pages, total, args.lang, args.jobs, tmpdir)
        elif engine in ("tesseract", "claude"):
            if "pngs" not in locals():
                print(f"splitting at {args.dpi} DPI ...")
                pngs = split_pdf(pdf, pages, args.dpi, tmpdir)
            if engine == "tesseract":
                results = run_tesseract_pages(pngs, args.lang, args.jobs)
            else:
                results = run_claude_pages(pngs, args.lang, args.jobs, args.model)
        else:
            sys.exit(f"error: unknown engine '{engine}'")

        write_output(results, out_dir, args.fmt, args.per_page, pdf.stem)

    finally:
        if args.keep_temp:
            print(f"kept temp dir: {tmpdir}")
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
