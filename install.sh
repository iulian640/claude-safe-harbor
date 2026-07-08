#!/usr/bin/env bash
# Install Claude safe-harbor into your Claude Code skills directory.
set -euo pipefail

DEST="${1:-$HOME/.claude/skills/safe-harbor}"
SRC="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$DEST"
cp "$SRC/SKILL.md" "$DEST/"
cp -r "$SRC/references" "$DEST/"
cp -r "$SRC/scripts" "$DEST/"

echo "Installed Claude safe-harbor -> $DEST"
echo "Invoke it in Claude Code with /safe-harbor, or just ask it to wrap up safely."
