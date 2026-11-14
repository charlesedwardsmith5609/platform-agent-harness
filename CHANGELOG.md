# Changelog

Format follows Keep a Changelog. Dates are UTC.

## [Unreleased] - 2026-11-06

- Review fixes (PR #24, step 2): `Read` denies for `/proc/**/environ` and `/var/run/secrets/**` use the documented `//` absolute-path form; docs say Bash denies are a seatbelt, not a sandbox; title errors name the specific reason.
- Review fixes (PR #24, step 1): `--body-file`/`--rationale-file`/`--reason-file` must end in `.local.md` (a Git-ignored `.env` is no longer accepted). The auto-approved command list drops `git remote/pull/stash/worktree/branch` prefixes, narrows `unittest` to `discover -s tests`, and denies `--output`, `--no-index`, `--upload-pack` and `--exec` forms.
- Untrusted input: issue text is data, never instructions, in the security-hardening skill and both worker loops.
- Issue titles reject control characters, shell metacharacters and `../` segments; apostrophes, double quotes and `..` inside words are accepted. `pr-draft` shell-quotes the title so a hostile GitHub title stays one argument.
- Tool and network policy in `CLAUDE.md` / worker skill / incident playbook (allowed hosts,
  forbidden credential paths, stop-and-comment on deny; ambient cloud credentials forbidden)
- Portable `claude_permissions.ask`/`deny` in `setup/agent-permissions.json`, materialized by
  `apply_permissions.py` (aligned with agent-pairing-kit; extra ssh/cloud-cred Bash mirrors)
- Workflow audit: no `pull_request_target` in `github-actions/` or `.github/workflows/`
- Taxonomy-bound issue wrappers, fail-closed claim protocol, portable permissions
- Ruff and mypy CI; attribution to the upstream agentic-dev-harness
- Removed unverifiable review-ledger entries
