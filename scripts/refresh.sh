#!/usr/bin/env bash
# Rebuild data.json (+ digest) from raw/*.json and push to GitHub Pages.
set -euo pipefail
cd "$(dirname "$0")/.."
DAY="${1:-$(TZ=America/Los_Angeles date +%F)}"
DIGEST="${DIGEST:-/workspace/xmanager/inbox/digest-$DAY.md}"
python3 scripts/build_board.py --digest "$DIGEST"
git add -A && git commit -qm "Board refresh $DAY" || echo "nothing to commit"
git push -q origin main
echo "Live: https://eepykith.github.io/x-virality-board/"
