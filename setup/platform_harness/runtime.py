"""Trusted subprocess runners and repository roots."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from .errors import IssueError

SETUP_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = SETUP_ROOT.parent
TAXONOMY_PATH = SETUP_ROOT / "project-taxonomy.json"

CommandRunner = Callable[[list[str]], str]
_gh_runner: CommandRunner | None = None
_git_runner: CommandRunner | None = None


def set_command_runners(
    *,
    gh: CommandRunner | None = None,
    git: CommandRunner | None = None,
) -> None:
    """Override subprocess runners (tests only). Pass None to restore defaults."""
    global _gh_runner, _git_runner
    _gh_runner = gh
    _git_runner = git


def gh_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GH_PROMPT_DISABLED": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
            "GH_PAGER": "cat",
            "PAGER": "cat",
            "GIT_PAGER": "cat",
            "NO_COLOR": "1",
        }
    )
    return env


def run_trusted(executable: str, args: list[str], *, timeout: int = 30) -> str:
    completed = subprocess.run(
        [executable, *args],
        cwd=REPOSITORY_ROOT,
        env=gh_environment(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise IssueError(detail or f"{executable} {' '.join(args)} failed")
    return completed.stdout


def run_git(args: list[str]) -> str:
    if _git_runner is not None:
        return _git_runner(args)
    return run_trusted("git", args)


def run_gh(args: list[str]) -> str:
    if _gh_runner is not None:
        return _gh_runner(args)
    return run_trusted("gh", args)
