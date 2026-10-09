#!/usr/bin/env python3
"""Materialize portable permission placeholders into gitignored local settings.

Committed setup/agent-permissions.json uses REPLACE_WITH_YOUR_REPO_GIT_ROOT. Absolute
paths are written only to machine-local files that Git ignores.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from platform_harness import IssueError, REPOSITORY_ROOT, run_git

PLACEHOLDER = "REPLACE_WITH_YOUR_REPO_GIT_ROOT"
SOURCE = Path(__file__).resolve().parent / "agent-permissions.json"
CLAUDE_LOCAL = REPOSITORY_ROOT / ".claude" / "settings.local.json"
CURSOR_LOCAL = REPOSITORY_ROOT / ".cursor" / "permissions.local.json"


def repository_root() -> Path:
    root = Path(run_git(["rev-parse", "--show-toplevel"]).strip()).resolve()
    if root != REPOSITORY_ROOT.resolve():
        raise IssueError("apply_permissions must run from the physical repository Git root")
    return root


def load_source() -> dict:
    document = json.loads(SOURCE.read_text(encoding="utf-8"))
    locations = document.get("locations")
    if not isinstance(locations, dict) or list(locations.keys()) != [PLACEHOLDER]:
        raise IssueError(
            "permission source must define exactly one location: REPLACE_WITH_YOUR_REPO_GIT_ROOT"
        )
    return document


def command_to_claude(identifier: str) -> str:
    if identifier.endswith(":*"):
        return f"Bash({identifier[:-2]} *)"
    return f"Bash({identifier})"


def substitute_placeholder(value, root: Path):
    """Replace portable root placeholders with the absolute Git root."""
    if isinstance(value, str):
        return value.replace(PLACEHOLDER, str(root))
    if isinstance(value, list):
        return [substitute_placeholder(item, root) for item in value]
    if isinstance(value, dict):
        return {key: substitute_placeholder(item, root) for key, item in value.items()}
    return value


def materialize(root: Path, document: dict) -> tuple[dict, dict]:
    entry = substitute_placeholder(document["locations"][PLACEHOLDER], root)
    directories = entry.get("allowed_directories") or []
    if not directories:
        raise IssueError(
            "permission source must scope allowed_directories to REPLACE_WITH_YOUR_REPO_GIT_ROOT"
        )
    if any(path != str(root) for path in directories):
        raise IssueError(
            "permission source allowed_directories must resolve only to the repository Git root"
        )
    resolved = {"locations": {str(root): entry}}
    identifiers = []
    for approval in entry.get("tool_approvals") or []:
        if approval.get("kind") == "commands":
            identifiers.extend(approval.get("commandIdentifiers") or [])
    banned_exact = {
        "python:*",
        "python3:*",
        "git push:*",
        "gh issue:*",
        "gh label:*",
        "gh milestone:*",
        "gh project:*",
        "gh pr merge:*",
        "gh pr:*",
        "gh api",
        "gh api:*",
    }
    for identifier in identifiers:
        if identifier in banned_exact:
            raise IssueError(f"permission source must not auto-approve {identifier}")
        if identifier.startswith(("python -c", "python3 -c", "gh api ")):
            raise IssueError(f"permission source must not auto-approve {identifier}")
    claude = {
        "permissions": {
            "allow": [command_to_claude(item) for item in identifiers],
        }
    }
    return resolved, claude


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = repository_root()
    document = load_source()
    resolved, claude = materialize(root, document)
    result = {
        "repository_root": str(root),
        "claude_local": str(CLAUDE_LOCAL),
        "cursor_local": str(CURSOR_LOCAL),
        "resolved": resolved,
        "claude_settings": claude,
    }
    if args.dry_run:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    write_json(CLAUDE_LOCAL, claude)
    write_json(CURSOR_LOCAL, resolved)
    json.dump(
        {
            "applied": True,
            "claude_local": str(CLAUDE_LOCAL),
            "cursor_local": str(CURSOR_LOCAL),
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except IssueError as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1)
