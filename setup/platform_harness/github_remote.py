"""Fixed-purpose GitHub issue adapter over the trusted gh runner."""

from __future__ import annotations

from .errors import IssueError
from .runtime import run_gh
from .taxonomy import parse_json

ISSUE_JSON_FIELDS = (
    "number,title,body,state,labels,milestone,assignees,comments,parent,subIssues,url"
)
ISSUE_JSON_FIELDS_FALLBACK = "number,title,body,state,labels,milestone,assignees,comments,url"
# issue list does not reliably support parent/subIssues; omit them for batch list.
LIST_JSON_FIELDS = "number,title,body,state,labels,milestone,assignees,comments,url"

_label_name_cache: set[str] | None = None


def clear_label_cache() -> None:
    global _label_name_cache
    _label_name_cache = None


def relation(issue: dict | None) -> dict | None:
    if not issue or not isinstance(issue, dict):
        return None
    return {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "state": issue.get("state"),
        "url": issue.get("url"),
    }


def normalize_comment(comment: dict) -> dict:
    return {
        "id": comment.get("id"),
        "body": comment.get("body") or "",
        "createdAt": comment.get("createdAt") or "",
        "author": comment.get("author") or {},
    }


def sub_issue_nodes(raw) -> list:
    """Normalize gh subIssues payloads (list or {nodes,totalCount}) to issue dicts."""
    if not raw:
        return []
    if isinstance(raw, list):
        nodes = raw
    elif isinstance(raw, dict):
        nodes = raw.get("nodes") or []
    else:
        return []
    return [node for node in nodes if isinstance(node, dict)]


def comment_nodes(raw) -> list:
    """Normalize gh comments payloads (list, count int, or {nodes,...}) to comment dicts."""
    if not raw:
        return []
    if isinstance(raw, int):
        return []
    if isinstance(raw, list):
        nodes = raw
    elif isinstance(raw, dict):
        nodes = raw.get("nodes") or []
    else:
        return []
    return [node for node in nodes if isinstance(node, dict)]


def normalize_issue(issue: dict) -> dict:
    return {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "body": issue.get("body"),
        "state": issue.get("state"),
        "labels": issue.get("labels") or [],
        "milestone": issue.get("milestone") or None,
        "assignees": issue.get("assignees") or [],
        "comments": [normalize_comment(item) for item in comment_nodes(issue.get("comments"))],
        "parent": relation(issue.get("parent") if isinstance(issue.get("parent"), dict) else None),
        "children": [relation(child) for child in sub_issue_nodes(issue.get("subIssues"))],
        "url": issue.get("url"),
    }


def label_name_set(issue: dict) -> set[str]:
    return {label["name"].lower() for label in issue.get("labels") or []}


def classification_satisfied(issue: dict, classification: dict) -> bool:
    actual = label_name_set(issue)
    if classification["milestone"] is None:
        milestone_matches = issue.get("milestone") is None
    else:
        milestone = issue.get("milestone") or {}
        milestone_matches = milestone.get("title") == classification["milestone"]
    return (
        all(label["name"].lower() in actual for label in classification["labels"])
        and milestone_matches
    )


def view_issue_number(number: int) -> dict:
    try:
        raw = run_gh(["issue", "view", str(number), "--json", ISSUE_JSON_FIELDS])
    except IssueError:
        raw = run_gh(
            ["issue", "view", str(number), "--json", ISSUE_JSON_FIELDS_FALLBACK]
        )
    return normalize_issue(parse_json(raw, "issue view"))


def list_issue_records(state: str) -> list[dict]:
    """One batched gh issue list — avoids N+1 view calls for triage."""
    raw = run_gh(
        ["issue", "list", "--state", state, "--limit", "1000", "--json", LIST_JSON_FIELDS]
    )
    return [normalize_issue(item) for item in parse_json(raw, "issue list")]


def existing_label_names() -> set[str]:
    global _label_name_cache
    if _label_name_cache is not None:
        return _label_name_cache
    existing = parse_json(
        run_gh(["label", "list", "--limit", "1000", "--json", "name"]),
        "label list",
    )
    _label_name_cache = {item["name"].lower() for item in existing}
    return _label_name_cache


def ensure_label(label: dict) -> None:
    names = existing_label_names()
    if label["name"].lower() in names:
        return
    run_gh(
        [
            "label",
            "create",
            label["name"],
            "--color",
            label["color"].lstrip("#"),
            "--description",
            label["description"],
        ]
    )
    names.add(label["name"].lower())


def ensure_classification_labels(classification: dict) -> None:
    for label in classification["labels"]:
        ensure_label(label)
