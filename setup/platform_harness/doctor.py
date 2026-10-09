"""Install / environment health checks and adoption scorecards."""

from __future__ import annotations

import sys
from pathlib import Path

from .errors import IssueError
from .runtime import REPOSITORY_ROOT, SETUP_ROOT, run_gh, run_trusted
from .taxonomy import load_taxonomy

# Relative paths a consumer checkout should have after sync (identity files optional).
ADOPTION_REQUIRED = (
    "setup/repo_issue.py",
    "setup/project-taxonomy.json",
    "setup/platform_harness",
    "setup/wrapper-catalog.md",
    "setup/create_labels.py",
    ".github/skills/workflow/multi-agent-coordination.md",
    ".github/skills/coding/platform-engineering.md",
    ".github/workflows/harness-ci.yml",
    "pyproject.toml",
)
ADOPTION_RECOMMENDED = (
    "CLAUDE.md",
    "docs/STATUS.md",
    "docs/guides/trial-install.md",
    ".github/workflows/pr-gate.yml",
    "playbooks/status-reporting.md",
    "LICENSE",
)


def _check(name: str, ok: bool, detail: str, *, weight: int = 1) -> dict:
    return {"check": name, "ok": ok, "detail": detail, "weight": weight}


def _score(checks: list[dict]) -> int:
    total = sum(int(item.get("weight") or 1) for item in checks)
    if total <= 0:
        return 0
    earned = sum(int(item.get("weight") or 1) for item in checks if item.get("ok"))
    return int(round(100.0 * earned / total))


def _harness_self_checks(*, probe_github: bool, root: Path) -> list[dict]:
    checks: list[dict] = []
    py_ok = sys.version_info >= (3, 11)
    checks.append(
        _check(
            "python_version",
            py_ok,
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            weight=2,
        )
    )

    taxonomy_path = root / "setup" / "project-taxonomy.json"
    try:
        if root.resolve() == REPOSITORY_ROOT.resolve():
            taxonomy = load_taxonomy()
        else:
            taxonomy = load_taxonomy(taxonomy_path)
        has_wip = any("wip_limit" in lane for lane in taxonomy.get("lanes") or [])
        checks.append(
            _check(
                "taxonomy",
                True,
                f"{len(taxonomy['lanes'])} lanes, {len(taxonomy['milestones'])} milestones"
                + ("; wip_limit set" if has_wip else ""),
                weight=3,
            )
        )
    except IssueError as exc:
        checks.append(_check("taxonomy", False, str(exc), weight=3))

    permissions = root / "setup" / "agent-permissions.json"
    checks.append(
        _check(
            "permissions_source",
            permissions.is_file(),
            str(permissions.relative_to(root)).replace("\\", "/")
            if permissions.is_file()
            else "missing",
            weight=2,
        )
    )

    try:
        sys.path.insert(0, str(root / "setup"))
        # Prefer consumer copy of sync allowlist when present.
        from sync_harness_to_repo import DEFAULT_PATHS, IDENTITY_PATHS

        missing = [rel for rel in DEFAULT_PATHS + IDENTITY_PATHS if not (root / rel).exists()]
        checks.append(
            _check(
                "sync_allowlist_paths",
                not missing,
                "all present" if not missing else f"missing: {', '.join(missing[:5])}",
                weight=3,
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("sync_allowlist_paths", False, str(exc)[:200], weight=3))

    if probe_github:
        try:
            version = run_trusted("gh", ["--version"], timeout=10).splitlines()[0]
            checks.append(_check("gh_cli", True, version.strip(), weight=1))
        except IssueError as exc:
            checks.append(_check("gh_cli", False, str(exc)[:200], weight=1))
        try:
            auth = run_gh(["auth", "status"])
            detail = (auth or "authenticated").strip().splitlines()[0][:120] or "ok"
            checks.append(_check("gh_auth", True, detail, weight=1))
        except IssueError as exc:
            checks.append(_check("gh_auth", False, str(exc)[:200], weight=1))
    else:
        checks.append(_check("gh_cli", True, "skipped (--offline)", weight=1))
        checks.append(_check("gh_auth", True, "skipped (--offline)", weight=1))
    return checks


def _adoption_checks(target: Path) -> list[dict]:
    checks: list[dict] = []
    git_ok = (target / ".git").exists()
    checks.append(
        _check("git_checkout", git_ok, str(target), weight=2),
    )
    for rel in ADOPTION_REQUIRED:
        path = target / rel
        checks.append(
            _check(
                f"required:{rel}",
                path.exists(),
                "present" if path.exists() else "missing",
                weight=3,
            )
        )
    for rel in ADOPTION_RECOMMENDED:
        path = target / rel
        checks.append(
            _check(
                f"recommended:{rel}",
                path.exists(),
                "present" if path.exists() else "missing",
                weight=1,
            )
        )
    return checks


def run_doctor(
    *,
    probe_github: bool = True,
    target: str | Path | None = None,
) -> dict:
    """Return a structured health / adoption report with a 0–100 score."""
    if target is None:
        root = REPOSITORY_ROOT
        checks = _harness_self_checks(probe_github=probe_github, root=root)
        mode = "self"
    else:
        root = Path(target).resolve()
        if not root.is_dir():
            raise IssueError(f"doctor --target is not a directory: {root}")
        # Adoption scorecard: file presence + optional self checks if harness files exist.
        checks = _adoption_checks(root)
        if (root / "setup" / "project-taxonomy.json").is_file():
            checks.extend(_harness_self_checks(probe_github=probe_github, root=root))
        mode = "adoption"
    score = _score(checks)
    # Recommended:* misses lower the score but do not fail the gate.
    ok = all(
        item["ok"]
        for item in checks
        if not str(item["check"]).startswith("recommended:")
    )
    return {
        "ok": ok,
        "mode": mode,
        "score": score,
        "repository_root": str(root),
        "checks": checks,
    }
