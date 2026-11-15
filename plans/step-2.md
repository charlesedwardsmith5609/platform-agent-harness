# Step 2 - MEDIUM findings (3, 4, 5, 6)

## Findings covered
3. `Read(/proc/**/environ)` deny form.
4. Docs overclaim about Bash denies (partial: `CLAUDE.md` says "seatbelt"; other docs still read as protective).
5. Title filter over-rejects ordinary titles.
6. Hostile-title test does not assert the rejection reason.

## Types
- `validate_title(title: str | None) -> str` raising `IssueError` with distinct messages for control characters vs shell metacharacters.
- `claude_permissions.deny`: list of permission rule strings.

## Shared state ownership
- `setup/platform_harness/taxonomy.py` and `agent-permissions.json`: coordinator-owned.
- `docs/` text: worker-owned within the lane.

## Design notes
- Verify the Claude Code rule syntax before editing: absolute paths use a `//` prefix (`Read(//proc/**/environ)`). Offline this cannot be checked, so keep both entries and record the assumption.
- Title policy: titles are passed as argv with `shell=False` and `gh_command` uses `shlex.quote`, so quoting is the real defense. Allow `'`, `"` and `..` inside words (e.g. "Don't", "v1..v2 diff"); keep rejecting control characters, backtick, `$(`, `${`, `;`, `|`, `&`, `<`, `>`, backslash and path-traversal segments (`../`). Assumption: this narrower list is acceptable; append a new dated DECISIONS.md entry that supersedes the 2026-11-13 one.
- Docs: state in `docs/guides/permissions-and-security.md`, `setup/permissions-setup.md` and `SECURITY.md` that Bash deny patterns match literal strings and are trivially bypassed (variables, encoding, other tools).

## Tests
- `/proc` environ deny entry present in the verified form, asserted exactly.
- Titles `Don't drop spans`, `Fix "quoted" name`, `Upgrade v1.2..v1.3 notes` are accepted.
- Each hostile title is rejected and the message matches the specific reason (`assertRaisesRegex`): newline -> control characters, `$(id)` -> metacharacters, `a; b` -> metacharacters, `../x` -> path traversal.
- The three docs files contain the phrases "not a sandbox" and "seatbelt".

## Files
- `setup/platform_harness/taxonomy.py`
- `setup/agent-permissions.json`
- `tests/test_repo_issue.py`
- `docs/guides/permissions-and-security.md`
- `setup/permissions-setup.md`
- `SECURITY.md`
- `DECISIONS.md`
- `CHANGELOG.md`
