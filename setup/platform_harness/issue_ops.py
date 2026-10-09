"""Taxonomy-bound issue operations (create/classify/claim/…)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from .errors import IssueError
from .github_remote import (
    classification_satisfied,
    ensure_classification_labels,
    ensure_label,
    label_name_set,
    list_issue_records,
    view_issue_number,
)
from .project_sync import sync_project_lane
from .runtime import REPOSITORY_ROOT, run_gh
from .taxonomy import (
    argument_value,
    assert_flag_arguments,
    classification_from_arguments,
    configured_item,
    ignored_issue_file,
    positive_issue_number,
    validate_claim_branch,
    validate_claim_worker,
    validate_title,
)
from .telemetry import emit_event

CLAIM_MARKER_RE = re.compile(
    r"<!--\s*harness:claim\s+v1\s+id=(?P<id>[0-9a-fA-F-]{36})\s*-->"
)
RELEASE_MARKER_RE = re.compile(
    r"<!--\s*harness:release\s+v1\s+id=(?P<id>\*|[0-9a-fA-F-]{36})\s*-->"
)


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
    project = sync_project_lane(
        taxonomy,
        issue_number=number,
        lane=classification["lane"],
        issue_url=str(created.get("url")),
    )
    return {
        "number": number,
        "url": created.get("url"),
        "title": title,
        "labels": [label["name"] for label in classification["labels"]],
        "milestone": classification["milestone"],
        "project": project,
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
    project = sync_project_lane(
        taxonomy,
        issue_number=number,
        lane=classification["lane"],
        issue_url=str(classified.get("url")),
    )
    return {
        "number": number,
        "url": classified.get("url"),
        "labels": [label["name"] for label in classification["labels"]],
        "milestone": classification["milestone"],
        "project": project,
    }


def list_issues(args: list[str]) -> list[dict]:
    assert_flag_arguments(
        args, required=[], optional=["--state"], usage="usage: list [--state open|closed|all]"
    )
    state = argument_value(args, "--state") or "open"
    if state not in {"open", "closed", "all"}:
        raise IssueError("issue state must be open, closed, or all")
    return list_issue_records(state)


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
    """Return active structured claims ordered by createdAt, then comment order."""
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


def lane_wip_limit(taxonomy: dict, lane: str) -> int | None:
    """Return configured WIP limit for a lane, or None when unlimited/unset."""
    item = configured_item(taxonomy["lanes"], lane, "issue lane")
    limit = item.get("wip_limit")
    if limit is None:
        return None
    if not isinstance(limit, int) or limit < 1:
        raise IssueError(f"lane {lane} wip_limit must be a positive integer or null")
    return limit


def count_lane_wip(lane: str, *, exclude_issue: int | None = None) -> int:
    """Count open issues in lane that currently hold status:wip."""
    count = 0
    for issue in list_issue_records("open"):
        number = issue.get("number")
        if exclude_issue is not None and number == exclude_issue:
            continue
        labels = label_name_set(issue)
        if lane.lower() in labels and "status:wip" in labels:
            count += 1
    return count


def assert_lane_wip_available(taxonomy: dict, lane: str, *, exclude_issue: int | None = None) -> None:
    limit = lane_wip_limit(taxonomy, lane)
    if limit is None:
        return
    current = count_lane_wip(lane, exclude_issue=exclude_issue)
    if current >= limit:
        raise IssueError(
            f"lane {lane} is at WIP limit ({current}/{limit}); "
            "finish or release an in-progress claim before taking more work"
        )


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
        pass


def claim_issue(taxonomy: dict, args: list[str]) -> dict:
    """Claim an issue with comment-first, fail-closed race detection."""
    assert_flag_arguments(
        args,
        required=["--issue", "--lane", "--worker", "--branch"],
        usage="usage: claim --issue <number> --lane <lane> --worker <handle> --branch <branch>",
    )
    number = positive_issue_number(argument_value(args, "--issue"))
    lane = configured_item(taxonomy["lanes"], argument_value(args, "--lane"), "issue lane")["name"]
    worker = validate_claim_worker(argument_value(args, "--worker"))
    branch = validate_claim_branch(argument_value(args, "--branch"))
    issue = view_issue_number(number)
    assert_grabbable(issue, lane)
    assert_lane_wip_available(taxonomy, lane, exclude_issue=number)
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
    run_gh(["issue", "comment", str(number), "--body", body])
    after_comment = view_issue_number(number)
    winner = claim_winner(after_comment)
    if winner is None or winner["id"] != claim_id:
        _relinquish_lost_claim(number, claim_id)
        emit_event(
            "claim.race_lost",
            issue=number,
            lane=lane,
            worker=worker,
            claim_id=claim_id,
            winner_id=(winner or {}).get("id"),
        )
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
        emit_event(
            "claim.postcondition_failed",
            issue=number,
            lane=lane,
            worker=worker,
            claim_id=claim_id,
        )
        raise IssueError(f"issue {number} failed claim postcondition verification")
    emit_event(
        "claim.won",
        issue=number,
        lane=lane,
        worker=worker,
        branch=branch,
        claim_id=claim_id,
    )
    return {
        "number": number,
        "url": claimed.get("url"),
        "claim": body,
        "claim_id": claim_id,
    }


def release_issue(taxonomy: dict, args: list[str]) -> dict:
    assert_flag_arguments(
        args,
        required=["--issue", "--reason-file", "--mode"],
        usage="usage: release --issue <number> --mode abandon|blocked --reason-file <ignored-file>",
    )
    number = positive_issue_number(argument_value(args, "--issue"))
    mode = (argument_value(args, "--mode") or "").lower()
    if mode not in {"abandon", "blocked"}:
        raise IssueError("release --mode must be abandon or blocked")
    reason = ignored_issue_file(
        REPOSITORY_ROOT, argument_value(args, "--reason-file"), "release reason file"
    )
    reason_text = reason.read_text(encoding="utf-8").strip()
    body = format_release_body(claim_id="*", reason=f"{mode}: {reason_text}")
    run_gh(["issue", "comment", str(number), "--body", body])
    edit = ["issue", "edit", str(number), "--remove-label", "status:wip"]
    if mode == "blocked":
        ensure_label(configured_item(taxonomy["concerns"], "blocked", "issue concern"))
        edit.extend(["--add-label", "blocked"])
    run_gh(edit)
    released = view_issue_number(number)
    labels = label_name_set(released)
    if active_claim(released) or "status:wip" in labels:
        raise IssueError(f"issue {number} failed release postcondition verification")
    if mode == "blocked" and "blocked" not in labels:
        raise IssueError(f"issue {number} failed blocked release postcondition verification")
    if mode == "abandon" and "blocked" in labels:
        # Abandon must not add blocked; pre-existing blocked is allowed to remain.
        pass
    return {
        "number": number,
        "released": True,
        "mode": mode,
        "url": released.get("url"),
    }


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
