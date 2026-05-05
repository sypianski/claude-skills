#!/usr/bin/env bash
# skill installer — copies selected skill subdirs into Claude Code's
# skills directory and sets up a per-skill virtualenv for Python deps.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

usage() {
  cat <<EOF
usage: $0 <skill> [<skill>...]

Installs one or more skills from this repo into \$CLAUDE_SKILLS_DIR
(default: ~/.claude/skills). Existing destinations are overwritten.

For skills with a requirements.txt, a self-contained virtualenv is created
at <skill>/.venv and the shebang of every script in <skill>/scripts/*.py
is rewritten to use it. No system-wide pip pollution.

Available skills in this repo:
EOF
  for d in "$SCRIPT_DIR"/skills/*/; do
    name=$(basename "$d")
    [[ -f "$d/SKILL.md" ]] && echo "  - $name"
  done
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 1
fi

mkdir -p "$SKILL_DIR"

for skill in "$@"; do
  src="$SCRIPT_DIR/skills/$skill"
  if [[ ! -d "$src" || ! -f "$src/SKILL.md" ]]; then
    echo "skill not found or missing SKILL.md: $skill" >&2
    exit 1
  fi
  dest="$SKILL_DIR/$skill"
  rm -rf "$dest"
  cp -r "$src" "$dest"
  echo "installed: $skill -> $dest"

  if [[ -f "$dest/requirements.txt" ]]; then
    if ! command -v python3 >/dev/null 2>&1; then
      echo "warning: python3 not found; skipping deps for $skill" >&2
      continue
    fi

    echo "creating venv at $dest/.venv ..."
    if ! python3 -m venv "$dest/.venv" 2>/dev/null; then
      cat >&2 <<EOF
warning: 'python3 -m venv' failed for $skill.
On Debian/Ubuntu install: sudo apt install python3-venv python3-full
Then re-run: $0 $skill
EOF
      continue
    fi

    "$dest/.venv/bin/pip" install --upgrade --quiet pip
    "$dest/.venv/bin/pip" install --quiet -r "$dest/requirements.txt"

    if [[ -d "$dest/scripts" ]]; then
      shopt -s nullglob
      for f in "$dest/scripts"/*.py; do
        sed -i.bak "1s|^#!.*python[0-9.]*.*|#!$dest/.venv/bin/python3|" "$f"
        rm -f "$f.bak"
        chmod +x "$f"
      done
      shopt -u nullglob
    fi
    echo "venv ready: $dest/.venv"
  fi
done

echo
echo "done. restart Claude Code or run /skills to refresh."
