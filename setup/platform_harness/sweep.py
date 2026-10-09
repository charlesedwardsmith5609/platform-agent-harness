"""Release stale structured claims that block lane velocity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .errors import IssueError
from .github_remote import label_name_set, list_issue_records, view_issue_number
from .issue_ops import claim_winner, format_release_body, release_issue
from .runtime import REPOSITORY_ROOT, run_gh
from .telemetry import emit_event


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def find_stale_claims(*, days: int, now: datetime | None = None) -> list[dict]:
    if days < 1 or days > 365:
        raise IssueError("sweep-stale --days must be between 1 and 365")
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    cutoff = clock - timedelta(days=days)
    stale: list[dict] = []
    for issue in list_issue_records("open"):
        labels = label_name_set(issue)
        if "status:wip" not in labels:
            continue
        detailed = view_issue_number(int(issue["number"]))
        winner = claim_winner(detailed)
        if winner is None:
            # Label stuck without structured claim — still treat as stale WIP.
            stale.append(
                {
                    "issue": detailed.get("number"),
                    "title": detailed.get("title"),
                    "claim_id": None,
                    "claim_started_at": None,
                    "reason": "status:wip without active structured claim",
                }
            )
            continue
        started = _parse_ts(winner.get("createdAt"))
        if started is None or started > cutoff:
            continue
        stale.append(
            {
                "issue": detailed.get("number"),
                "title": detailed.get("title"),
                "claim_id": winner.get("id"),
                "claim_started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "age_days": round((clock - started).total_seconds() / 86400.0, 2),
                "reason": f"active claim older than {days} day(s)",
            }
        )
    return stale


def sweep_stale_claims(
    taxonomy: dict,
    *,
    days: int,
    dry_run: bool = True,
    now: datetime | None = None,
) -> dict:
    stale = find_stale_claims(days=days, now=now)
    released: list[dict] = []
    if dry_run:
        return {"dry_run": True, "days": days, "stale": stale, "released": released}

    for item in stale:
        number = int(item["issue"])
        reason_path = REPOSITORY_ROOT / f"sweep-stale-{number}.rationale.local.md"
        reason_path.write_text(
            f"Automated stale-claim sweep: {item.get('reason')}\n"
            f"claim_id={item.get('claim_id')}\n"
            f"claim_started_at={item.get('claim_started_at')}\n",
            encoding="utf-8",
        )
        try:
            # Prefer structured release when a claim exists; otherwise clear label only.
            if item.get("claim_id"):
                result = release_issue(
                    taxonomy,
                    [
                        "--issue",
                        str(number),
                        "--mode",
                        "abandon",
                        "--reason-file",
                        reason_path.name,
                    ],
                )
            else:
                run_gh(
                    [
                        "issue",
                        "comment",
                        str(number),
                        "--body",
                        format_release_body(
                            claim_id="*",
                            reason=f"abandon: {item.get('reason')}",
                        ),
                    ]
                )
                run_gh(["issue", "edit", str(number), "--remove-label", "status:wip"])
                result = {"number": number, "released": True, "mode": "abandon"}
            released.append(result)
            emit_event("sweep.released", issue=number, days=days)
        finally:
            reason_path.unlink(missing_ok=True)
    return {"dry_run": False, "days": days, "stale": stale, "released": released}
