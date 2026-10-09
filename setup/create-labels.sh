#!/usr/bin/env bash
# Creates or reconciles GitHub labels from setup/project-taxonomy.json.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python setup/create_labels.py "$@"
