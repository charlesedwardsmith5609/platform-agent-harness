#!/usr/bin/env python3
"""Compatibility entry point for taxonomy-bound GitHub issue lifecycle.

Implementation lives in setup/platform_harness/. Prefer:

    python setup/repo_issue.py <command> ...

or after install:

    repo-issue <command> ...
"""

from __future__ import annotations

import sys

from platform_harness import (
    COMMANDS,
    IssueError,
    REPOSITORY_ROOT,
    SETUP_ROOT,
    active_claim,
    active_claims,
    claim_issue,
    claim_winner,
    classification_from_arguments,
    dispatch,
    format_claim_body,
    format_release_body,
    load_taxonomy,
    main,
    normalize_issue,
    parse_json,
    run_gh,
    run_git,
    set_command_runners,
    sub_issue_nodes,
    validate_title,
)

__all__ = [
    "COMMANDS",
    "IssueError",
    "REPOSITORY_ROOT",
    "SETUP_ROOT",
    "active_claim",
    "active_claims",
    "claim_issue",
    "claim_winner",
    "classification_from_arguments",
    "dispatch",
    "format_claim_body",
    "format_release_body",
    "load_taxonomy",
    "main",
    "normalize_issue",
    "parse_json",
    "run_gh",
    "run_git",
    "set_command_runners",
    "sub_issue_nodes",
    "validate_title",
]


if __name__ == "__main__":
    raise SystemExit(main())
