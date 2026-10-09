# Session permissions setup

This harness uses a reviewable **per-repo allowlist** instead of blanket Allow All. Repository
source declares routine capabilities; the human applies that source to machine-local settings,
then starts a new agent session.

## Files

- `setup/agent-permissions.json` — portable command policy. The location key is the placeholder
  `REPLACE_WITH_YOUR_REPO_GIT_ROOT`, never a machine-specific absolute path.
- `setup/apply_permissions.py` — substitutes the current Git root and writes gitignored local files.
- `.claude/settings.local.json` — Claude Code allowlist (generated, not committed).
- `.cursor/permissions.local.json` — resolved copy for Cursor-side review (generated, not committed).

## Matching granularity

Treat every identifier as an exact normalized prefix. A permission for a child command never grants
its parent or siblings.

- use `git push:*`, not `git push origin:*`;
- `gh issue:*` does not authorize `gh pr` or `gh api`;
- Git global options before the subcommand change the identifier. Do not run `git -c ...`.

Do not add `gh api` (including GraphQL) to the source. Issue hierarchy uses `gh issue edit`
`--add-sub-issue` / `--remove-parent` through `setup/repo_issue.py`.

`python:*` is repo-local because the issue and permission wrappers are Python. Do not use that
approval to run inline programs; use the named setup scripts.

`git push:*` cannot distinguish `--force`. Protect the default branch server-side against
non-fast-forward pushes and branch deletion before enabling it.

The source excludes destructive git (`reset`, `clean`, `checkout`), account management, package
installers, and blanket MCP access.

## Apply

1. Turn off Allow All.
2. From the repo root, preview:

   ```bash
   python setup/apply_permissions.py --dry-run
   ```

3. Apply (writes gitignored local files only):

   ```bash
   python setup/apply_permissions.py
   ```

4. Restart the agent session. Permission files load at session start.

Do not hand-edit generated local files to add absolute sibling or home paths. Change
`setup/agent-permissions.json` and re-apply instead.
