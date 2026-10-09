"""Optional GitHub Project lane sync after create/classify.

When setup/project-taxonomy.json sets project_board to null, sync is a no-op.
When configured, the wrapper adds the issue to the project and sets the lane field
using fixed gh project commands (no arbitrary API).
"""

from __future__ import annotations

from .errors import IssueError
from .runtime import run_gh


REQUIRED_BOARD_KEYS = ("owner", "number", "lane_field", "lane_option_map")


def project_board_config(taxonomy: dict) -> dict | None:
    board = taxonomy.get("project_board")
    if board is None:
        return None
    if not isinstance(board, dict):
        raise IssueError("project_board must be null or an object")
    missing = [key for key in REQUIRED_BOARD_KEYS if key not in board]
    if missing:
        raise IssueError(
            "project_board is missing required keys: " + ", ".join(missing)
        )
    if not isinstance(board["lane_option_map"], dict) or not board["lane_option_map"]:
        raise IssueError("project_board.lane_option_map must be a non-empty object")
    return board


def sync_project_lane(taxonomy: dict, *, issue_number: int, lane: str, issue_url: str) -> dict:
    """Sync taxonomy lane into the configured Project field, or skip when unset."""
    board = project_board_config(taxonomy)
    if board is None:
        return {"synced": False, "reason": "project_board not configured"}
    option = board["lane_option_map"].get(lane)
    if not option:
        raise IssueError(
            f"project_board.lane_option_map has no option for lane {lane}"
        )
    # Fixed command shapes — wrappers never accept free-form project argv.
    run_gh(
        [
            "project",
            "item-add",
            str(board["number"]),
            "--owner",
            str(board["owner"]),
            "--url",
            issue_url,
        ]
    )
    run_gh(
        [
            "project",
            "item-edit",
            "--project-id",
            str(board["number"]),
            "--owner",
            str(board["owner"]),
            "--issue",
            str(issue_number),
            "--field",
            str(board["lane_field"]),
            "--text",
            str(option),
        ]
    )
    return {
        "synced": True,
        "owner": board["owner"],
        "project": board["number"],
        "lane_field": board["lane_field"],
        "lane_option": option,
    }
