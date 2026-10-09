"""argparse CLI for taxonomy-bound issue lifecycle."""

from __future__ import annotations

import argparse
import json
import sys
import time

from .doctor import run_doctor
from .errors import IssueError
from .issue_ops import (
    change_child_relation,
    claim_issue,
    classify_issue,
    create_issue,
    list_issues,
    mark_in_review,
    release_issue,
    view_issue,
)
from .taxonomy import load_taxonomy
from .telemetry import emit_event

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
    "doctor",
)


def _flag_args(namespace: argparse.Namespace, *keys: str, repeatable: tuple[str, ...] = ()) -> list[str]:
    """Rebuild argv-style flags for domain validators that still consume flag lists."""
    out: list[str] = []
    data = vars(namespace)
    for key in keys:
        flag = f"--{key.replace('_', '-')}"
        if key in repeatable:
            for value in data.get(key) or []:
                out.extend([flag, value])
            continue
        value = data.get(key)
        if value is None:
            continue
        out.extend([flag, str(value)])
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-issue",
        description="Taxonomy-bound GitHub issue lifecycle for the platform harness.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a classified issue (milestone usually empty)")
    create.add_argument("--title", required=True)
    create.add_argument("--body-file", required=True)
    create.add_argument("--type", required=True)
    create.add_argument("--priority", required=True)
    create.add_argument("--lane", required=True)
    create.add_argument("--concern", action="append", default=[])
    create.add_argument("--milestone")

    list_cmd = sub.add_parser("list", help="List issues in one batched gh call")
    list_cmd.add_argument("--state", choices=("open", "closed", "all"), default="open")

    view = sub.add_parser("view", help="View one issue")
    view.add_argument("--issue", required=True)

    classify = sub.add_parser("classify", help="Replace taxonomy classification + comment rationale")
    classify.add_argument("--issue", required=True)
    classify.add_argument("--type", required=True)
    classify.add_argument("--priority", required=True)
    classify.add_argument("--lane", required=True)
    classify.add_argument("--concern", action="append", default=[])
    classify.add_argument("--milestone")
    classify.add_argument("--rationale-file", required=True)

    for name in ("link-child", "unlink-child"):
        rel = sub.add_parser(name)
        rel.add_argument("--parent", required=True)
        rel.add_argument("--child", required=True)

    claim = sub.add_parser("claim", help="Fail-closed structured claim")
    claim.add_argument("--issue", required=True)
    claim.add_argument("--lane", required=True)
    claim.add_argument("--worker", required=True)
    claim.add_argument("--branch", required=True)

    release = sub.add_parser("release", help="Release claim; abandon or mark blocked")
    release.add_argument("--issue", required=True)
    release.add_argument("--mode", required=True, choices=("abandon", "blocked"))
    release.add_argument("--reason-file", required=True)

    review = sub.add_parser("in-review", help="Move status:wip → status:in-review")
    review.add_argument("--issue", required=True)

    doctor = sub.add_parser("doctor", help="Check taxonomy, sync paths, and optional gh auth")
    doctor.add_argument(
        "--offline",
        action="store_true",
        help="Skip gh CLI / auth probes (CI and air-gapped checks)",
    )

    return parser


def dispatch_namespace(namespace: argparse.Namespace) -> object:
    command = namespace.command
    if command == "doctor":
        return run_doctor(probe_github=not bool(getattr(namespace, "offline", False)))
    taxonomy = load_taxonomy()
    if command == "create":
        return create_issue(
            taxonomy,
            _flag_args(
                namespace,
                "title",
                "body_file",
                "type",
                "priority",
                "lane",
                "concern",
                "milestone",
                repeatable=("concern",),
            ),
        )
    if command == "list":
        return list_issues(_flag_args(namespace, "state"))
    if command == "view":
        return view_issue(_flag_args(namespace, "issue"))
    if command == "classify":
        return classify_issue(
            taxonomy,
            _flag_args(
                namespace,
                "issue",
                "type",
                "priority",
                "lane",
                "concern",
                "milestone",
                "rationale_file",
                repeatable=("concern",),
            ),
        )
    if command == "claim":
        return claim_issue(
            taxonomy,
            _flag_args(namespace, "issue", "lane", "worker", "branch"),
        )
    if command == "release":
        return release_issue(
            taxonomy,
            _flag_args(namespace, "issue", "mode", "reason_file"),
        )
    if command == "in-review":
        return mark_in_review(taxonomy, _flag_args(namespace, "issue"))
    if command in {"link-child", "unlink-child"}:
        return change_child_relation(
            _flag_args(namespace, "parent", "child"),
            unlink=command == "unlink-child",
        )
    raise IssueError(f"unknown command: {command}")


def dispatch(command: str, args: list[str]) -> object:
    """Backward-compatible dispatch used by older call sites/tests."""
    parser = build_parser()
    namespace = parser.parse_args([command, *args])
    return dispatch_namespace(namespace)


def main(argv: list[str] | None = None) -> int:
    started = time.monotonic()
    command = None
    try:
        parser = build_parser()
        namespace = parser.parse_args(argv)
        command = namespace.command
        result = dispatch_namespace(namespace)
        sys.stdout.write(f"{json.dumps(result, indent=2)}\n")
        duration_ms = int((time.monotonic() - started) * 1000)
        emit_event("command.ok", command=command, duration_ms=duration_ms)
        if command == "doctor" and isinstance(result, dict) and not result.get("ok"):
            return 1
        return 0
    except IssueError as error:
        duration_ms = int((time.monotonic() - started) * 1000)
        emit_event(
            "command.error",
            command=command,
            duration_ms=duration_ms,
            error_type="IssueError",
            error=str(error)[:500],
        )
        sys.stderr.write(f"{error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
