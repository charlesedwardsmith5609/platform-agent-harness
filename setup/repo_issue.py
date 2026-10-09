#!/usr/bin/env python3
"""Taxonomy-bound GitHub issue lifecycle for the platform engineering harness.

Body and rationale text are read from Git-ignored files so multiline content is never
passed as shell argv. Classification is constrained to setup/project-taxonomy.json.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

SETUP_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SETUP_ROOT.parent
TAXONOMY_PATH = SETUP_ROOT / "project-taxonomy.json"
TITLE_RE = re.compile(r"^[^\x00-\x1f]{1,120}$")
POSITIVE_INT_RE = re.compile(r"^[1-9]\d*$")
# Only structured harness markers count — free-text "CLAIM"/"RELEASE" is ignored.
CLAIM_MARKER_RE = re.compile(
    r"<!--\s*harness:claim\s+v1\s+id=(?P<id>[0-9a-fA-F-]{36})\s*-->"
)
RELEASE_MARKER_RE = re.compile(
    r"<!--\s*harness:release\s+v1\s+id=(?P<id>\*|[0-9a-fA-F-]{36})\s*-->"
)
ISSUE_JSON_FIELDS = (
    "number,title,body,state,labels,milestone,assignees,comments,parent,subIssues,url"
)
ISSUE_JSON_FIELDS_FALLBACK = "number,title,body,state,labels,milestone,assignees,comments,url"
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

CommandRunner = Callable[[list[str]], str]
_gh_runner: CommandRunner | None = None
_git_runner: CommandRunner | None = None


class IssueError(ValueError):
    pass


def set_command_runners(
    *,
    gh: CommandRunner | None = None,
    git: CommandRunner | None = None,
) -> None:
    """Override subprocess runners (tests only). Pass None to restore defaults."""
    global _gh_runner, _git_runner
    _gh_runner = gh
    _git_runner = git


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
    return path


def gh_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GH_PROMPT_DISABLED": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
            "GH_PAGER": "cat",
            "PAGER": "cat",
            "GIT_PAGER": "cat",
            "NO_COLOR": "1",
        }
    )
    return env


def run_trusted(executable: str, args: list[str], *, timeout: int = 30) -> str:
    completed = subprocess.run(
        [executable, *args],
        cwd=REPOSITORY_ROOT,
        env=gh_environment(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise IssueError(detail or f"{executable} {' '.join(args)} failed")
    return completed.stdout


def run_git(args: list[str]) -> str:
    if _git_runner is not None:
        return _git_runner(args)
    return run_trusted("git", args)


def run_gh(args: list[str]) -> str:
    if _gh_runner is not None:
        return _gh_runner(args)
    return run_trusted("gh", args)


def parse_json(output: str, operation: str):
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise IssueError(f"{operation} returned invalid JSON") from exc


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


def normalize_issue(issue: dict) -> dict:
    return {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "body": issue.get("body"),
        "state": issue.get("state"),
        "labels": issue.get("labels") or [],
        "milestone": issue.get("milestone") or None,
        "assignees": issue.get("assignees") or [],
        "comments": [normalize_comment(item) for item in (issue.get("comments") or [])],
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
        raw = run_gh(
            ["issue", "view", str(number), "--json", ISSUE_JSON_FIELDS]
        )
    except IssueError:
        raw = run_gh(
            ["issue", "view", str(number), "--json", ISSUE_JSON_FIELDS_FALLBACK]
        )
    return normalize_issue(parse_json(raw, "issue view"))


def ensure_label(label: dict) -> None:
    existing = parse_json(
        run_gh(["label", "list", "--limit", "1000", "--json", "name"]),
        "label list",
    )
    if any(item["name"].lower() == label["name"].lower() for item in existing):
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


def ensure_classification_labels(classification: dict) -> None:
    for label in classification["labels"]:
        ensure_label(label)


def create_issue(taxonomy: dict, args: list[str]) -> dict:
    classification = classification_from_arguments(taxonomy, args)
    title = validate_title(argument_value(args, "--title"))
    body = ignored_issue_file(
        REPOSITORY_ROOT, argument_value(args, "--body-file"), "issue body file"
    )
    ensure_classification_labels(classification)
    create_args = ["issue", "create", "--title", title, "--body-file", str(body)]
    for label in classification["labels"]:
        create_args.extend(["--label", label["name"]])
    if classification["milestone"]:
        create_args.extend(["--milestone", classification["milestone"]])
    output = run_gh(create_args).strip()
    match = re.search(r"/issues/([1-9]\d*)/?$", output)
    if not match:
        raise IssueError(f"unable to identify created issue from GitHub output: {output}")
    number = int(match.group(1))
    created = view_issue_number(number)
    if str(created.get("state") or "").upper() != "OPEN":
        raise IssueError(
            f"created issue {number} failed taxonomy postcondition verification; inspect {created.get('url')}"
        )
    if created.get("title") != title or not classification_satisfied(created, classification):
        raise IssueError(
            f"created issue {number} failed taxonomy postcondition verification; inspect {created.get('url')}"
        )
    return {
        "number": number,
        "url": created.get("url"),
        "title": title,
        "labels": [label["name"] for label in classification["labels"]],
        "milestone": classification["milestone"],
    }


def classify_issue(taxonomy: dict, args: list[str]) -> dict:
    classification = classification_from_arguments(taxonomy, args, rationale=True)
    number = positive_issue_number(argument_value(args, "--issue"))
    rationale = ignored_issue_file(
        REPOSITORY_ROOT,
        argument_value(args, "--rationale-file"),
        "classification rationale file",
    )
    before = view_issue_number(number)
    classification_names = {
        item["name"].lower()
        for group in (
            taxonomy["issue_types"],
            taxonomy["priorities"],
            taxonomy["concerns"],
            taxonomy["lanes"],
        )
        for item in group
    }
    desired = {label["name"].lower() for label in classification["labels"]}
    remove_labels = [
        label["name"]
        for label in before.get("labels") or []
        if label["name"].lower() in classification_names and label["name"].lower() not in desired
    ]
    ensure_classification_labels(classification)
    edit = ["issue", "edit", str(number)]
    for name in remove_labels:
        edit.extend(["--remove-label", name])
    for label in classification["labels"]:
        edit.extend(["--add-label", label["name"]])
    if classification["milestone"]:
        edit.extend(["--milestone", classification["milestone"]])
    else:
        edit.append("--remove-milestone")
    run_gh(edit)
    classified = view_issue_number(number)
    unrelated_before = [
        label["name"]
        for label in before.get("labels") or []
        if label["name"].lower() not in classification_names
    ]
    classified_names = label_name_set(classified)
    if not classification_satisfied(classified, classification) or any(
        name.lower() not in classified_names for name in unrelated_before
    ):
        raise IssueError(
            f"issue {number} failed taxonomy classification postcondition verification; "
            f"inspect {classified.get('url')}"
        )
    run_gh(["issue", "comment", str(number), "--body", rationale.read_text(encoding="utf-8")])
    return {
        "number": number,
        "url": classified.get("url"),
        "labels": [label["name"] for label in classification["labels"]],
        "milestone": classification["milestone"],
    }


def list_issues(args: list[str]) -> list[dict]:
    assert_flag_arguments(
        args, required=[], optional=["--state"], usage="usage: list [--state open|closed|all]"
    )
    state = argument_value(args, "--state") or "open"
    if state not in {"open", "closed", "all"}:
        raise IssueError("issue state must be open, closed, or all")
    issues = parse_json(
        run_gh(["issue", "list", "--state", state, "--limit", "1000", "--json", "number"]),
        "issue list",
    )
    return [view_issue_number(item["number"]) for item in issues]


def view_issue(args: list[str]) -> dict:
    assert_flag_arguments(args, required=["--issue"], usage="usage: view --issue <number>")
    return view_issue_number(positive_issue_number(argument_value(args, "--issue")))


def change_child_relation(args: list[str], *, unlink: bool) -> dict:
    usage = f"usage: {'unlink-child' if unlink else 'link-child'} --parent <number> --child <number>"
    assert_flag_arguments(args, required=["--parent", "--child"], usage=usage)
    parent = positive_issue_number(argument_value(args, "--parent"), "parent")
    child = positive_issue_number(argument_value(args, "--child"), "child")
    if parent == child:
        raise IssueError("an issue cannot be its own parent")
    view_issue_number(parent)
    view_issue_number(child)
    if unlink:
        run_gh(["issue", "edit", str(child), "--remove-parent"])
    else:
        run_gh(["issue", "edit", str(parent), "--add-sub-issue", str(child)])
    verified = view_issue_number(parent)
    present = any((issue or {}).get("number") == child for issue in verified.get("children") or [])
    if present == unlink:
        raise IssueError(
            f"issue {parent} failed {'unlink' if unlink else 'link'}-child postcondition verification"
        )
    return {"parent": parent, "child": child, "linked": not unlink}


def format_claim_body(
    *,
    claim_id: str,
    lane: str,
    worker: str,
    branch: str,
    stamp: str,
) -> str:
    return (
        f"<!-- harness:claim v1 id={claim_id} -->\n"
        f"CLAIM · lane={lane} · worker={worker} · branch={branch} · at={stamp} · id={claim_id}"
    )


def format_release_body(*, claim_id: str, reason: str) -> str:
    return (
        f"<!-- harness:release v1 id={claim_id} -->\n"
        f"RELEASE · id={claim_id} · reason={reason}"
    )


def active_claims(issue: dict) -> list[dict]:
    """Return active structured claims ordered by createdAt, then comment order.

    Free-text mentions of CLAIM/RELEASE do not count. A release with id=* clears all
    active claims; a release with a specific id clears only that claim.
    """
    active: dict[str, dict] = {}
    order = 0
    for comment in issue.get("comments") or []:
        body = comment.get("body") or ""
        created = comment.get("createdAt") or ""
        release = RELEASE_MARKER_RE.search(body)
        if release:
            released_id = release.group("id")
            if released_id == "*":
                active.clear()
            else:
                active.pop(released_id, None)
            continue
        claim = CLAIM_MARKER_RE.search(body)
        if not claim:
            continue
        claim_id = claim.group("id")
        active[claim_id] = {
            "id": claim_id,
            "createdAt": created,
            "order": order,
            "body": body,
        }
        order += 1
    return sorted(
        active.values(),
        key=lambda item: (item["createdAt"], item["order"]),
    )


def active_claim(issue: dict) -> bool:
    return bool(active_claims(issue))


def claim_winner(issue: dict) -> dict | None:
    claims = active_claims(issue)
    return claims[0] if claims else None


def assert_grabbable(issue: dict, lane: str) -> None:
    if str(issue.get("state") or "").upper() not in {"OPEN"}:
        raise IssueError("issue must be open")
    labels = label_name_set(issue)
    if lane.lower() not in labels:
        raise IssueError(f"issue is not in lane {lane}")
    for blocked in ("status:wip", "status:in-review", "blocked"):
        if blocked in labels:
            raise IssueError(f"issue is not grabbable: {blocked}")
    if active_claim(issue):
        raise IssueError("issue already has a structured CLAIM")


def _relinquish_lost_claim(number: int, claim_id: str) -> None:
    run_gh(
        [
            "issue",
            "comment",
            str(number),
            "--body",
            format_release_body(
                claim_id=claim_id,
                reason="lost claim race; fail closed",
            ),
        ]
    )
    try:
        run_gh(["issue", "edit", str(number), "--remove-label", "status:wip"])
    except IssueError:
        # Label may never have been added, or another worker holds it.
        pass


def claim_issue(taxonomy: dict, args: list[str]) -> dict:
    """Claim an issue with comment-first, fail-closed race detection.

    Protocol:
    1. Preflight grabbable check
    2. Post a structured CLAIM comment with a unique id (comment stream is the lock)
    3. Re-read; earliest active structured claim wins
    4. Losers immediately RELEASE themselves and fail closed
    5. Winner adds status:wip and re-verifies sole ownership
    """
    assert_flag_arguments(
        args,
        required=["--issue", "--lane", "--worker", "--branch"],
        usage="usage: claim --issue <number> --lane <lane> --worker <handle> --branch <branch>",
    )
    number = positive_issue_number(argument_value(args, "--issue"))
    lane = configured_item(taxonomy["lanes"], argument_value(args, "--lane"), "issue lane")["name"]
    worker = argument_value(args, "--worker")
    branch = argument_value(args, "--branch")
    if not worker or not branch:
        raise IssueError("claim requires --worker and --branch")
    issue = view_issue_number(number)
    assert_grabbable(issue, lane)
    ensure_label(configured_item(taxonomy["claim_statuses"], "status:wip", "claim status"))

    claim_id = str(uuid.uuid4())
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = format_claim_body(
        claim_id=claim_id,
        lane=lane,
        worker=worker,
        branch=branch,
        stamp=stamp,
    )
    # Comment first so concurrent claimers share one ordered lock stream.
    run_gh(["issue", "comment", str(number), "--body", body])
    after_comment = view_issue_number(number)
    winner = claim_winner(after_comment)
    if winner is None or winner["id"] != claim_id:
        _relinquish_lost_claim(number, claim_id)
        raise IssueError(
            f"issue {number} claim race lost; another structured CLAIM is active"
        )

    run_gh(["issue", "edit", str(number), "--add-label", "status:wip"])
    claimed = view_issue_number(number)
    winner = claim_winner(claimed)
    if (
        "status:wip" not in label_name_set(claimed)
        or winner is None
        or winner["id"] != claim_id
        or len(active_claims(claimed)) != 1
    ):
        _relinquish_lost_claim(number, claim_id)
        raise IssueError(f"issue {number} failed claim postcondition verification")
    return {
        "number": number,
        "url": claimed.get("url"),
        "claim": body,
        "claim_id": claim_id,
    }


def release_issue(taxonomy: dict, args: list[str]) -> dict:
    assert_flag_arguments(
        args,
        required=["--issue", "--reason-file"],
        usage="usage: release --issue <number> --reason-file <ignored-file>",
    )
    number = positive_issue_number(argument_value(args, "--issue"))
    reason = ignored_issue_file(
        REPOSITORY_ROOT, argument_value(args, "--reason-file"), "release reason file"
    )
    ensure_label(configured_item(taxonomy["concerns"], "blocked", "issue concern"))
    reason_text = reason.read_text(encoding="utf-8").strip()
    body = format_release_body(claim_id="*", reason=reason_text)
    run_gh(["issue", "comment", str(number), "--body", body])
    run_gh(
        [
            "issue",
            "edit",
            str(number),
            "--remove-label",
            "status:wip",
            "--add-label",
            "blocked",
        ]
    )
    released = view_issue_number(number)
    if active_claim(released) or "status:wip" in label_name_set(released):
        raise IssueError(f"issue {number} failed release postcondition verification")
    return {"number": number, "released": True, "url": released.get("url")}


def mark_in_review(taxonomy: dict, args: list[str]) -> dict:
    assert_flag_arguments(
        args, required=["--issue"], usage="usage: in-review --issue <number>"
    )
    number = positive_issue_number(argument_value(args, "--issue"))
    ensure_label(configured_item(taxonomy["claim_statuses"], "status:in-review", "claim status"))
    run_gh(
        [
            "issue",
            "edit",
            str(number),
            "--remove-label",
            "status:wip",
            "--add-label",
            "status:in-review",
        ]
    )
    reviewed = view_issue_number(number)
    labels = label_name_set(reviewed)
    if "status:in-review" not in labels or "status:wip" in labels:
        raise IssueError(f"issue {number} failed in-review postcondition verification")
    return {"number": number, "url": reviewed.get("url")}


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
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        raise IssueError(f"usage: python setup/repo_issue.py <{'|'.join(COMMANDS)}>")
    result = dispatch(args[0], args[1:])
    sys.stdout.write(f"{json.dumps(result, indent=2)}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except IssueError as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1)
