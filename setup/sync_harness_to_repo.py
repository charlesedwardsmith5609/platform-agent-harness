#!/usr/bin/env python3
"""Copy allowlisted harness files into a consumer infrastructure checkout.

Does not overwrite consumer CLAUDE.md / docs/STATUS.md by default — those stay
repo-specific. Use --include-identity to force-refresh them from this harness
(usually wrong for real orgs; fine for sandbox resets).
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
    "tests/test_repo_issue.py",
    "tests/test_issue_mutations.py",
    "pyproject.toml",
    ".gitignore",
]

IDENTITY_PATHS = [
    "CLAUDE.md",
    "docs/STATUS.md",
]


def copy_path(src_root: Path, dst_root: Path, rel: str) -> str:
    src = src_root / rel
    dst = dst_root / rel
    if not src.exists():
        raise FileNotFoundError(f"missing harness path: {rel}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    target = Path(args.target).resolve()
    if not (target / ".git").exists():
        print(f"target is not a git checkout: {target}", file=sys.stderr)
        return 1
    paths = list(DEFAULT_PATHS)
    if args.include_identity:
        paths.extend(IDENTITY_PATHS)
    planned = []
    for rel in paths:
        planned.append(rel)
    if args.dry_run:
        json.dump({"target": str(target), "would_copy": planned}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    copied = [copy_path(HARNESS_ROOT, target, rel) for rel in paths]
    json.dump({"target": str(target), "copied": copied}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
