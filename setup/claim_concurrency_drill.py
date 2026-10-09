#!/usr/bin/env python3
"""Live claim concurrency drill against the current repository.

Creates a temporary hardening issue, claims it as worker-a, then asserts a
second claim as worker-b fails closed. Cleans up by releasing and closing the
issue when possible.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SETUP = Path(__file__).resolve().parent
sys.path.insert(0, str(SETUP))

from platform_harness import IssueError, load_taxonomy  # noqa: E402
from platform_harness.issue_ops import claim_issue, create_issue, release_issue  # noqa: E402
from platform_harness.runtime import REPOSITORY_ROOT, run_gh  # noqa: E402


def main() -> int:
    taxonomy = load_taxonomy()
    body = REPOSITORY_ROOT / "claim-drill.issue-body.local.md"
    reason = REPOSITORY_ROOT / "claim-drill.rationale.local.md"
    body.write_text(
        "Temporary issue for claim concurrency drill. Safe to close.\n",
        encoding="utf-8",
    )
    reason.write_text("concurrency drill cleanup\n", encoding="utf-8")
    created = create_issue(
        taxonomy,
        [
            "--title",
            "TEMP claim concurrency drill",
            "--body-file",
            "claim-drill.issue-body.local.md",
            "--type",
            "hardening",
            "--priority",
            "P4",
            "--lane",
            "lane:platform-api",
        ],
    )
    number = created["number"]
    print(json.dumps({"created": created}, indent=2))
    first = claim_issue(
        taxonomy,
        [
            "--issue",
            str(number),
            "--lane",
            "lane:platform-api",
            "--worker",
            "drill-worker-a",
            "--branch",
            f"issue/{number}-drill-a",
        ],
    )
    print(json.dumps({"first_claim": {"number": first["number"], "claim_id": first["claim_id"]}}, indent=2))
    lost = False
    try:
        claim_issue(
            taxonomy,
            [
                "--issue",
                str(number),
                "--lane",
                "lane:platform-api",
                "--worker",
                "drill-worker-b",
                "--branch",
                f"issue/{number}-drill-b",
            ],
        )
    except IssueError as error:
        lost = True
        print(json.dumps({"second_claim": "failed_closed", "error": str(error)}, indent=2))
    if not lost:
        print("second claim unexpectedly succeeded", file=sys.stderr)
        return 1
    release_issue(
        taxonomy,
        [
            "--issue",
            str(number),
            "--mode",
            "abandon",
            "--reason-file",
            "claim-drill.rationale.local.md",
        ],
    )
    run_gh(["issue", "close", str(number), "--reason", "not planned"])
    body.unlink(missing_ok=True)
    reason.unlink(missing_ok=True)
    print(json.dumps({"drill": "passed", "issue": number}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except IssueError as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1)
