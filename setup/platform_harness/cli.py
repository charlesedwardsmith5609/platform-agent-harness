"""CLI entry for taxonomy-bound issue lifecycle."""

from __future__ import annotations

import json
import sys

from .errors import IssueError
from .issue_ops import (
    change_child_relation,
    claim_issue,
    classify_issue,
    create_issue,
    list_issues,
    mark_in_review,
    release_issue,
    view_issue,
)
from .taxonomy import load_taxonomy

COMMANDS = (
    "create",
    "list",
    "view",
    "classify",
    "link-child",
    "unlink-child",
    "claim",
    "release",
    "in-review",
)


def dispatch(command: str, args: list[str]) -> object:
    if command not in COMMANDS:
        raise IssueError(f"usage: python setup/repo_issue.py <{'|'.join(COMMANDS)}>")
    taxonomy = load_taxonomy()
    if command == "create":
        return create_issue(taxonomy, args)
    if command == "list":
        return list_issues(args)
    if command == "view":
        return view_issue(args)
    if command == "classify":
        return classify_issue(taxonomy, args)
    if command == "claim":
        return claim_issue(taxonomy, args)
    if command == "release":
        return release_issue(taxonomy, args)
    if command == "in-review":
        return mark_in_review(taxonomy, args)
    return change_child_relation(args, unlink=command == "unlink-child")


def main(argv: list[str] | None = None) -> int:
    try:
        args = list(sys.argv[1:] if argv is None else argv)
        if not args:
            raise IssueError(f"usage: python setup/repo_issue.py <{'|'.join(COMMANDS)}>")
        result = dispatch(args[0], args[1:])
        sys.stdout.write(f"{json.dumps(result, indent=2)}\n")
        return 0
    except IssueError as error:
        sys.stderr.write(f"{error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
