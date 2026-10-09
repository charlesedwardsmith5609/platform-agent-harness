#!/usr/bin/env python3
"""Lightweight PR gate for coordination hygiene.

Fails when:
- PR body lacks Closes #<n>
- PR body lacks a Blast radius section
- Diff touches shared-foundation paths without 'foundation/' branch or
  'lane:foundation' mentioned in body/title (coordinator signal)

Designed for GitHub Actions; also runnable locally against an event JSON or
with --body-file / --diff-files for tests.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

CLOSES_RE = re.compile(r"(?i)\bcloses\s+#([1-9]\d*)\b")
BLAST_RE = re.compile(r"(?im)^##\s*blast radius\b")

# Paths that require coordinator/foundation signal in this harness and fleet copies.
FOUNDATION_PREFIXES = (
    "setup/project-taxonomy.json",
    "setup/platform_harness/",
    "foundation/",
)


def load_event(path: Path | None) -> dict:
    if path is None:
        env = os.environ.get("GITHUB_EVENT_PATH")
        if not env:
            return {}
        path = Path(env)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def collect_findings(
    *,
    body: str,
    title: str,
    branch: str,
    changed_files: list[str],
) -> list[str]:
    findings: list[str] = []
    if not CLOSES_RE.search(body or ""):
        findings.append("PR body must include `Closes #<issue>` for auto-close linkage")
    if not BLAST_RE.search(body or ""):
        findings.append("PR body must include a `## Blast radius` section")
    foundation_hits = [
        path
        for path in changed_files
        if any(path == prefix or path.startswith(prefix) for prefix in FOUNDATION_PREFIXES)
    ]
    if foundation_hits:
        coordinator_signal = (
            branch.startswith("foundation/")
            or "lane:foundation" in (body or "").lower()
            or "lane:foundation" in (title or "").lower()
            or "foundation" in (title or "").lower()
        )
        if not coordinator_signal:
            findings.append(
                "foundation-path changes require a foundation/* branch or explicit "
                f"lane:foundation signal in title/body (touched: {', '.join(foundation_hits[:5])})"
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, help="GitHub event JSON path")
    parser.add_argument("--body-file", type=Path, help="PR body file (tests/local)")
    parser.add_argument("--title", default="")
    parser.add_argument("--branch", default="")
    parser.add_argument(
        "--diff-files",
        type=Path,
        help="Newline-separated file paths changed in the PR",
    )
    parser.add_argument("--warn-only", action="store_true")
    args = parser.parse_args(argv)

    event = load_event(args.event)
    pr = event.get("pull_request") or {}
    body = (args.body_file.read_text(encoding="utf-8") if args.body_file else None) or (
        pr.get("body") or ""
    )
    title = args.title or pr.get("title") or ""
    branch = args.branch or (pr.get("head") or {}).get("ref") or ""
    if args.diff_files and args.diff_files.is_file():
        changed = [
            line.strip().replace("\\", "/")
            for line in args.diff_files.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        changed = []
        # Local/Actions without explicit list: try git if available via subprocess-free env.
        # Actions should pass --diff-files from `git diff --name-only`.
    findings = collect_findings(
        body=body, title=title, branch=branch, changed_files=changed
    )
    result = {"ok": not findings, "findings": findings}
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    if findings and not args.warn_only:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
