"""Install / environment health checks for the coordination harness."""

from __future__ import annotations

import sys
from pathlib import Path

from .errors import IssueError
from .runtime import REPOSITORY_ROOT, SETUP_ROOT, run_gh, run_trusted
from .taxonomy import load_taxonomy


def _check(name: str, ok: bool, detail: str) -> dict:
    return {"check": name, "ok": ok, "detail": detail}


def run_doctor(*, probe_github: bool = True) -> dict:
    """Return a structured health report. Raises IssueError only for taxonomy load hard-fail."""
    checks: list[dict] = []

    py_ok = sys.version_info >= (3, 11)
    checks.append(
        _check(
            "python_version",
            py_ok,
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
    )

    try:
        taxonomy = load_taxonomy()
        checks.append(
            _check(
                "taxonomy",
                True,
                f"{len(taxonomy['lanes'])} lanes, {len(taxonomy['milestones'])} milestones",
            )
        )
    except IssueError as exc:
        checks.append(_check("taxonomy", False, str(exc)))
        taxonomy = None

    permissions = SETUP_ROOT / "agent-permissions.json"
    checks.append(
        _check(
            "permissions_source",
            permissions.is_file(),
            str(permissions.relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
        )
    )

    try:
        # Import lazily so doctor works even if sync script is mid-edit.
        sys.path.insert(0, str(SETUP_ROOT))
        from sync_harness_to_repo import DEFAULT_PATHS, IDENTITY_PATHS

        missing = [rel for rel in DEFAULT_PATHS + IDENTITY_PATHS if not (REPOSITORY_ROOT / rel).exists()]
        checks.append(
            _check(
                "sync_allowlist_paths",
                not missing,
                "all present" if not missing else f"missing: {', '.join(missing[:5])}",
            )
        )
    except Exception as exc:  # noqa: BLE001 — doctor must stay fail-soft
        checks.append(_check("sync_allowlist_paths", False, str(exc)[:200]))

    if probe_github:
        try:
            version = run_trusted("gh", ["--version"], timeout=10).splitlines()[0]
            checks.append(_check("gh_cli", True, version.strip()))
        except IssueError as exc:
            checks.append(_check("gh_cli", False, str(exc)[:200]))
        try:
            auth = run_gh(["auth", "status"])
            # auth status writes useful text to stderr sometimes; run_gh returns stdout.
            detail = (auth or "authenticated").strip().splitlines()[0][:120] or "ok"
            checks.append(_check("gh_auth", True, detail))
        except IssueError as exc:
            checks.append(_check("gh_auth", False, str(exc)[:200]))
    else:
        checks.append(_check("gh_cli", True, "skipped (--offline)"))
        checks.append(_check("gh_auth", True, "skipped (--offline)"))

    ok = all(item["ok"] for item in checks)
    return {
        "ok": ok,
        "repository_root": str(REPOSITORY_ROOT),
        "checks": checks,
    }
