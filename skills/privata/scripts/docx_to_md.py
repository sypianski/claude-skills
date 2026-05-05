#!/usr/bin/env python3
"""
docx_to_md.py — convert .docx to GitHub-flavored Markdown via pandoc.

Usage:
    python3 docx_to_md.py <input.docx> [-o output.md]

If -o is omitted, writes alongside input with .md extension.
Extracts embedded media into <stem>_media/ next to the output.
"""

import argparse
import pathlib
import shutil
import subprocess
import sys


def convert(src: pathlib.Path, dst: pathlib.Path) -> None:
    if not src.is_file():
        sys.exit(f"input not found: {src}")
    if shutil.which("pandoc") is None:
        sys.exit("pandoc not installed (apt install pandoc)")

    media_dir = dst.with_name(f"{dst.stem}_media")
    cmd = [
        "pandoc",
        str(src),
        "-f", "docx",
        "-t", "gfm",
        "--wrap=none",
        f"--extract-media={media_dir}",
        "-o", str(dst),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"pandoc failed:\n{res.stderr}")

    size = dst.stat().st_size
    print(f"wrote {dst} ({size} bytes)")
    if media_dir.exists():
        n = sum(1 for _ in media_dir.rglob("*") if _.is_file())
        if n:
            print(f"extracted {n} media file(s) → {media_dir}")
        else:
            media_dir.rmdir()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=pathlib.Path)
    ap.add_argument("-o", "--output", type=pathlib.Path)
    args = ap.parse_args()

    src = args.input.expanduser().resolve()
    dst = (args.output.expanduser() if args.output
           else src.with_suffix(".md")).resolve()
    convert(src, dst)


if __name__ == "__main__":
    main()
