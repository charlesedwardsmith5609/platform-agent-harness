#!/usr/bin/env python3
"""Copy allowlisted harness files into a consumer infrastructure checkout.

Does not overwrite consumer CLAUDE.md / docs/STATUS.md by default — those stay
repo-specific. Use --include-identity to force-refresh them from this harness
(usually wrong for real orgs; fine for sandbox resets).

Destructive directory replace requires --force. Prefer --dry-run first.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[1]

# Paths relative to harness root that every consumer needs.
DEFAULT_PATHS = [
    "setup/platform_harness",
    "setup/repo_issue.py",
    "setup/create_labels.py",
    "setup/create-labels.sh",
    "setup/create-labels.ps1",
    "setup/apply_permissions.py",
    "setup/apply_permissions.ps1",
    "setup/agent-permissions.json",
    "setup/project-taxonomy.json",
    "setup/wrapper-catalog.md",
    "setup/setup-guide.md",
    "setup/permissions-setup.md",
    "setup/claim_concurrency_drill.py",
    "setup/sync_harness_to_repo.py",
    "docs/guides/permissions-and-security.md",
    "docs/guides/trial-install.md",
    "docs/guides/project-board.md",
    "docs/guides/claim-concurrency-drill.md",
    "docs/guides/multi-repo-rollout.md",
    ".github/skills/workflow",
    ".github/skills/coding",
    ".github/workflows/harness-ci.yml",
    "github-actions/secrets-injection.yml",
    "playbooks",
    "tests/test_repo_issue.py",
    "tests/test_issue_mutations.py",
    "pyproject.toml",
    "LICENSE",
    ".gitignore",
]

IDENTITY_PATHS = [
    "CLAUDE.md",
    "docs/STATUS.md",
]


def validate_target(target: Path) -> Path:
    resolved = target.resolve()
    if resolved == HARNESS_ROOT.resolve():
        raise SystemExit("refusing to sync into the harness repository itself")
    git_dir = resolved / ".git"
    if not git_dir.exists():
        raise SystemExit(f"target is not a git checkout: {resolved}")
    # Require a real .git directory or file (worktree) — not a random folder named .git.
    if not (git_dir.is_dir() or git_dir.is_file()):
        raise SystemExit(f"target .git is not a directory or worktree file: {resolved}")
    return resolved


def validate_rel(rel: str) -> None:
    if not rel or rel.startswith("/") or rel.startswith("\\") or ".." in Path(rel).parts:
        raise SystemExit(f"refusing path that escapes harness root: {rel}")


def copy_path(src_root: Path, dst_root: Path, rel: str, *, force: bool) -> str:
    validate_rel(rel)
    src = (src_root / rel).resolve()
    dst = (dst_root / rel).resolve()
    try:
        src.relative_to(src_root.resolve())
        dst.relative_to(dst_root.resolve())
    except ValueError as exc:
        raise SystemExit(f"path escapes repository root: {rel}") from exc
    if not src.exists():
        raise FileNotFoundError(f"missing harness path: {rel}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            if not force:
                raise SystemExit(
                    f"refusing to replace existing directory without --force: {rel}"
                )
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        return f"dir:{rel}"
    shutil.copy2(src, dst)
    return f"file:{rel}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        required=True,
        help="Absolute path to the consumer repository checkout",
    )
    parser.add_argument(
        "--include-identity",
        action="store_true",
        help="Also overwrite CLAUDE.md and docs/STATUS.md (dangerous for real orgs)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow replacing existing destination directories (rmtree)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    target = validate_target(Path(args.target))
    paths = list(DEFAULT_PATHS)
    if args.include_identity:
        paths.extend(IDENTITY_PATHS)
    for rel in paths:
        validate_rel(rel)
    if args.dry_run:
        json.dump(
            {
                "target": str(target),
                "would_copy": paths,
                "force": bool(args.force),
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0
    copied = [
        copy_path(HARNESS_ROOT, target, rel, force=bool(args.force)) for rel in paths
    ]
    json.dump({"target": str(target), "copied": copied}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
