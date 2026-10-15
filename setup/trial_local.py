#!/usr/bin/env python3
"""Bootstrap a local dogfood trial environment for this harness.

Prepares:
  - editable package install
  - GH_TOKEN from git credentials when unset (Windows-friendly)
  - doctor + label reconcile + milestone ensure
  - local agent permissions materialization
  - gitignored trial body/rationale templates
  - optional sibling git worktree for a worker claim loop
  - optional --smoke create→classify→claim→release→close cycle

Examples:
  python setup/trial_local.py
  python setup/trial_local.py --worktree
  python setup/trial_local.py --smoke
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup"
sys.path.insert(0, str(SETUP))

from platform_harness import IssueError, load_taxonomy, run_gh, run_git  # noqa: E402
from platform_harness.doctor import run_doctor  # noqa: E402
from platform_harness.taxonomy import parse_json  # noqa: E402


def _run(cmd: list[str], *, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=env or os.environ.copy(),
        text=True,
        capture_output=True,
        check=check,
    )


def ensure_gh_token() -> dict:
    """Populate GH_TOKEN from git credential helper when missing."""
    if (os.environ.get("GH_TOKEN") or "").strip() or (os.environ.get("GITHUB_TOKEN") or "").strip():
        return {"source": "environment", "set": True}
    proc = subprocess.run(
        ["git", "credential", "fill"],
        cwd=ROOT,
        input="protocol=https\nhost=github.com\n\n",
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if proc.returncode != 0:
        return {"source": "none", "set": False, "detail": (proc.stderr or "").strip()[:200]}
    password = None
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            password = line.split("=", 1)[1]
            break
    if not password:
        return {"source": "none", "set": False}
    os.environ["GH_TOKEN"] = password
    return {"source": "git-credential", "set": True}


def ensure_package() -> dict:
    result = _run([sys.executable, "-m", "pip", "install", "-e", ".", "-q"], check=False)
    return {
        "ok": result.returncode == 0,
        "detail": (result.stderr or result.stdout or "").strip()[-200:],
    }


def ensure_labels() -> dict:
    plan = _run([sys.executable, "setup/create_labels.py", "--plan"], check=False)
    if plan.returncode != 0:
        return {"ok": False, "detail": (plan.stderr or plan.stdout)[:300]}
    actions = parse_json(plan.stdout, "label plan")
    needed = [item for item in actions if item.get("action") in {"create", "update"}]
    if not needed:
        return {"ok": True, "created_or_updated": 0, "kept": len(actions)}
    apply = _run([sys.executable, "setup/create_labels.py"], check=False)
    if apply.returncode != 0:
        return {"ok": False, "detail": (apply.stderr or apply.stdout)[:300]}
    return {"ok": True, "created_or_updated": len(needed), "kept": len(actions) - len(needed)}


def ensure_milestones() -> dict:
    taxonomy = load_taxonomy()
    existing = parse_json(
        run_gh(["api", "repos/:owner/:repo/milestones", "--paginate"]),
        "milestones",
    )
    by_title = {item.get("title"): item for item in existing if isinstance(item, dict)}
    created = []
    kept = []
    for milestone in taxonomy["milestones"]:
        title = milestone["name"]
        if title in by_title:
            kept.append(title)
            continue
        run_gh(
            [
                "api",
                "--method",
                "POST",
                "repos/:owner/:repo/milestones",
                "-f",
                f"title={title}",
                "-f",
                f"description={milestone.get('description') or ''}",
            ]
        )
        created.append(title)
    return {"ok": True, "created": created, "kept": kept}


def write_templates() -> dict:
    body = ROOT / "trial-smoke.issue-body.local.md"
    rationale = ROOT / "trial-smoke.rationale.local.md"
    if not body.exists():
        body.write_text(
            "Local trial smoke issue for platform-agent-harness.\n\n"
            "What: exercise create → classify → claim → release via wrappers.\n"
            "Why: prove the local trial environment works end-to-end.\n"
            "Verify: claim succeeds, WIP label appears, release clears it.\n"
            "Tracking: none\n",
            encoding="utf-8",
        )
    if not rationale.exists():
        rationale.write_text(
            "Triage: hardening · P3 · lane:ci-cd · Phase 2: Developer Experience\n\n"
            "Local trial classify step. Safe to close after smoke.\n",
            encoding="utf-8",
        )
    return {"body_file": body.name, "rationale_file": rationale.name}


def ensure_worktree(*, path: Path, branch: str) -> dict:
    path = path.resolve()
    if path.exists():
        return {"ok": True, "path": str(path), "branch": branch, "existed": True}
    run_git(["fetch", "origin"])
    # Prefer branching from origin/main when available.
    try:
        run_git(["rev-parse", "--verify", "origin/main"])
        base = "origin/main"
    except IssueError:
        base = "main"
    _run(
        ["git", "worktree", "add", "-b", branch, str(path), base],
        check=True,
    )
    return {"ok": True, "path": str(path), "branch": branch, "existed": False}


def apply_permissions() -> dict:
    dry = _run([sys.executable, "setup/apply_permissions.py", "--dry-run"], check=False)
    if dry.returncode != 0:
        return {"ok": False, "detail": (dry.stderr or dry.stdout)[:300]}
    applied = _run([sys.executable, "setup/apply_permissions.py"], check=False)
    return {
        "ok": applied.returncode == 0,
        "detail": "materialized .claude/settings.local.json and .cursor/permissions.local.json",
    }


def _repo_issue_json(argv: list[str]) -> dict:
    """Run repo-issue CLI and parse its JSON stdout (stderr stays for errors)."""
    result = _run([sys.executable, "setup/repo_issue.py", *argv], check=False)
    if result.returncode != 0:
        raise IssueError((result.stderr or result.stdout or "repo_issue failed").strip()[:400])
    return parse_json(result.stdout, "repo_issue " + " ".join(argv[:1]))


def run_smoke(*, worker: str, worktree: Path | None) -> dict:
    body = write_templates()
    created = _repo_issue_json(
        [
            "create",
            "--title",
            "Trial smoke: local harness environment",
            "--body-file",
            body["body_file"],
            "--type",
            "hardening",
            "--priority",
            "P3",
            "--lane",
            "lane:ci-cd",
        ]
    )
    number = int(created["number"])
    _repo_issue_json(
        [
            "classify",
            "--issue",
            str(number),
            "--type",
            "hardening",
            "--priority",
            "P3",
            "--lane",
            "lane:ci-cd",
            "--milestone",
            "Phase 2: Developer Experience",
            "--rationale-file",
            body["rationale_file"],
        ]
    )
    branch = f"issue/{number}-trial-smoke"
    if worktree is not None:
        # Replace default trial branch with the claim branch in the worktree.
        if worktree.exists():
            _run(["git", "worktree", "remove", "--force", str(worktree)], check=False)
        ensure_worktree(path=worktree, branch=branch)
    else:
        try:
            run_git(["rev-parse", "--verify", branch])
        except IssueError:
            run_git(["branch", branch, "HEAD"])
    _repo_issue_json(
        [
            "claim",
            "--issue",
            str(number),
            "--lane",
            "lane:ci-cd",
            "--worker",
            worker,
            "--branch",
            branch,
        ]
    )
    draft = _repo_issue_json(["pr-draft", "--issue", str(number), "--write"])
    release_path = ROOT / f"trial-smoke-release-{number}.rationale.local.md"
    release_path.write_text(
        "Local trial smoke complete; releasing claim and closing issue.\n",
        encoding="utf-8",
    )
    try:
        _repo_issue_json(
            [
                "release",
                "--issue",
                str(number),
                "--mode",
                "abandon",
                "--reason-file",
                release_path.name,
            ]
        )
    finally:
        release_path.unlink(missing_ok=True)
    run_gh(
        [
            "issue",
            "close",
            str(number),
            "--comment",
            "Closed by setup/trial_local.py --smoke after successful local trial.",
        ]
    )
    return {
        "ok": True,
        "issue": number,
        "branch": branch,
        "draft_written": bool(draft.get("written")),
        "url": created.get("url"),
    }


def print_next_steps(report: dict) -> None:
    worktree = (report.get("worktree") or {}).get("path")
    print()
    print("=== Local trial environment ready ===")
    print(f"Repo: {ROOT}")
    print(f"Doctor score: {(report.get('doctor') or {}).get('score')}")
    print(f"GH token: {(report.get('gh_token') or {}).get('source')}")
    if worktree:
        print(f"Worker worktree: {worktree}")
    print()
    print("Try a manual loop (or re-run with --smoke):")
    print("  python setup/repo_issue.py list --state open")
    print("  python setup/repo_issue.py create --title \"...\" --body-file trial-smoke.issue-body.local.md \\")
    print("    --type hardening --priority P3 --lane lane:ci-cd")
    print("  python setup/repo_issue.py claim --issue <n> --lane lane:ci-cd --worker you --branch issue/<n>-slug")
    print("  python setup/repo_issue.py pr-draft --issue <n> --write")
    print("  python setup/repo_issue.py velocity --days 14")
    print()
    print("Guide: docs/guides/trial-install.md")
    print("Demo:  docs/guides/five-minute-demo.md")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worktree",
        action="store_true",
        help="Create sibling worktree ../platform-agent-harness-trial-worker",
    )
    parser.add_argument(
        "--worktree-path",
        default="",
        help="Custom worktree path (implies --worktree)",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run create→classify→claim→pr-draft→release→close against GitHub",
    )
    parser.add_argument("--worker", default="trial-local", help="Claim worker handle for --smoke")
    parser.add_argument(
        "--skip-permissions",
        action="store_true",
        help="Do not materialize local agent permission files",
    )
    args = parser.parse_args(argv)

    report: dict = {"repository_root": str(ROOT)}
    try:
        report["package"] = ensure_package()
        report["gh_token"] = ensure_gh_token()
        offline = run_doctor(probe_github=False)
        online = run_doctor(probe_github=True)
        report["doctor"] = {"offline": offline, "online": online, "score": online.get("score")}
        if not online.get("ok"):
            raise IssueError(f"doctor failed: {json.dumps(online, indent=2)}")
        report["labels"] = ensure_labels()
        if not report["labels"].get("ok"):
            raise IssueError(f"labels failed: {report['labels']}")
        report["milestones"] = ensure_milestones()
        report["templates"] = write_templates()
        if not args.skip_permissions:
            report["permissions"] = apply_permissions()
            if not report["permissions"].get("ok"):
                raise IssueError(f"permissions failed: {report['permissions']}")
        worktree_path = None
        if args.worktree or args.worktree_path:
            worktree_path = (
                Path(args.worktree_path)
                if args.worktree_path
                else ROOT.parent / "platform-agent-harness-trial-worker"
            )
            # With --smoke, the claim branch owns the worktree; skip the placeholder branch.
            if not args.smoke:
                report["worktree"] = ensure_worktree(
                    path=worktree_path, branch="trial/local-worker"
                )
        if args.smoke:
            report["smoke"] = run_smoke(worker=args.worker, worktree=worktree_path)
            if worktree_path is not None:
                report["worktree"] = {
                    "ok": True,
                    "path": str(worktree_path.resolve()),
                    "branch": report["smoke"].get("branch"),
                    "existed": False,
                }
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        print_next_steps(report)
        return 0
    except (IssueError, subprocess.CalledProcessError, OSError, json.JSONDecodeError) as exc:
        report["error"] = str(exc)[:500]
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.stderr.write(f"{exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
