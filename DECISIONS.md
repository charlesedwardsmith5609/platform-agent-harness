# Decisions

## 2026-11-13: Catch-up branch includes the unmerged worker policy

Context: `improve/tldr-2026-11-05` (`87eb4f9`) is one commit ahead of `main` and not behind it. That commit documents the worker tool and network policy and Claude deny defaults.

Choice: `improve/tldr-catchup-2026-11-13` is cut from that commit.

Why: The commit is unmerged. Cutting from `main` would drop it.

## 2026-11-13: Ambient credentials are already covered

Context: The Nov 5 digest says workers must not use ambient cloud credentials.

Evidence: `CLAUDE.md` section "Ambient credentials (incident-informed)", `playbooks/incident-response.md` section "Agent credentials (incident-informed)", and `setup/agent-permissions.json` deny rules. The tests in `tests/test_repo_issue.py` assert a deny entry for `.aws/credentials`.

Choice: do not add a second copy of the rule. The untrusted-input section points workers at the existing tool and network policy.
