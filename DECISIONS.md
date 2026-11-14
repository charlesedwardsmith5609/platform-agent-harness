# Decisions

## 2026-11-13: Catch-up branch includes the unmerged worker policy

Context: `improve/tldr-2026-11-05` (`87eb4f9`) is one commit ahead of `main` and not behind it. That commit documents the worker tool and network policy and Claude deny defaults.

Choice: `improve/tldr-catchup-2026-11-13` is cut from that commit.

Why: The commit is unmerged. Cutting from `main` would drop it.

## 2026-11-13: Ambient credentials are already covered

Context: The Nov 5 digest says workers must not use ambient cloud credentials.

Evidence: `CLAUDE.md` section "Ambient credentials (incident-informed)", `playbooks/incident-response.md` section "Agent credentials (incident-informed)", and `setup/agent-permissions.json` deny rules. The tests in `tests/test_repo_issue.py` assert a deny entry for `.aws/credentials`.

Choice: do not add a second copy of the rule. The untrusted-input section points workers at the existing tool and network policy.

## 2026-11-13: Issue text can reach a shell string, so it is quoted

Context: `run_trusted` uses `shell=False`, so a title passed as an argv element is not parsed by a shell. `build_pr_draft` used to embed the GitHub issue title inside double quotes in `gh_command`. A title already stored on GitHub does not pass through `validate_title`. `--body-file` is a path the caller supplies. `ignored_issue_file` resolves it and rejects paths outside the repository.

Choice: `validate_title` rejects quotes, backticks, `$`, `;`, backslash, and `..`. `gh_command` uses `shlex.quote` on the title and the body file name. The issue body stays in the draft markdown and is not copied into the command.

Why: Rejecting the characters at create time does not protect a title that is already on GitHub. Quoting the command does. No new dependency.

## 2026-11-14: Body files must be `.local.md`; the allowlist drops argument-sensitive prefixes

Context: Review of PR #24 found that `ignored_issue_file` accepted any Git-ignored file in the repository (for example `.env`, which `*.env` ignores), and that the allowlist auto-approved `git remote:*`, `git pull:*`, `git diff:*` (`--output`, `--no-index`) and `python -m unittest:*`.

Choice: body, rationale and reason files must end in `.local.md`. Mutating git prefixes are removed, exact read-only forms stay, `unittest` is limited to `discover -s tests`, and Bash deny patterns cover `--output`, `--no-index`, `--upload-pack`, `--exec`. Approved by the human via the review plan approval (hash recorded in `review-archive/platform-agent-harness/APPROVED`).

Why: a prefix rule cannot constrain arguments, so the safer reading (D14) is to remove or narrow the prefix. Deny patterns match literal strings and remain a seatbelt, not a sandbox.
