# Permissions and security

- Keep Allow All disabled.
- Committed permission sources use the portable placeholder `REPLACE_WITH_YOUR_REPO_GIT_ROOT`.
  Absolute roots are materialized only in gitignored local settings when the human applies
  permissions. `allowed_directories` must resolve to that root only.
- Every command identifier is an exact normalized prefix. A child subcommand does not authorize
  its parent or sibling commands.
- Run one bare executable per tool call. Do not use `cd`, chaining, pipes, loops, conditionals, or
  inline generated programs (`python -c`, etc.).
- Use `python setup/repo_issue.py` for issue create, list, view, classify, hierarchy, claim,
  release, and in-review. Do not substitute raw `gh issue` for those operations.
- Do not auto-approve `python:*`, `git push:*`, `gh api`, or `gh pr merge:*`. Push and merge stay
  human-gated; branch protection is still required server-side.
- Issue body and rationale files are scanned for common secret patterns before GitHub posts.
- `sync_harness_to_repo.py` refuses self-sync and requires `--force` before replacing existing
  destination directories.

Apply or refresh permissions only when the human requests it:

[`setup/permissions-setup.md`](../../setup/permissions-setup.md)
