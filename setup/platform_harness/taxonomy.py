"""Taxonomy loading and classification argument validation."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .errors import IssueError
from .runtime import TAXONOMY_PATH, run_git

TITLE_RE = re.compile(r"^[^\x00-\x1f]{1,120}$")
POSITIVE_INT_RE = re.compile(r"^[1-9]\d*$")

# Fail closed on common secret shapes before posting body/rationale to GitHub.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PEM private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b")),
    ("GitHub fine-grained PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    (
        "assignment-style secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|token|gh_token|aws_secret_access_key)\s*[:=]\s*\S{12,}"
        ),
    ),
)


def reject_secret_content(content: str, description: str) -> None:
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(content):
            raise IssueError(
                f"{description} looks like it contains a {label}; "
                "remove secrets before posting to GitHub"
            )


def load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    taxonomy = json.loads(path.read_text(encoding="utf-8"))
    for key in ("issue_types", "priorities", "concerns", "claim_statuses", "lanes", "milestones"):
        if key not in taxonomy or not isinstance(taxonomy[key], list):
            raise IssueError(f"setup/project-taxonomy.json is missing {key}")
    if not taxonomy["lanes"]:
        raise IssueError("setup/project-taxonomy.json must declare at least one lane")
    return taxonomy


def argument_value(args: list[str], name: str) -> str | None:
    try:
        index = args.index(name)
    except ValueError:
        return None
    if index + 1 >= len(args):
        return None
    return args[index + 1]


def argument_values(args: list[str], name: str) -> list[str]:
    values = []
    index = 0
    while index < len(args):
        if args[index] == name:
            if index + 1 >= len(args) or args[index + 1].startswith("--"):
                raise IssueError(f"{name} requires a value")
            values.append(args[index + 1])
            index += 2
            continue
        index += 1
    return values


def positive_issue_number(value: str | None, name: str = "issue") -> int:
    if not POSITIVE_INT_RE.match(str(value or "")):
        raise IssueError(f"{name} must be a positive integer")
    return int(value)


def assert_flag_arguments(
    args: list[str],
    *,
    required: list[str],
    optional: list[str] | None = None,
    repeatable: list[str] | None = None,
    usage: str,
) -> None:
    optional = optional or []
    repeatable = repeatable or []
    values = set(required + optional + repeatable)
    allowed = set(values)
    seen: dict[str, int] = {}
    index = 0
    while index < len(args):
        flag = args[index]
        if flag not in allowed:
            raise IssueError(usage)
        seen[flag] = seen.get(flag, 0) + 1
        if flag not in repeatable and seen[flag] > 1:
            raise IssueError(f"duplicate issue argument: {flag}")
        if flag in values:
            if index + 1 >= len(args) or args[index + 1].startswith("--"):
                raise IssueError(f"{flag} requires a value")
            index += 1
        index += 1
    for flag in required:
        if flag not in seen:
            raise IssueError(f"issue operation requires {flag}")


def configured_item(items: list[dict], requested: str | None, field: str) -> dict:
    normalized = str(requested or "").lower()
    match = next((item for item in items if item["name"].lower() == normalized), None)
    if match is None:
        raise IssueError(f"{field} is not configured in setup/project-taxonomy.json: {requested}")
    return match


def classification_from_arguments(
    taxonomy: dict,
    args: list[str],
    *,
    rationale: bool = False,
) -> dict:
    require_milestone = bool(taxonomy.get("milestones")) and (
        taxonomy.get("require_milestone_on_classify", True)
        if rationale
        else taxonomy.get("require_milestone_on_create", False)
    )
    required = ["--type", "--priority", "--lane"]
    if rationale:
        required = ["--issue", *required, "--rationale-file"]
    else:
        required = ["--title", "--body-file", *required]
    assert_flag_arguments(
        args,
        required=required,
        optional=["--milestone"],
        repeatable=["--concern"],
        usage=(
            "expected classify flags: --issue, --type, --priority, --lane, "
            "[--concern ...], [--milestone], --rationale-file"
            if rationale
            else "expected create flags: --title, --body-file, --type, --priority, --lane, "
            "[--concern ...], [--milestone]"
        ),
    )
    labels = [
        configured_item(taxonomy["issue_types"], argument_value(args, "--type"), "issue type"),
        configured_item(taxonomy["priorities"], argument_value(args, "--priority"), "issue priority"),
        configured_item(taxonomy["lanes"], argument_value(args, "--lane"), "issue lane"),
        *[
            configured_item(taxonomy["concerns"], name, "issue concern")
            for name in argument_values(args, "--concern")
        ],
    ]
    names = [label["name"] for label in labels]
    if len({name.lower() for name in names}) != len(names):
        raise IssueError("issue concerns must not contain duplicates")
    requested_milestone = argument_value(args, "--milestone")
    if require_milestone and not requested_milestone:
        raise IssueError("configured project milestones require --milestone")
    if taxonomy["milestones"] and requested_milestone:
        milestone = configured_item(
            taxonomy["milestones"], requested_milestone, "issue milestone"
        )["name"]
    elif requested_milestone:
        raise IssueError("issue milestone is not configured in setup/project-taxonomy.json")
    else:
        milestone = None
    return {"labels": labels, "milestone": milestone, "lane": labels[2]["name"]}


def validate_title(title: str | None) -> str:
    if not isinstance(title, str) or not TITLE_RE.match(title):
        raise IssueError("issue title must be 1-120 printable characters")
    return title


def ignored_issue_file(repository_root: Path, relpath: str | None, description: str) -> Path:
    if not relpath:
        raise IssueError(f"{description} is required")
    path = (repository_root / relpath).resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise IssueError(f"{description} must be a physical file inside the repository") from exc
    if not path.is_file() or path.is_symlink():
        raise IssueError(f"{description} must be a physical file inside the repository")
    relative = str(path.relative_to(repository_root.resolve())).replace("\\", "/")
    try:
        run_git(["check-ignore", "--quiet", "--", relative])
    except IssueError as exc:
        raise IssueError(f"{description} must be ignored by Git") from exc
    content = path.read_text(encoding="utf-8")
    if not content.strip() or len(content) > 65_536 or "\0" in content:
        raise IssueError(f"{description} must contain 1-65536 characters and no NUL bytes")
    reject_secret_content(content, description)
    return path


def parse_json(output: str, operation: str):
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise IssueError(f"{operation} returned invalid JSON") from exc
