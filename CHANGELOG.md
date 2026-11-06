# Changelog

Format follows Keep a Changelog. Dates are UTC.

## [Unreleased] - 2026-11-06

- Tool and network policy in `CLAUDE.md` / worker skill / incident playbook (allowed hosts,
  forbidden credential paths, stop-and-comment on deny; ambient cloud credentials forbidden)
- Portable `claude_permissions.ask`/`deny` in `setup/agent-permissions.json`, materialized by
  `apply_permissions.py` (aligned with agent-pairing-kit; extra ssh/cloud-cred Bash mirrors)
- Workflow audit: no `pull_request_target` in `github-actions/` or `.github/workflows/`
- Taxonomy-bound issue wrappers, fail-closed claim protocol, portable permissions
- Ruff and mypy CI; attribution to the upstream agentic-dev-harness
- Removed unverifiable review-ledger entries
