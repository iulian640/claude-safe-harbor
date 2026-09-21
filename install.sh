#!/usr/bin/env bash
# Install Claude safe-harbor into your Claude Code skills directory.
# Usage: ./install.sh [DEST] [--estimator]
#   --estimator  also copy scripts/usage.py (optional usage estimator)
set -euo pipefail

DEST="$HOME/.claude/skills/safe-harbor"
WITH_ESTIMATOR=0
for arg in "$@"; do
  case "$arg" in
    --estimator) WITH_ESTIMATOR=1 ;;
    *) DEST="$arg" ;;
  esac
done
SRC="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$DEST"
cp "$SRC/SKILL.md" "$DEST/"
cp -r "$SRC/references" "$DEST/"
if [ "$WITH_ESTIMATOR" -eq 1 ]; then
  cp -r "$SRC/scripts" "$DEST/"
fi

echo "Installed Claude safe-harbor -> $DEST"
echo "Invoke it in Claude Code with /safe-harbor, or just say you are wrapping up."
