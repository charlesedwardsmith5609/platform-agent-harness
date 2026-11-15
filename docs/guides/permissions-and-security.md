# Permissions and security

- Keep Allow All disabled.
- Committed permission sources use the portable placeholder `REPLACE_WITH_YOUR_REPO_GIT_ROOT`.
  Absolute roots are materialized only in gitignored local settings when the human applies
  permissions. `allowed_directories` must resolve to that root only.
- `setup/agent-permissions.json` also declares `claude_permissions.ask` (at least `WebFetch`) and
  `claude_permissions.deny` for environ/env/ssh/cloud-cred/metadata paths. Apply with
  `python setup/apply_permissions.py`. These reduce accidental exposure; they are a seatbelt, not a sandbox —
  Bash can bypass `Read` denies unless matching Bash patterns are denied, and Bash deny
  patterns match literal strings, so variables, encoding or another tool bypass them trivially.
- Absolute paths in `Read` rules use `//` (`Read(//proc/**/environ)`); a single leading `/`
  anchors at the settings source.
- The committed kit file `.claude/settings.json` is separate from `apply_permissions.py` output
  (`.claude/settings.local.json`). It disables claude.ai connectors and artifacts, asks before
  `WebFetch`, and denies a shorter list (its two absolute-path `Read` rules use `//`). See
  [`setup/permissions-setup.md`](../../setup/permissions-setup.md#relation-to-claudesettingsjson-kit).
- Allowed network: GitHub via approved `gh` / wrappers; `127.0.0.1` / `localhost` for tests.
  Other hosts need prior approval on the issue. Never use ambient cloud credentials; see
  `CLAUDE.md` and `playbooks/incident-response.md`.
- Every command identifier is an exact normalized prefix. A child subcommand does not authorize
  its parent or sibling commands. The allowlist has no `git remote:*`, `git pull:*`, `git stash:*`,
  `git worktree:*` or `git branch:*` prefixes (only `git remote -v`, `git branch --list`,
  `git branch --show-current`), and `unittest` is limited to `python -m unittest discover -s tests`.
- Run one bare executable per tool call. Do not use `cd`, chaining, pipes, loops, conditionals, or
  inline generated programs (`python -c`, etc.).
- Use `python setup/repo_issue.py` for issue create, list, view, classify, hierarchy, claim,
  release, and in-review. Do not substitute raw `gh issue` for those operations.
- Do not auto-approve `python:*`, `git push:*`, `gh api`, or `gh pr merge:*`. Push and merge stay
  human-gated; branch protection is still required server-side.
- Issue body, rationale and reason files must end in `.local.md`, be Git-ignored, and be physical
  files inside the repository: a symlink at any path component under the repository root
  (including a symlinked parent directory) is rejected. They are scanned for common secret
  patterns before GitHub posts.
- Issue titles are rejected for control characters, shell metacharacters (backtick, `;`, `|`, `&`,
  `<`, `>`, backslash, `$(`, `${`) and `../` segments; apostrophes, double quotes and `..` inside
  words are allowed. `pr-draft` returns a quoted `gh_command` (POSIX or Windows quoting) and the
  portable `gh_argv`.
- `sync_harness_to_repo.py` refuses self-sync and requires `--force` before replacing existing
  destination directories.

Apply or refresh permissions only when the human requests it:

[`setup/permissions-setup.md`](../../setup/permissions-setup.md)
