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

Choice: `validate_title` rejects quotes, backticks, `$`, `;`, backslash, and `..` (title rule superseded on 2026-11-14, below). `gh_command` uses `shlex.quote` on the title and the body file name (now `shlex.join` on POSIX and `subprocess.list2cmdline` on `nt`; see 2026-11-14). The issue body stays in the draft markdown and is not copied into the command.

Why: Rejecting the characters at create time does not protect a title that is already on GitHub. Quoting the command does. No new dependency.

## 2026-11-14: Body files must be `.local.md`; the allowlist drops argument-sensitive prefixes

Context: Review of PR #24 found that `ignored_issue_file` accepted any Git-ignored file in the repository (for example `.env`, which `*.env` ignores), and that the allowlist auto-approved `git remote:*`, `git pull:*`, `git diff:*` (`--output`, `--no-index`) and `python -m unittest:*`.

Choice: body, rationale and reason files must end in `.local.md`. Mutating git prefixes are removed, exact read-only forms stay, `unittest` is limited to `discover -s tests`, and Bash deny patterns cover `--output`, `--no-index`, `--upload-pack`, `--exec`. Approved by the human via the review plan approval (the approval record, `review-archive/platform-agent-harness/APPROVED`, is not in this repository, so it was not checked here).

Why: a prefix rule cannot constrain arguments, so the safer reading (D14) is to remove or narrow the prefix. Deny patterns match literal strings and remain a seatbelt, not a sandbox.

## 2026-11-14: Title filter narrowed (supersedes 2026-11-13 title rule); `//` absolute Read paths

Context: The 2026-11-13 entry made `validate_title` reject quotes and `..` anywhere, which refuses ordinary titles such as "Don't drop spans". Titles are passed as argv with `shell=False` and quoted in `gh_command`, so quoting is the real defense.

Choice: reject control characters, backtick, `$(`, `${`, `;`, `|`, `&`, `<`, `>`, backslash and `../` path segments, each with its own message. Accept apostrophes, double quotes and `..` inside words. The quoting decision in the 2026-11-13 entry still stands.

Also: Claude Code permission docs (code.claude.com/docs/en/permissions, checked 2026-11-14) say a single leading `/` anchors at the settings source and absolute paths need `//`. The `Read(/proc/**/environ)` and `Read(/var/run/secrets/**)` denies were replaced with the `//` forms (the plan proposed keeping both; with the syntax verified, the wrong form was dropped).

## 2026-11-14: Symlink check and portable `gh_command`

Context: the symlink check in `ignored_issue_file` ran on the resolved path, where `is_symlink()` is always false. `gh_command` used POSIX quoting only.

Choice: `ignored_issue_file` walks the unresolved path component by component under the repository root and rejects any symlink, so a symlinked parent directory is rejected too (the step 3 plan had proposed leaving symlinked parents followed; the code rejects them). `build_pr_draft` returns `gh_argv` (the portable list) and builds `gh_command` with `shlex.join` on POSIX and `subprocess.list2cmdline` on `nt`. `validate_title` checks ASCII control characters 0x00-0x1f only, so DEL (0x7f) is accepted.

## 2026-11-14: Agent-pairing-kit installed; its settings file is separate from `apply_permissions.py`

Context: commit `2a4b465` installed kit `c8eabf8` (later refreshed for `assertion-check.sh` and `cross-review.ps1`): `scripts/`, `skills/`, `.claude/commands/`, `.claude/settings.json`, `.pairing-profiles`, and a pairing-mode section in `CLAUDE.md`. `scripts/checks/python.sh` was adapted: no `.venv` requirement, `unittest` instead of pytest, no `ruff format --check`.

Finding, not a decision: the kit's `.claude/settings.json` (connectors and artifacts disabled, `WebFetch` asks, 8 deny entries) and `setup/agent-permissions.json` (29 deny entries) are not generated from each other and `apply_permissions.py` never touches the kit file. The kit file originally used `Read(/proc/**/environ)` and `Read(/var/run/secrets/**)` with a single `/`, the form the 2026-11-14 entry above replaced as wrong. Resolved the same day: the kit (agent-pairing-kit `2ccbb85`) now ships the `//` forms and this repo's copy of the file was refreshed to match, so the two sources agree on those two rules. `disableClaudeAiConnectors` and `enableArtifact` were not verified against Claude Code documentation.
