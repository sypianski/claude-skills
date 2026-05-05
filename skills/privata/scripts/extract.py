#!/usr/bin/env python3
"""
extract.py — privacy-safe extraction from a document via OpenRouter → Anthropic.

Reads a quarantined source document and a separate prompt file, POSTs
both to OpenRouter, and writes the model's response to a chosen output
path. The orchestrating Claude Code session sees only this script's
invocation; it does NOT see the document body.

PRIVACY: enable "Disable prompt logging" in OpenRouter account settings
(https://openrouter.ai/settings/privacy) — otherwise OpenRouter retains
prompts even though Anthropic does not train on API inputs.

Usage:
    python3 extract.py <input.md> --prompt <prompt.md> [--out <output>] \
        [--model anthropic/claude-opus-4.7]

Environment:
    OPENROUTER_API_KEY           primary key
    OPENROUTER_API_KEY_FALLBACK  optional second key, tried on 403/quota errors
"""

import argparse
import os
import pathlib
import sys

try:
    from openai import OpenAI
except ImportError:
    sys.exit(
        "missing dependency: openai\n"
        "install with: pip install openai"
    )


def load_keys() -> list[tuple[str, str]]:
    """Return [(name, key), ...] in priority order, no duplicates."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in ("OPENROUTER_API_KEY", "OPENROUTER_API_KEY_FALLBACK"):
        val = os.environ.get(name)
        if val and val not in seen:
            out.append((name, val))
            seen.add(val)
    if not out:
        sys.exit(
            "no OpenRouter key found.\n"
            "set OPENROUTER_API_KEY (and optionally OPENROUTER_API_KEY_FALLBACK)"
        )
    return out


def extract(src: pathlib.Path, prompt_file: pathlib.Path,
            out: pathlib.Path, model: str) -> None:
    if not src.is_file():
        sys.exit(f"input not found: {src}")
    if not prompt_file.is_file():
        sys.exit(f"prompt file not found: {prompt_file}")

    text = src.read_text(encoding="utf-8")
    if not text.strip():
        sys.exit(f"empty file: {src}")
    system_prompt = prompt_file.read_text(encoding="utf-8")

    keys = load_keys()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            "Below is the full document. Analyze it per the system instructions.\n\n"
            "--- DOCUMENT START ---\n"
            f"{text}\n"
            "--- DOCUMENT END ---"
        )},
    ]

    last_err: Exception | None = None
    resp = None
    for name, key in keys:
        print(f"trying key: {name}")
        client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        try:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=8192,
                temperature=0.2,
                messages=messages,
                extra_headers={
                    "HTTP-Referer": "https://github.com/sypianski/lertaro",
                    "X-Title": "lertaro/privata",
                },
                extra_body={"transforms": []},
            )
            break
        except Exception as e:
            print(f"  failed ({type(e).__name__}): {e}")
            last_err = e
            continue
    if resp is None:
        sys.exit(f"all {len(keys)} keys failed; last error: {last_err}")

    body = resp.choices[0].message.content or ""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body)

    n_lines = sum(1 for ln in body.splitlines() if ln.strip())
    print(f"wrote {n_lines} non-empty lines → {out}")
    if resp.usage:
        print(
            f"input tokens: {resp.usage.prompt_tokens}  "
            f"output tokens: {resp.usage.completion_tokens}"
        )
    finish = resp.choices[0].finish_reason
    if finish != "stop":
        print(
            f"WARNING: finish_reason={finish} "
            f"(may be truncated; raise --max-tokens or chunk input)"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=pathlib.Path,
                    help="path to the source document (typically in ~/privata/)")
    ap.add_argument("--prompt", type=pathlib.Path, required=True,
                    help="path to the prompt file describing what to extract")
    ap.add_argument("--out", type=pathlib.Path,
                    help="output path (default: ~/privata-out/<stem>.out)")
    ap.add_argument("--model", default="anthropic/claude-opus-4.7",
                    help="OpenRouter model slug (default: anthropic/claude-opus-4.7)")
    args = ap.parse_args()

    src = args.input.expanduser().resolve()
    prompt_file = args.prompt.expanduser().resolve()
    if args.out:
        out = args.out.expanduser().resolve()
    else:
        out = (pathlib.Path.home() / "privata-out" / f"{src.stem}.out").resolve()

    extract(src, prompt_file, out, args.model)


if __name__ == "__main__":
    main()
