#!/usr/bin/env bash
# Points git at the versioned hooks in .githooks/. Run once per clone.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true
echo "Hooks installed: pre-commit (leak scan) and commit-msg (conventional, English)."
