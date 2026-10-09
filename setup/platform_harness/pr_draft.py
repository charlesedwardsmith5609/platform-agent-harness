"""Generate a PR body skeleton from an issue + local CLAUDE.md validation commands."""

from __future__ import annotations

import re
from pathlib import Path

from .errors import IssueError
from .github_remote import label_name_set, view_issue_number
from .runtime import REPOSITORY_ROOT
from .taxonomy import positive_issue_number

VALIDATION_BLOCK_RE = re.compile(
    r"Validation commands.*?\n```(?:bash)?\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)


def _lane_of(issue: dict) -> str | None:
    for name in label_name_set(issue):
        if name.startswith("lane:"):
            return name
    return None


def _validation_commands() -> list[str]:
    path = REPOSITORY_ROOT / "CLAUDE.md"
    if not path.is_file():
        return ["python -m unittest discover -s tests -v"]
    text = path.read_text(encoding="utf-8")
    match = VALIDATION_BLOCK_RE.search(text)
    if not match:
        return ["python -m unittest discover -s tests -v"]
    lines = []
    for raw in match.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Drop inline comments after commands for the checklist.
        command = line.split(" #", 1)[0].strip()
        if command:
            lines.append(command)
    return lines or ["python -m unittest discover -s tests -v"]


def build_pr_draft(*, issue: int | str) -> dict:
    number = positive_issue_number(str(issue))
    viewed = view_issue_number(number)
    title = viewed.get("title") or f"Issue {number}"
    lane = _lane_of(viewed) or "lane:unknown"
    commands = _validation_commands()
    validation_md = "\n".join(f"- [ ] `{cmd}`" for cmd in commands)
    body = f"""Closes #{number}

## What changed
[What was done and why — 2–4 sentences]

## Validation
{validation_md}

## Blast radius
- Lane: `{lane}`
- Who is affected if this is wrong: [teams/services]
- Rollback: [command or revert path]

## STATUS
STATUS · PR opened · [UTC timestamp]
Lane: {lane}
Issue: #{number}  PR: #<pr>
What: {title}
Validation: [pass/fail per command]
Blast radius: [one line]
Next: coordinator review
"""
    pr_title = f"{title} (#{number})"
    return {
        "issue": number,
        "lane": lane,
        "title": pr_title,
        "body": body.strip() + "\n",
        "gh_command": (
            f'gh pr create --base main --title "{pr_title}" '
            f'--body-file pr-{number}.issue-body.local.md'
        ),
        "hint": (
            f"Write the body to pr-{number}.issue-body.local.md (gitignored), "
            "then run the gh_command after pushing your branch."
        ),
    }


def write_pr_draft_file(draft: dict, *, path: Path | None = None) -> Path:
    target = path or (REPOSITORY_ROOT / f"pr-{draft['issue']}.issue-body.local.md")
    target.write_text(draft["body"], encoding="utf-8")
    return target
