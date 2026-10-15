#!/usr/bin/env bash
# Bootstrap a local dogfood trial (Unix).
# Usage:
#   bash setup/trial-local.sh
#   bash setup/trial-local.sh --worktree
#   bash setup/trial-local.sh --smoke
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python setup/trial_local.py "$@"
