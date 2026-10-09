"""Scaffold a parent initiative plus per-lane child issues."""

from __future__ import annotations

from pathlib import Path

from .errors import IssueError
from .issue_ops import change_child_relation, create_issue
from .runtime import REPOSITORY_ROOT
from .taxonomy import configured_item, ignored_issue_file, validate_title


def scaffold_initiative(
    taxonomy: dict,
    *,
    title: str,
    body_file: str,
    lanes: list[str],
    include_foundation: bool = True,
    type_name: str = "feature",
    priority: str = "P2",
) -> dict:
    title = validate_title(title)
    if not lanes:
        raise IssueError("scaffold requires at least one --lane")
    # Validate lanes early.
    lane_names = [
        configured_item(taxonomy["lanes"], lane, "issue lane")["name"] for lane in lanes
    ]
    if include_foundation and "lane:foundation" not in {n.lower() for n in lane_names}:
        lane_names = ["lane:foundation", *lane_names]

    parent_body = ignored_issue_file(REPOSITORY_ROOT, body_file, "scaffold body file")
    parent = create_issue(
        taxonomy,
        [
            "--title",
            title,
            "--body-file",
            body_file,
            "--type",
            type_name,
            "--priority",
            priority,
            "--lane",
            lane_names[0],
        ],
    )
    parent_number = int(parent["number"])
    children: list[dict] = []

    # Remaining lanes become blocked children.
    for lane in lane_names[1:]:
        child_title = f"{title} — {lane}"
        child_path = REPOSITORY_ROOT / f"scaffold-child-{lane.replace(':', '-')}.issue-body.local.md"
        child_path.write_text(
            f"Parent initiative: #{parent_number}\n"
            f"Blocked by #{parent_number}\n\n"
            f"Lane work for `{lane}` under: {title}\n\n"
            f"{parent_body.read_text(encoding='utf-8')}\n",
            encoding="utf-8",
        )
        try:
            child = create_issue(
                taxonomy,
                [
                    "--title",
                    child_title[:120],
                    "--body-file",
                    child_path.name,
                    "--type",
                    type_name,
                    "--priority",
                    priority,
                    "--lane",
                    lane,
                    "--concern",
                    "blocked",
                ],
            )
            change_child_relation(
                ["--parent", str(parent_number), "--child", str(child["number"])],
                unlink=False,
            )
            children.append(child)
        finally:
            child_path.unlink(missing_ok=True)

    return {
        "parent": parent,
        "children": children,
        "lanes": lane_names,
        "include_foundation": include_foundation,
    }
