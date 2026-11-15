# Step 1 - HIGH findings (1, 2)

## Findings covered
1. Body-file check accepts `.env` and other secret files.
2. Auto-approved git prefixes and unittest bypass the denies.

## Types
- `ignored_issue_file(repository_root, relpath, description) -> Path` gains a required-suffix rule (`.local.md`).
- `agent-permissions.json` `commandIdentifiers`: list of strings, narrowed.
- Materialized permissions go through `setup/apply_permissions.py` validation.

## Shared state ownership
- `setup/platform_harness/` and the claim protocol are coordinator-owned. Coordinator approval is required before the code step; this plan does not touch `project-taxonomy.json`.
- `setup/agent-permissions.json` is the portable permission source (single owner: coordinator).

## Design notes (assumptions, D14: safer reading)
- Remove `git remote:*`, `git stash:*`, `git worktree:*`, `git pull:*`, `git branch:*` from the allowlist. Replace with exact read-only forms (`git remote -v`, `git branch --list`, `git branch --show-current`) where needed.
- `git diff:*`, `git log:*`, `git show:*` allow `--output`; the prefix style cannot constrain arguments, so replace with exact argument forms or add Bash deny patterns for `--output*`, `--no-index*`, `--upload-pack*`, `--exec*`.
- `python -m unittest:*` can run arbitrary test files that write; restrict to `python -m unittest discover -s tests*`.
- No new dependencies (D12).

## Tests (written failing first)
- Body file named `.env` (git-ignored, in repo) is rejected for lacking `.local.md`.
- Body file `notes.txt` and `x.local.md.bak` are rejected; `x.issue-body.local.md` is accepted.
- Body file path through a symlinked directory pointing outside the repo is rejected.
- Allowlist contains no entry for `git remote:*`, `git stash:*`, `git worktree:*`, `git pull:*`.
- No allowlist entry can match `git diff --output=x`, `git log --output=x`, `git diff --no-index a b`, or `git fetch --upload-pack=cmd` (one test per bypass, using a prefix matcher over the shipped list plus deny patterns).
- `python -m unittest some_writer` is not matched; `python -m unittest discover -s tests` is.
- `apply_permissions.py --dry-run` still succeeds.

## Files
- `setup/platform_harness/taxonomy.py`
- `setup/agent-permissions.json`
- `setup/apply_permissions.py`
- `tests/test_repo_issue.py`
- `setup/permissions-setup.md`
- `CHANGELOG.md`
- `DECISIONS.md`
