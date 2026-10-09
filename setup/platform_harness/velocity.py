"""Cycle-time and aging report from harness claim markers + PRs."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .errors import IssueError
from .github_remote import label_name_set, list_issue_records, view_issue_number
from .issue_ops import CLAIM_MARKER_RE
from .runtime import run_gh
from .taxonomy import parse_json

CLAIM_AT_RE = re.compile(r"\bat=([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]+Z)\b")
CLOSES_RE = re.compile(r"(?i)\bcloses\s+#([1-9]\d*)\b")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _hours(delta: timedelta | None) -> float | None:
    if delta is None:
        return None
    return round(delta.total_seconds() / 3600.0, 2)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return round((ordered[mid - 1] + ordered[mid]) / 2.0, 2)


def first_claim_timestamp(issue: dict) -> datetime | None:
    """Earliest structured CLAIM time (ignores later RELEASE — used for cycle start)."""
    earliest: datetime | None = None
    for comment in issue.get("comments") or []:
        body = comment.get("body") or ""
        if not CLAIM_MARKER_RE.search(body):
            continue
        stamp = CLAIM_AT_RE.search(body)
        ts = _parse_ts(stamp.group(1) if stamp else None) or _parse_ts(comment.get("createdAt"))
        if ts is None:
            continue
        if earliest is None or ts < earliest:
            earliest = ts
    return earliest


def _lane_of(issue: dict) -> str | None:
    for name in label_name_set(issue):
        if name.startswith("lane:"):
            return name
    return None


def _priority_of(issue: dict) -> str | None:
    for name in sorted(label_name_set(issue)):
        if re.fullmatch(r"p[0-4]", name):
            return name.upper()
    return None


def _list_merged_prs(limit: int = 100) -> list[dict]:
    raw = run_gh(
        [
            "pr",
            "list",
            "--state",
            "merged",
            "--limit",
            str(limit),
            "--json",
            "number,title,mergedAt,body,url",
        ]
    )
    return parse_json(raw, "pr list")


def velocity_report(*, days: int = 14, now: datetime | None = None) -> dict:
    if days < 1 or days > 365:
        raise IssueError("velocity --days must be between 1 and 365")
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    cutoff = clock - timedelta(days=days)

    open_issues = list_issue_records("open")
    closed_issues = list_issue_records("closed")

    wip: list[dict] = []
    in_review: list[dict] = []
    stale_wip: list[dict] = []
    claim_to_merge_hours: list[float] = []
    claim_to_close_hours: list[float] = []
    p0_p1_aging: list[dict] = []

    for issue in open_issues:
        labels = label_name_set(issue)
        priority = _priority_of(issue)
        if priority in {"P0", "P1"} and "status:wip" not in labels and "status:in-review" not in labels:
            created = _parse_ts(issue.get("createdAt")) or _parse_ts(issue.get("updatedAt"))
            p0_p1_aging.append(
                {
                    "issue": issue.get("number"),
                    "priority": priority,
                    "lane": _lane_of(issue),
                    "age_hours": _hours(clock - created) if created else None,
                    "state": "open",
                }
            )
        if "status:wip" not in labels and "status:in-review" not in labels:
            continue
        detailed = view_issue_number(int(issue["number"]))
        started = first_claim_timestamp(detailed)
        age_h = _hours(clock - started) if started else None
        row = {
            "issue": detailed.get("number"),
            "title": detailed.get("title"),
            "lane": _lane_of(detailed),
            "priority": _priority_of(detailed),
            "claim_started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ") if started else None,
            "age_hours": age_h,
        }
        detailed_labels = label_name_set(detailed)
        if "status:wip" in detailed_labels:
            wip.append(row)
            if age_h is not None and age_h >= 72:
                stale_wip.append(row)
        if "status:in-review" in detailed_labels:
            in_review.append(row)
        if _priority_of(detailed) in {"P0", "P1"}:
            p0_p1_aging.append({**row, "state": "open"})

    for issue in closed_issues:
        closed_at = _parse_ts(issue.get("closedAt"))
        if closed_at is None or closed_at < cutoff:
            continue
        detailed = view_issue_number(int(issue["number"]))
        started = first_claim_timestamp(detailed)
        if started and closed_at >= started:
            hours = _hours(closed_at - started)
            if hours is not None:
                claim_to_close_hours.append(hours)

    merged = _list_merged_prs()
    pr_rows: list[dict] = []
    for pr in merged:
        merged_at = _parse_ts(pr.get("mergedAt"))
        if merged_at is None or merged_at < cutoff:
            continue
        body = pr.get("body") or ""
        for number in (int(n) for n in CLOSES_RE.findall(body)):
            try:
                detailed = view_issue_number(number)
            except IssueError:
                continue
            started = first_claim_timestamp(detailed)
            claim_to_merge = _hours(merged_at - started) if started else None
            if claim_to_merge is not None:
                claim_to_merge_hours.append(claim_to_merge)
            pr_rows.append(
                {
                    "pr": pr.get("number"),
                    "issue": number,
                    "merged_at": merged_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "claim_to_merge_hours": claim_to_merge,
                    "url": pr.get("url"),
                }
            )

    return {
        "window_days": days,
        "generated_at": clock.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open_wip": wip,
        "open_in_review": in_review,
        "stale_wip_over_3d": stale_wip,
        "p0_p1_open_aging": p0_p1_aging,
        "merged_prs": pr_rows,
        "summary": {
            "open_wip_count": len(wip),
            "open_in_review_count": len(in_review),
            "stale_wip_count": len(stale_wip),
            "median_claim_to_close_hours": _median(claim_to_close_hours),
            "median_claim_to_merge_hours": _median(claim_to_merge_hours),
            "samples_claim_to_close": len(claim_to_close_hours),
            "samples_claim_to_merge": len(claim_to_merge_hours),
        },
    }
