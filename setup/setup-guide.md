# Setup guide index

Do not copy files by ad-hoc `cp`. Use the documented entry points:

| Goal | Doc | Command |
|---|---|---|
| Health check before install | [`wrapper-catalog.md`](wrapper-catalog.md) | `python setup/repo_issue.py doctor [--offline]` |
| Dogfood this harness on itself | [`docs/guides/trial-install.md`](../docs/guides/trial-install.md) | `python setup/create_labels.py` then `python setup/repo_issue.py` |
| Install into a consumer infra repo | [`docs/guides/multi-repo-rollout.md`](../docs/guides/multi-repo-rollout.md) | `python setup/sync_harness_to_repo.py --target <path> --dry-run` |
| Issue create/claim/classify | [`wrapper-catalog.md`](wrapper-catalog.md) | `python setup/repo_issue.py …` |
| Agent allowlist | [`permissions-setup.md`](permissions-setup.md) | `python setup/apply_permissions.py --dry-run` (human only) |
| Audit telemetry | [`wrapper-catalog.md`](wrapper-catalog.md) | `HARNESS_TELEMETRY=1` and/or `AGENT_AUDIT_LOG=<path>` |

Milestones must match `setup/project-taxonomy.json` names. Create them with `gh api`
(see trial-install); do not use `gh milestone create` — it is not available on all
GitHub CLI versions.

`docs/STATUS.md` and `CLAUDE.md` already exist in this repo; adapt them, do not recreate
from scratch.
