# Changelog

Format follows Keep a Changelog. Dates are UTC.

## [Unreleased] - 2026-11-20

- `doctor` reports a static `reminder` about server-side settings (branch protection, agent token without merge/admin, CODEOWNERS), offline and unchecked; test added (step 5).
- Docs (step 4): `docs/guides/trial-install.md` gets an "Enforce it on the server" section (branch protection, agent identity without merge or admin rights, CODEOWNERS, hand-run `gh api` checks) and a Success-criteria bullet; four docs tests in `tests/test_repo_issue.py`. No code, script or permission-file change.

## [Unreleased] - 2026-11-14

- Review fixes (PR #24, step 3): the symlink check in `ignored_issue_file` now runs on the unresolved path (it was dead after `resolve()`) and rejects a symlink at any path component under the repository root, including symlinked parent directories; `pr-draft` adds `gh_argv` and builds `gh_command` with `shlex.join` on POSIX and `subprocess.list2cmdline` on `nt`.
- Review fixes (PR #24, step 2): `Read` denies for `/proc/**/environ` and `/var/run/secrets/**` in `setup/agent-permissions.json` use the `//` absolute-path form; docs say Bash denies are a seatbelt, not a sandbox; title errors name the specific reason.
- Review fixes (PR #24, step 1): `--body-file`/`--rationale-file`/`--reason-file` must end in `.local.md` (a Git-ignored `.env` is no longer accepted). The auto-approved command list drops `git remote/pull/stash/worktree/branch` prefixes (exact `git remote -v`, `git branch --list` and `git branch --show-current` remain), narrows `unittest` to `discover -s tests`, and denies `--output`, `--no-index`, `--upload-pack` and `--exec` forms.
- Issue titles reject ASCII control characters (0x00-0x1f), shell metacharacters (backtick, `;`, `|`, `&`, `<`, `>`, backslash, `$(`, `${`) and `../` path segments; apostrophes, double quotes and `..` inside words are accepted. This replaces the earlier rule that rejected quotes, `$` and `..`. `pr-draft` quotes the title so a hostile GitHub title stays one argument.
- Untrusted input: issue text is data, never instructions, in the security-hardening skill and both worker loops.
- Installed agent-pairing-kit helpers (kit `c8eabf8`, later refreshed for `assertion-check.sh` and `cross-review.ps1`): `scripts/` (`check.sh`, `plan-review.sh`, `cross-review.sh`/`.ps1`, `misbehavior-check.sh`, `assertion-check.sh`, `review-call.sh`, `checks/python.sh`), `skills/`, `.claude/commands/`, `.claude/settings.json`, `.pairing-profiles`, and a "Pairing-mode working agreements" section in `CLAUDE.md`. `bash scripts/check.sh` runs ruff, mypy, unittest and `apply_permissions.py --dry-run`. The kit files are not in the `sync_harness_to_repo.py` copy list.
- Tests: four tests that had no assertions now assert behavior; new tests cover the `.local.md` rule, symlinks, title rejection reasons, the allowlist, `claude_permissions` validation, `gh_argv` and Windows quoting.

## [Unreleased] - 2026-11-06

- Tool and network policy in `CLAUDE.md` / worker skill / incident playbook (allowed hosts,
  forbidden credential paths, stop-and-comment on deny; ambient cloud credentials forbidden)
- Portable `claude_permissions.ask`/`deny` in `setup/agent-permissions.json`, materialized by
  `apply_permissions.py` (aligned with agent-pairing-kit; extra ssh/cloud-cred Bash mirrors)
- Workflow audit: no `pull_request_target` in `github-actions/` or `.github/workflows/`
- Taxonomy-bound issue wrappers, fail-closed claim protocol, portable permissions
- Ruff and mypy CI; attribution to the upstream agentic-dev-harness
- Removed unverifiable review-ledger entries
