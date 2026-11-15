#!/usr/bin/env bash
# Python checks for this repo, matching the validation commands in CLAUDE.md:
# ruff check, mypy, unittest, apply_permissions --dry-run. Runs in the Python project's directory.
# Adapted from the kit's profile: no .venv requirement (tools come from PATH), no pytest
# (tests use unittest), no `ruff format --check` (existing code is not ruff-formatted).
set -u
fail=0
stage() { printf '\n== python: %s\n' "$1"; }

for t in ruff mypy python; do
  command -v "$t" >/dev/null 2>&1 || { echo "FAIL: $t not on PATH (install: python -m pip install -e \".[dev]\")"; exit 1; }
done

stage "ruff check"
if ruff check setup tests; then echo "PASS"; else echo "FAIL"; fail=1; fi

stage "mypy"
if mypy; then echo "PASS"; else echo "FAIL"; fail=1; fi

stage "unittest"
if python -m unittest discover -s tests; then echo "PASS"; else echo "FAIL"; fail=1; fi

stage "apply_permissions dry-run"
if python setup/apply_permissions.py --dry-run >/dev/null; then echo "PASS"; else echo "FAIL"; fail=1; fi

exit "$fail"
